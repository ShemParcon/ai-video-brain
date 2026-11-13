import math, subprocess, functools
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import art, audio

W, H, FPS, R = art.W, art.H, 24, 2
FP = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
FPO = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf'
@functools.lru_cache(maxsize=64)
def font(sz, obl=False):
    try: return ImageFont.truetype(FPO if obl else FP, int(sz))
    except Exception:
        try: return ImageFont.truetype(FP, int(sz))
        except Exception: return ImageFont.load_default(int(sz))
_tmp = ImageDraw.Draw(Image.new('L', (4, 4)))
@functools.lru_cache(maxsize=512)
def base_size(text, size, maxw, obl=False):
    while size > 36:
        if _tmp.textlength(text, font=font(size, obl)) <= maxw: return size
        size -= 4
    return 36

def chunks(text):
    words = audio.clean(text).split(); out = []; i = 0
    while i < len(words):
        w = words[i]
        if len(w) <= 2 and i + 1 < len(words) and len(w) + len(words[i + 1]) <= 10: out.append(w + ' ' + words[i + 1]); i += 2
        else: out.append(w); i += 1
    return out or ['']

def chunks_phrase(text, n=3, maxc=19):
    out, cur = [], []
    for w in audio.clean(text).split():
        if cur and (len(cur) >= n or len(' '.join(cur + [w])) > maxc): out.append(' '.join(cur)); cur = []
        cur.append(w)
    if cur: out.append(' '.join(cur))
    return out or ['']

def mouth_curve(a):
    win = audio.SR // FPS; n = max(1, len(a) // win)
    env = np.array([np.sqrt(np.mean(a[i * win:(i + 1) * win] ** 2)) if len(a[i * win:(i + 1) * win]) else 0 for i in range(n)])
    v = np.clip((env / (np.percentile(env, 90) + 1e-6)) ** .8 * 1.1, 0, 1); out = []; cur = 0.0
    for x in v:
        cur += (x - cur) * (.65 if x > cur else .3); out.append(cur)
    return out

HS = {1: 820, 2: 660, 3: 540}; XS = {1: [360], 2: [190, 530], 3: [120, 360, 600]}
REACT = {'angry': 'surprised', 'surprised': 'surprised', 'happy': 'happy', 'sad': 'sad', 'neutral': 'neutral'}

def ease_io(p):
    p = min(1.0, max(0.0, p)); return 4 * p ** 3 if p < .5 else 1 - (-2 * p + 2) ** 3 / 2

