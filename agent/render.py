import json, subprocess, math
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import art, audio

W, H, FPS = art.W, art.H, 24
FP = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
def font(sz):
    try: return ImageFont.truetype(FP, sz)
    except Exception: return ImageFont.load_default(sz)
F_CAP, F_HOOK = font(64), font(52)

def chunks(text, n=3):
    w = audio.clean(text).split()
    return [' '.join(w[i:i + n]) for i in range(0, len(w), n)] or ['']

def mouth_levels(a):
    win = audio.SR // FPS; n = max(1, len(a) // win)
    env = np.array([np.sqrt(np.mean(a[i * win:(i + 1) * win] ** 2)) if len(a[i * win:(i + 1) * win]) else 0 for i in range(n)])
    r = env / (np.percentile(env, 90) + 1e-6)
    return ['closed' if v < .15 else 'small' if v < .5 else 'open' if v < .9 else 'wide' for v in r]

def render(scenes, lines, chars, total, voice_wav, out_mp4):
    """scenes: [{setting, roles}], lines: [{scene, who, text, emotion, start, end, audio}], chars: role -> char dict"""
    bgs = [art.make_bg(s['setting']) for s in scenes]
    for l in lines: l['lv'] = mouth_levels(l['audio']); l['chunks'] = chunks(l['text'])
    scene_start = []
    for i in range(len(scenes)):
        f = [l['start'] for l in lines if l['scene'] == i]; scene_start.append(0 if i == 0 else (f[0] - .15 if f else 1e9))
    hook = scenes[0].get('hook', '')
    cache = {}
    def compose(si, speaker, mouth, bounce, blink, emo, cap, hk):
        k = (si, speaker, mouth, bounce, blink, emo, cap, hk)
        if k in cache: return cache[k]
        im = bgs[si].copy(); roles = scenes[si]['roles']; n = len(roles)
        s = {1: 1.5, 2: 1.25, 3: .95}[n]; xs = {1: [360], 2: [190, 530], 3: [120, 360, 600]}[n]
        for role, x in zip(roles, xs):
            ch = chars[role]; sc = ch['look'].get('scale', 1.0); sw, sh = int(300 * s * sc), int(420 * s * sc)
            me = role == speaker
            spr = art.sprite(json.dumps(ch['look']), mouth if me else 'closed', emo if me else 'neutral', blink, sw, sh)
            im.paste(spr, (x - sw // 2, 1010 - sh + (bounce if me else 0)), spr)
        d = ImageDraw.Draw(im)
        if cap: d.text((W // 2, 1110), cap, font=F_CAP, fill='white', stroke_width=8, stroke_fill=(20, 20, 28), anchor='mm')
        if hk:
            tw = d.textlength(hk, font=F_HOOK); x0 = W // 2 - tw // 2 - 28
            d.rounded_rectangle((x0, 90, x0 + tw + 56, 190), radius=28, fill='#ffd43b', outline=art.OL, width=6)
            d.text((W // 2, 140), hk, font=F_HOOK, fill=art.OL, anchor='mm')
        b = im.tobytes(); cache[k] = b
        if len(cache) > 1500: cache.pop(next(iter(cache)))
        return b
    cmd = ['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-',
           '-i', voice_wav, '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '25', '-pix_fmt', 'yuv420p',
           '-c:a', 'aac', '-b:a', '128k', '-shortest', '-movflags', '+faststart', out_mp4]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(int(total * FPS)):
        t = f / FPS
        si = max([i for i in range(len(scenes)) if scene_start[i] <= t] or [0])
        cur = next((l for l in lines if l['start'] <= t < l['end']), None)
        speaker = mouth = emo = cap = None; bounce = 0
        if cur:
            if cur['scene'] != si: si = cur['scene']
            speaker, emo = cur['who'], cur['emotion']
            mouth = cur['lv'][min(len(cur['lv']) - 1, int((t - cur['start']) * FPS))]
            bounce = [0, -6, 0, -4][int(t * 10) % 4]
            frac = (t - cur['start']) / max(.01, cur['end'] - cur['start']); w = [len(c) for c in cur['chunks']]
            acc = 0; cap = cur['chunks'][-1]
            for c, wl in zip(cur['chunks'], w):
                acc += wl / sum(w)
                if frac <= acc: cap = c; break
        else:
            prev = [l for l in lines if l['end'] <= t]
        pr.stdin.write(compose(si, speaker, mouth or 'closed', bounce, f % 96 in (0, 1), emo or 'neutral', cap, hook if t < 2.8 else ''))
    pr.stdin.close(); pr.wait()
    if pr.returncode: raise RuntimeError('ffmpeg render failed')
