import asyncio, os, re, subprocess, time, wave, random
import numpy as np

SR = 24000
EMOJI = re.compile('[\U00010000-\U0010ffff\u2600-\u27bf\ufe0f\u200d]')
def clean(t): return re.sub(r'\s+', ' ', EMOJI.sub('', t)).strip()

def read_wav(path):
    with wave.open(path) as w: a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    return a

def write_wav(path, a):
    with wave.open(path, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((np.clip(a, -1, 1) * 32767).astype(np.int16).tobytes())

def trim(a):
    idx = np.where(np.abs(a) > 0.012)[0]
    if len(idx) == 0: return a
    return a[max(0, idx[0] - int(.04 * SR)): idx[-1] + int(.08 * SR)]

def tts(text, ch, path):
    text = clean(text)
    if os.getenv('DRY'):
        n = int(SR * max(.8, len(text) * .06)); t = np.arange(n) / SR
        return (np.sin(2 * np.pi * (140 + ch['pitch']) * t) * (.3 + .3 * np.sin(2 * np.pi * 3.5 * t)) ** 2).astype(np.float32)
    import edge_tts
    mp3 = path + '.mp3'
    safe = re.sub(r"[^\w\s.,!?'\u2019\-:;()%/]", ' ', text); safe = re.sub(r'\s+', ' ', safe).strip() or 'Ok'
    alt = 'en-PH-RosaNeural' if ch['voice'].endswith('BlancaNeural') else 'en-PH-JamesNeural'
    tries = [(ch['voice'], f"{ch['rate']:+d}%", f"{ch['pitch']:+d}Hz"), (ch['voice'], '+0%', f"{ch['pitch']:+d}Hz"),
             (ch['voice'], '+0%', '+0Hz'), (ch['voice'], '+0%', '+0Hz'), (alt, '+0%', '+0Hz')]
    last = None
    for v, r, pch in tries:
        try:
            if os.path.exists(mp3): os.remove(mp3)
            asyncio.run(edge_tts.Communicate(safe, v, rate=r, pitch=pch).save(mp3))
            if os.path.getsize(mp3) > 1000: break
        except Exception as e:
            last = e; time.sleep(2)
    else:
        raise RuntimeError(f'voice failed: {str(last)[:150]}')
    wav = path + '.wav'
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-i', mp3, '-ar', str(SR), '-ac', '1', wav], check=True)
    return trim(read_wav(wav))

def sfx(name):
    T = lambda d: np.arange(int(SR * d)) / SR
    if name == 'pop':
        x = T(.15); return np.sin(2 * np.pi * np.cumsum(700 - 3000 * x) / SR) * np.exp(-x * 25)
    if name == 'ding':
        x = T(.8); return np.sin(2 * np.pi * 1320 * x) * np.exp(-x * 6) + .4 * np.sin(2 * np.pi * 1980 * x) * np.exp(-x * 8)
    if name == 'whoosh':
        x = T(.5); n = np.convolve(np.random.randn(len(x)), np.ones(40) / 40, 'same'); return n * np.sin(np.pi * x / .5) ** 2 * 3
    if name == 'bonk':
        x = T(.3); return np.sin(2 * np.pi * np.cumsum(190 - 250 * x) / SR) * np.exp(-x * 14)
    if name == 'sad':
        out = []
        for f, d in ((330, .3), (311, .3), (294, .3), (277, .8)):
            x = T(d); out.append((np.sin(2 * np.pi * f * x) + .4 * np.sin(4 * np.pi * f * x)) * np.exp(-x * 2.5) * .6)
        return np.concatenate(out)
    if name == 'laugh':
        out = []
        for i in range(3):
            x = T(.12); out.append(np.sin(2 * np.pi * (300 - i * 20) * x) * (1 + .5 * np.sin(2 * np.pi * 30 * x)) * np.hanning(len(x))); out.append(np.zeros(int(SR * .08)))
        return np.concatenate(out)
    return None

def music(dur):
    step = 60 / 108 / 2; n = int(dur / step) + 2; out = np.zeros(int((dur + 1) * SR), np.float32)
    scale = [261.63, 293.66, 329.63, 392.0, 440.0, 523.25]
    for i in range(n):
        f = scale[(i * 3 + (i // 8) * 2) % len(scale)]; x = np.arange(int(SR * .4)) / SR
        note = np.sin(2 * np.pi * f * x) * np.exp(-x * 6)
        if i % 4 == 0: note = note + 1.2 * np.sin(2 * np.pi * f / 4 * x) * np.exp(-x * 3)
        s = int(i * step * SR); e = min(len(out), s + len(note))
        if s < e: out[s:e] += note[:e - s]
    return out

def mix(total, lines, path):
    out = np.zeros(int(total * SR) + SR, np.float32)
    for l in lines:
        s = int(l['start'] * SR); out[s:s + len(l['audio'])] += l['audio']
        fx = sfx(l.get('sfx')) if l.get('sfx') else None
        if fx is not None: e = min(len(out), s + len(fx)); out[s:e] += .5 * fx[:e - s]
    m = music(total)[:len(out)]; fade = np.ones(len(m)); k = int(1.2 * SR)
    fade[int(total * SR) - k:] = np.linspace(1, 0, k + len(m) - int(total * SR))[:len(m) - (int(total * SR) - k)]
    out[:len(m)] += .06 * m * fade
    pk = np.abs(out).max()
    if pk > .92: out *= .92 / pk
    write_wav(path, out[:int(total * SR)])
