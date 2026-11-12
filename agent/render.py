import json, subprocess
from collections import OrderedDict
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import art, audio

W, H, FPS, R = art.W, art.H, 24, 2   # R = supersample of the composed scene (for crisp zooms)
FP = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
def font(sz):
    try: return ImageFont.truetype(FP, sz)
    except Exception: return ImageFont.load_default(sz)

def chunks(text):
    """one big word at a time (tiny words join the next word)"""
    words = audio.clean(text).split(); out = []; i = 0
    while i < len(words):
        w = words[i]
        if len(w) <= 2 and i + 1 < len(words) and len(w) + len(words[i + 1]) <= 10: out.append(w + ' ' + words[i + 1]); i += 2
        else: out.append(w); i += 1
    return out or ['']

def fit(d, text, size, maxw):
    while size > 36:
        f = font(size)
        if d.textlength(text, font=f) <= maxw: return f
        size -= 4
    return font(36)

def mouth_levels(a):
    win = audio.SR // FPS; n = max(1, len(a) // win)
    env = np.array([np.sqrt(np.mean(a[i * win:(i + 1) * win] ** 2)) if len(a[i * win:(i + 1) * win]) else 0 for i in range(n)])
    r = env / (np.percentile(env, 90) + 1e-6)
    return ['closed' if v < .15 else 'small' if v < .5 else 'open' if v < .9 else 'wide' for v in r]

def layout(roles, chars):
    n = len(roles); Hs = {1: 820, 2: 660, 3: 540}[n]; xs = {1: [360], 2: [190, 530], 3: [120, 360, 600]}[n]; out = {}
    for role, x in zip(roles, xs):
        sh = int(Hs * chars[role]['look'].get('scale', 1.0)); sw = int(sh * 600 / 1180)
        out[role] = dict(x=x, sh=sh, sw=sw, hy=1120 - sh + int(.284 * sh), hw=.254 * sh)
    return out

def cam_target(L):
    z = min(2.3, 440 / L['hw']); ch = H / z; cw = W / z
    cy = min(max(L['hy'] + .10 * ch, ch / 2), H - ch / 2); cx = min(max(L['x'], cw / 2), W - cw / 2)
    return (cx, cy, z)

def render(scenes, lines, chars, total, voice_wav, out_mp4):
    bgs = [art.make_bg(s['setting']).resize((W * R, H * R), Image.LANCZOS) for s in scenes]
    lay = [layout(s['roles'], chars) for s in scenes]
    for l in lines: l['lv'] = mouth_levels(l['audio']); l['chunks'] = chunks(l['text'])
    scene_start = []
    for i in range(len(scenes)):
        f = [l['start'] for l in lines if l['scene'] == i]; scene_start.append(0 if i == 0 else (f[0] - .15 if f else 1e9))
    hook = scenes[0].get('hook', '')
    wide = (W / 2, H / 2, 1.0)
    targets = [cam_target(lay[l['scene']][l['who']]) for l in lines]

    def camera(t):
        idx = -1
        for i, l in enumerate(lines):
            if l['start'] <= t: idx = i
        if idx < 0: return wide
        l = lines[idx]; tg = targets[idx]; first = idx == 0 or lines[idx - 1]['scene'] != l['scene']
        prev = wide if first else (targets[idx - 1][0], targets[idx - 1][1], targets[idx - 1][2] * 1.05)
        delay = .3 if first else 0
        p = min(1, max(0, (t - l['start'] - delay) / .16)); e = p * p * (3 - 2 * p)
        drift = 1 + .05 * min(1, (t - l['start']) / max(.5, l['end'] - l['start']))
        return (prev[0] + (tg[0] - prev[0]) * e, prev[1] + (tg[1] - prev[1]) * e, prev[2] + (tg[2] * drift - prev[2]) * e)

    cache = OrderedDict()
    def scene_img(si, speaker, mouth, bounce, blink, emo, pose):
        k = (si, speaker, mouth, bounce, blink, emo, pose)
        if k in cache: cache.move_to_end(k); return cache[k]
        im = bgs[si].copy()
        for role, L in lay[si].items():
            me = role == speaker; ch = chars[role]
            spr = art.sprite(json.dumps(ch['look']), mouth if me else 'closed', emo if me else 'neutral', blink, pose if me else 0, L['sw'] * R, L['sh'] * R)
            im.paste(spr, ((L['x'] - L['sw'] // 2) * R, (1120 - L['sh'] + (bounce if me else 0)) * R), spr)
        cache[k] = im
        if len(cache) > 24: cache.popitem(last=False)
        return im

    cmd = ['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
           '-i', voice_wav, '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '25', '-pix_fmt', 'yuv420p',
           '-c:a', 'aac', '-b:a', '128k', '-shortest', '-movflags', '+faststart', out_mp4]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(int(total * FPS)):
        t = f / FPS
        si = max([i for i in range(len(scenes)) if scene_start[i] <= t] or [0])
        cur = next((l for l in lines if l['start'] <= t < l['end']), None)
        speaker = mouth = emo = cap = None; bounce = 0; pose = 0
        if cur:
            si = cur['scene']; speaker, emo = cur['who'], cur['emotion']
            mouth = cur['lv'][min(len(cur['lv']) - 1, int((t - cur['start']) * FPS))]
            bounce = [0, -6, 0, -4][int(t * 10) % 4]; pose = [0, 1, 0, 2][int(t * 3) % 4]
            frac = (t - cur['start']) / max(.01, cur['end'] - cur['start']); wl = [len(c) for c in cur['chunks']]
            acc = 0; cap = cur['chunks'][-1]
            for c, n in zip(cur['chunks'], wl):
                acc += n / sum(wl)
                if frac <= acc: cap = c; break
        src = scene_img(si, speaker, mouth or 'closed', bounce, f % 96 in (0, 1), emo or 'neutral', pose)
        cx, cy, z = camera(t); hw, hh = W / (2 * z), H / (2 * z)
        cx = min(max(cx, hw), W - hw); cy = min(max(cy, hh), H - hh)
        im = src.resize((W, H), Image.BILINEAR, box=((cx - hw) * R, (cy - hh) * R, (cx + hw) * R, (cy + hh) * R))
        d = ImageDraw.Draw(im)
        if cap:
            c = cap.upper(); fnt = fit(d, c, 104, 640)
            d.text((W // 2, 1060), c, font=fnt, fill='#fff7c2', stroke_width=11, stroke_fill=(15, 15, 22), anchor='mm')
        if hook and t < 2.8:
            fnt = fit(d, hook, 52, 580); tw = d.textlength(hook, font=fnt); x0 = W // 2 - tw // 2 - 28
            d.rounded_rectangle((x0, 90, x0 + tw + 56, 190), radius=28, fill='#ffd43b', outline=art.OL, width=6)
            d.text((W // 2, 140), hook, font=fnt, fill=art.OL, anchor='mm')
        pr.stdin.write(im.tobytes())
    pr.stdin.close(); pr.wait()
    if pr.returncode: raise RuntimeError('ffmpeg render failed')