def render(scenes, lines, chars, total, voice_wav, out_mp4, style='color', watermark=''):
    sk = style == 'sketch'
    cfn = art.draw_char_sketch if sk else art.draw_char; bgfn = art.draw_bg_sketch if sk else art.draw_bg
    for l in lines: l['a'] = mouth_curve(l['audio']); l['chunks'] = chunks_phrase(l['text']) if sk else chunks(l['text'])
    wm = None
    if watermark:
        wi = Image.new('L', (W, H), 0); ImageDraw.Draw(wi).text((W // 2, 560), watermark.upper(), font=font(44, True), fill=255, anchor='mm')
        wm = wi.point(lambda v: int(v * .30))
    roles = []
    for sc in scenes:
        for r in sc['roles']:
            if r not in roles: roles.append(r)
    ph = {r: (hash(r) % 628) / 100 for r in roles}
    # per-scene layout
    lay = []
    for sc in scenes:
        n = len(sc['roles']); out = {}
        for r, x in zip(sc['roles'], XS[n]):
            sc_ = chars[r]['look'].get('scale', 1.0); out[r] = dict(x=x, s=HS[n] * sc_ / 735)
        lay.append(out)
    scene_t0 = []
    for i in range(len(scenes)):
        f = [l['start'] for l in lines if l['scene'] == i]; scene_t0.append(0 if i == 0 else (f[0] - .5 if f else 1e9))
    # emotion events per role
    ev = {r: [(0, 'neutral')] for r in roles}
    for l in lines:
        ev[l['who']].append((l['start'], l['emotion']))
        for o in scenes[l['scene']]['roles']:
            if o != l['who']: ev[o].append((l['start'] + .25, REACT.get(l['emotion'], 'neutral')))
    for r in roles: ev[r].sort()
    role_lines = {r: [l for l in lines if l['who'] == r] for r in roles}
    hook = scenes[0].get('hook', '')

    def target(l):
        L = lay[l['scene']][l['who']]; s = L['s']; hy = 1120 - (262 + 220 + 112) * s; hw = 236 * s
        z = min(1.9, 400 / hw); ch, cw = H / z, W / z
        return (min(max(L['x'], cw / 2), W - cw / 2), min(max(hy + .10 * ch, ch / 2), H - ch / 2), z)
    targets = [target(l) for l in lines]; wide = (W / 2, H / 2, 1.0)

    def camera(t):
        idx = -1
        for i, l in enumerate(lines):
            if l['start'] <= t: idx = i
        if idx < 0: return wide
        l = lines[idx]; tg = targets[idx]; first = idx == 0 or lines[idx - 1]['scene'] != l['scene']
        pv = wide if first else (targets[idx - 1][0], targets[idx - 1][1], targets[idx - 1][2] * 1.04)
        e = ease_io((t - l['start'] - (0 if (sk or not first) else .2)) / (.05 if sk else .45))
        dr = 1 + .04 * min(1, (t - l['start']) / max(.5, l['end'] - l['start']))
        return (pv[0] + (tg[0] - pv[0]) * e + 2.5 * math.sin(t * .9), pv[1] + (tg[1] - pv[1]) * e + 2 * math.sin(t * 1.3 + 1), pv[2] + (tg[2] * dr - pv[2]) * e)

    cmd = ['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
           '-i', voice_wav, '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '24', '-pix_fmt', 'yuv420p',
           '-c:a', 'aac', '-b:a', '128k', '-shortest', '-movflags', '+faststart', out_mp4]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(int(total * FPS)):
        t = f / FPS
        cur = next((l for l in lines if l['start'] <= t < l['end']), None)
        si = cur['scene'] if cur else max([i for i in range(len(scenes)) if scene_t0[i] <= t] or [0])
        cx, cy, z = camera(t)
        im = Image.new('RGB', (W * R, H * R)); d = art.Tr(ImageDraw.Draw(im), R * z, cx, cy, W * R, H * R)
        setting = scenes[si]['setting']; bgfn(d, setting); shadow = art.shadow_color(setting)
        order = [r for r in scenes[si]['roles'] if not (cur and r == cur['who'])] + ([cur['who']] if cur else [])
        for r in order:
            L = lay[si][r]; k = scenes[si]['roles'].index(r)
            pe = art.ease_back((t - scene_t0[si] - .12 * k) / .5)
            if pe <= .02: continue
            a = 0.0; arm_side = 1
            for i, l in enumerate(role_lines[r]):
                if l['start'] <= t: arm_side = 1 if i % 2 == 0 else -1
            if cur and cur['who'] == r:
                idx = int((t - cur['start']) * FPS); a = cur['a'][min(idx, len(cur['a']) - 1)]
            g = 0.0
            for l in role_lines[r]: g = max(g, art.smooth(min((t - l['start'] + .1) / .2, (l['end'] + .1 - t) / .2)))
            e = ev[r]; j = max(i for i, x in enumerate(e) if x[0] <= t)
            vec = art.emo_vec(e[j - 1][1] if j > 0 else 'neutral', e[j][1], art.smooth((t - e[j][0]) / .22))
            others = [o for o in scenes[si]['roles'] if o != r]
            gaze = 0.0
            if others: gaze = 1.0 if lay[si][others[0]]['x'] > L['x'] else -1.0
            per = 3.1 + .7 * roles.index(r); bp = (t + ph[r] * .5) % per
            blink = math.sin(math.pi * bp / .15) if bp < .15 else 0.0
            A = dict(t=t, g=g, a=a, ph=ph[r], bob=3 * math.sin(2 * math.pi * 1.1 * t + ph[r]) + 8 * a, emo=vec, blink=blink, gaze=gaze, arm_side=arm_side, shadow=shadow)
            cfn(d, chars[r]['look'], L['x'], 1120, L['s'] * min(pe, 1.12), A)
        fr = im.resize((W, H), Image.BILINEAR); dd = ImageDraw.Draw(fr)
        if cur:
            frac = (t - cur['start']) / max(.01, cur['end'] - cur['start']); wl = [len(c) for c in cur['chunks']]; acc = 0; ci = len(wl) - 1; cs0 = 0
            for i, n in enumerate(wl):
                if frac <= acc + n / sum(wl): ci = i; cs0 = acc; break
                acc += n / sum(wl)
            c = cur['chunks'][ci].upper()
            if sk:
                sz = base_size(c, 64, 660, True); dd.text((W // 2, 140), c, font=font(sz, True), fill=(28, 28, 28), anchor='mm')
            else:
                sz = base_size(c, 104, 640)
                pop = .82 + .18 * art.smooth((frac - cs0) * (cur['end'] - cur['start']) / .09)
                dd.text((W // 2, 1060), c, font=font(round(sz * pop / 2) * 2), fill='#fff7c2', stroke_width=11, stroke_fill=(15, 15, 22), anchor='mm')
        if hook and t < 3.0 and not sk:
            sz = base_size(hook, 52, 580); fn = font(sz); tw = dd.textlength(hook, font=fn); x0 = W // 2 - tw // 2 - 28
            dd.rounded_rectangle((x0, 90, x0 + tw + 56, 190), radius=28, fill='#ffd43b', outline=art.OL, width=6)
            dd.text((W // 2, 140), hook, font=fn, fill=art.OL, anchor='mm')
        if wm is not None: fr.paste((140, 140, 140), mask=wm)
        pr.stdin.write(fr.tobytes())
    pr.stdin.close(); pr.wait()
    if pr.returncode: raise RuntimeError('ffmpeg render failed')
