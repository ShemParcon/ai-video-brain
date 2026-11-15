import random, math
from PIL import Image, ImageDraw

W, H = 720, 1280
OL = (35, 35, 45)
SKINS = ['#f6d1a7', '#e8b98a', '#d29b6b', '#b9784a', '#8d5a3b']
HAIRS = ['#1b1b22', '#2e1f16', '#4a2e1f', '#1f2a44', '#6b2d1a']
SHIRTS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#14b8a6', '#ec4899', '#64748b', '#f97316']
HELMET = ('miner', 'rescuer', 'worker', 'engineer', 'firefighter', 'climber', 'driller', 'crew', 'diver', 'paramedic', 'caver')
OFFICE = ('boss', 'manager', 'hr', 'sir', 'ceo', 'supervisor', 'direktor', 'employer', 'amo')
M_VOICES = ['en-US-GuyNeural', 'en-US-ChristopherNeural', 'en-US-EricNeural', 'en-US-RogerNeural', 'en-US-SteffanNeural', 'en-GB-RyanNeural']
F_VOICES = ['en-US-JennyNeural', 'en-US-AriaNeural', 'en-US-MichelleNeural', 'en-GB-SoniaNeural', 'en-AU-NatashaNeural']
KID_VOICE = 'en-US-AnaNeural'

def get_char(reg, page, role, gender='M', age='adult'):
    """Same page+role always returns the same look and voice (saved in data/characters.json)."""
    key = f"{page}:{role.strip().lower()}"
    if key in reg and reg[key].get('v') == 3: return reg[key]
    gender = 'F' if str(gender).upper().startswith('F') else 'M'
    age = age if age in ('kid', 'adult', 'old') else 'adult'
    r = random.Random(key)
    style = r.choice(['long', 'bun', 'long']) if gender == 'F' else r.choice(['short', 'short', 'cap', 'bald'])
    if age in ('old', 'kid'): style = 'bun' if gender == 'F' else 'short'
    helm = any(k in role.lower() for k in HELMET)
    if helm: style = 'helmet'
    look = dict(skin=r.choice(SKINS), hair='#b9b9c0' if age == 'old' else r.choice(HAIRS), shirt=r.choice(SHIRTS),
                style=style, glasses=r.random() < (0.5 if age == 'old' else 0.22),
                tie=gender == 'M' and age == 'adult' and any(k in role.lower() for k in OFFICE),
                cap=r.choice(['#c0392b', '#2563eb', '#16a34a']), scale=0.85 if age == 'kid' else 1.0,
                pants=r.choice(['#334155', '#1e3a8a', '#4b5563', '#3f3f46', '#713f12']), shoe=r.choice(['#1f2937', '#f8fafc', '#7f1d1d']),
                skirt=gender == 'F' and r.random() < .5, skirtc=r.choice(['#be185d', '#0f766e', '#7c3aed', '#b45309']))
    pool = F_VOICES if gender == 'F' else M_VOICES
    used = [c['voice'] for c in reg.values() if c.get('v') == 3 and c.get('page') == page]
    voice = KID_VOICE if age == 'kid' and KID_VOICE not in used else None
    if not voice:
        k = r.randint(0, len(pool) - 1)
        order = pool[k:] + pool[:k]
        if age == 'old' and gender == 'M': order = ['en-US-RogerNeural'] + order
        voice = next((v for v in order if v not in used), order[0])
    if helm: look['shirt'] = '#f97316'
    reg[key] = dict(v=3, page=page, role=role, gender=gender, age=age, look=look, voice=voice,
                    pitch=-6 if age == 'old' else 0, rate={'kid': 4, 'old': -4}.get(age, r.randint(2, 8)))
    return reg[key]


class Tr:
    """Drawing wrapper: world coords (720x1280) -> camera view (pan/zoom), everything stays vector-sharp."""
    def __init__(s, d, k, cx, cy, ow, oh): s.d, s.k, s.cx, s.cy, s.ox, s.oy = d, k, cx, cy, ow / 2, oh / 2
    def p(s, x, y): return ((x - s.cx) * s.k + s.ox, (y - s.cy) * s.k + s.oy)
    def _s(s, v):
        if isinstance(v[0], (tuple, list)): return [s.p(x, y) for x, y in v]
        out = []
        for i in range(0, len(v), 2): out.extend(s.p(v[i], v[i + 1]))
        return out
    def _w(s, w): return max(1, int(round(w * s.k)))
    def ellipse(s, box, fill=None, outline=None, width=1): s.d.ellipse(s._s(box), fill=fill, outline=outline, width=s._w(width))
    def rectangle(s, box, fill=None, outline=None, width=1): s.d.rectangle(s._s(box), fill=fill, outline=outline, width=s._w(width))
    def rounded_rectangle(s, box, radius=0, fill=None, outline=None, width=1): s.d.rounded_rectangle(s._s(box), radius=radius * s.k, fill=fill, outline=outline, width=s._w(width))
    def polygon(s, pts, fill=None, outline=None, width=1): s.d.polygon(s._s(pts), fill=fill, outline=outline, width=s._w(width))
    def line(s, pts, fill=None, width=1): s.d.line(s._s(pts), fill=fill, width=s._w(width))
    def arc(s, box, start, end, fill=None, width=1): s.d.arc(s._s(box), start, end, fill=fill, width=s._w(width))
    def pieslice(s, box, start, end, fill=None, outline=None, width=1): s.d.pieslice(s._s(box), start, end, fill=fill, outline=outline, width=s._w(width))

def smooth(x):
    x = min(1.0, max(0.0, x)); return x * x * (3 - 2 * x)

def ease_back(p):
    p = min(1.0, max(0.0, p)); c1 = 1.70158; c3 = c1 + 1
    return 1 + c3 * (p - 1) ** 3 + c1 * (p - 1) ** 2

# emotion = (brow tilt, brow lift, eye scale, smile)
EMO = {'neutral': (0.0, 0, 1.0, 0.15), 'happy': (-0.25, 3, 0.92, 1.0), 'angry': (1.0, -5, 0.92, -0.5),
       'sad': (-1.0, 3, 1.0, -1.0), 'surprised': (0.0, 16, 1.25, 0.0)}
def emo_vec(a, b, p): return tuple(x + (y - x) * p for x, y in zip(EMO.get(a, EMO['neutral']), EMO.get(b, EMO['neutral'])))

def draw_char(d, look, x0, gy, s, A):
    """Procedural stick-bean character. x0,gy = feet position (world), s = scale, A = animation params."""
    skin, hair, shirt, style = look['skin'], look['hair'], look['shirt'], look['style']
    t, g, a, ph = A['t'], A['g'], A['a'], A['ph']
    ow = 8 * s
    hip = -262 + A['bob']; shy = hip - 220
    xu = x0 + 5 * math.sin(t * 1.3 + ph) * s
    U = lambda lx, ly: (xu + lx * s, gy + ly * s)
    pants = look.get('pants', '#334155'); skirt = look.get('skirt', False)
    d.ellipse((x0 - 95 * s, gy - 10 * s, x0 + 95 * s, gy + 16 * s), fill=A['shadow'])
    # legs
    legc = skin if skirt else pants
    ank = []
    for sd in (-1, 1):
        hp = (xu + sd * 38 * s, gy + hip * s); an = (x0 + sd * 52 * s, gy - 16 * s)
        kn = ((hp[0] + an[0]) / 2 + sd * 6 * s, (hp[1] + an[1]) / 2)
        d.line([hp, kn, an], fill=OL, width=26 * s)
        for q in (hp, kn, an): d.ellipse((q[0] - 13 * s, q[1] - 13 * s, q[0] + 13 * s, q[1] + 13 * s), fill=OL)
        d.line([hp, kn, an], fill=legc, width=15 * s)
        for q in (kn, an): d.ellipse((q[0] - 7.5 * s, q[1] - 7.5 * s, q[0] + 7.5 * s, q[1] + 7.5 * s), fill=legc)
        ank.append(an)
    for an in ank:
        d.ellipse((an[0] - 42 * s, an[1] - 6 * s, an[0] + 42 * s, an[1] + 26 * s), fill=look.get('shoe', '#1f2937'), outline=OL, width=ow)
    # torso
    d.rounded_rectangle((xu - 80 * s, gy + (shy - 8) * s, xu + 80 * s, gy + (hip + 22) * s), radius=62 * s, fill=shirt, outline=OL, width=ow)
    if skirt: d.polygon([U(-84, hip - 6), U(84, hip - 6), U(114, hip + 105), U(-114, hip + 105)], fill=look.get('skirtc', pants), outline=OL, width=ow)
    if look.get('tie'): d.polygon([U(-14, shy + 12), U(14, shy + 12), U(20, shy + 95), U(0, shy + 125), U(-20, shy + 95)], fill='#b3202a', outline=OL, width=ow * .6)
    # arms
    for sd in (-1, 1):
        gest = sd == A['arm_side']
        if gest: au = 12 + g * (46 + 22 * math.sin(2 * math.pi * .9 * t + ph) + 28 * a); bend = 10 + g * (34 + 18 * math.sin(2 * math.pi * 1.3 * t + ph))
        else: au = 10 + 4 * math.sin(1.2 * t + ph + sd) + g * 10; bend = 8 + 4 * math.sin(1.7 * t + ph) + g * 8
        sx, sy = U(sd * 70, shy + 14)
        a1, a2 = math.radians(au), math.radians(au + bend)
        e = (sx + sd * math.sin(a1) * 118 * s, sy + math.cos(a1) * 118 * s); h = (e[0] + sd * math.sin(a2) * 108 * s, e[1] + math.cos(a2) * 108 * s)
        d.line([(sx, sy), e, h], fill=OL, width=24 * s)
        for q in ((sx, sy), e, h): d.ellipse((q[0] - 12 * s, q[1] - 12 * s, q[0] + 12 * s, q[1] + 12 * s), fill=OL)
        d.line([(sx, sy), e], fill=shirt, width=14 * s); d.line([e, h], fill=skin, width=14 * s)
        d.ellipse((sx - 7 * s, sy - 7 * s, sx + 7 * s, sy + 7 * s), fill=shirt); d.ellipse((e[0] - 7 * s, e[1] - 7 * s, e[0] + 7 * s, e[1] + 7 * s), fill=skin)
        d.ellipse((h[0] - 19 * s, h[1] - 19 * s, h[0] + 19 * s, h[1] + 19 * s), fill=skin, outline=OL, width=ow * .8)
    # head
    hx, hy = U(0, shy - 112 + 5 * a)
    rot = math.radians(3 * math.sin(1.1 * t + ph) + g * 4 * math.sin(2.3 * t + ph)); cs, sn = math.cos(rot), math.sin(rot)
    HP = lambda dx, dy: (hx + (dx * cs - dy * sn) * s, hy + (dx * sn + dy * cs) * s)
    if style == 'long': d.rounded_rectangle((hx - 128 * s, hy - 95 * s, hx + 128 * s, hy + 170 * s), radius=80 * s, fill=hair, outline=OL, width=ow)
    for sd in (-1, 1):
        ex, ey = HP(sd * 114, 10); d.ellipse((ex - 19 * s, ey - 19 * s, ex + 19 * s, ey + 19 * s), fill=skin, outline=OL, width=ow * .8)
    d.ellipse((hx - 118 * s, hy - 118 * s, hx + 118 * s, hy + 118 * s), fill=skin, outline=OL, width=ow)
    if style != 'bald':
        c = look['cap'] if style == 'cap' else hair
        d.pieslice((hx - 122 * s, hy - 122 * s, hx + 122 * s, hy + 62 * s), 180, 360, fill=c)
        d.arc((hx - 122 * s, hy - 122 * s, hx + 122 * s, hy + 62 * s), 180, 360, fill=OL, width=ow)
        if style == 'bun': d.ellipse((hx - 36 * s, hy - 168 * s, hx + 36 * s, hy - 100 * s), fill=hair, outline=OL, width=ow)
        if style == 'cap': d.rounded_rectangle((hx - 10 * s, hy - 44 * s, hx + 160 * s, hy - 16 * s), radius=14 * s, fill=c, outline=OL, width=ow)
    tilt, lift, es, smile = A['emo']
    for sd in (-1, 1):
        cx_, cy_ = HP(sd * 43, 6)
        rx = 27 * es * s; ry = 31 * es * s * (1 - .92 * A['blink']) * (1 - .3 * max(0, smile))
        d.ellipse((cx_ - rx, cy_ - ry, cx_ + rx, cy_ + ry), fill='white', outline=OL, width=ow * .75)
        if A['blink'] < .8:
            pr = 12 * s; px = cx_ + A['gaze'] * 6 * s; py = cy_ + 1.5 * s
            d.ellipse((px - pr, py - pr, px + pr, py + pr), fill=OL)
        base = -52 - lift
        d.line([HP(sd * 16, base + tilt * 16), HP(sd * 68, base - tilt * 16)], fill=OL, width=9 * s)
    mx, my = HP(0, 66)
    if a > .05:
        w = 44 - 10 * a; h = 6 + 58 * a; top = my - 6 * s; bot = top + h * s
        d.ellipse((mx - w * s, top, mx + w * s, bot), fill='#6b1020', outline=OL, width=ow * .75)
        if a > .4: d.ellipse((mx - w * .55 * s, bot - .38 * h * s, mx + w * .55 * s, bot - 3 * s), fill='#e8707a')
    elif abs(smile) < .2: d.line([HP(-26, 70), HP(26, 70)], fill=OL, width=8 * s)
    elif smile > 0:
        c = (8 + 30 * smile) * s; d.arc((mx - 40 * s, my - c, mx + 40 * s, my + c), 10, 170, fill=OL, width=8 * s)
    else:
        cy2 = my + 22 * s; c = (6 + 24 * -smile) * s; d.arc((mx - 32 * s, cy2 - c, mx + 32 * s, cy2 + c), 190, 350, fill=OL, width=8 * s)
    if look.get('glasses'):
        for sd in (-1, 1):
            q = HP(sd * 43, 6); d.ellipse((q[0] - 40 * s, q[1] - 40 * s, q[0] + 40 * s, q[1] + 40 * s), outline=OL, width=5 * s)
        d.line([HP(-3, 6), HP(3, 6)], fill=OL, width=5 * s)

SETTINGS = {'opisina': ('#dbe7f3', '#8d99a6'), 'bahay': ('#fde8c8', '#b98b5e'), 'kusina': ('#e9f5e1', '#c9b28a'),
            'kwarto': ('#e6dcf5', '#a58bc9'), 'paaralan': ('#f7f1cf', '#9c8456'), 'kalye': ('#bfe3f7', '#6b7280'),
            'palengke': ('#ffe3d6', '#a8825a'), 'simbahan': ('#f3efe6', '#8b7355'), 'cafe': ('#f1e0d0', '#7a5a42'),
            'parke': ('#c7ecff', '#6abf69')}
ALIAS = {'office': 'opisina', 'home': 'bahay', 'living': 'bahay', 'sala': 'bahay', 'kitchen': 'kusina', 'bedroom': 'kwarto', 'school': 'paaralan',
         'classroom': 'paaralan', 'street': 'kalye', 'market': 'palengke', 'store': 'palengke', 'shop': 'palengke', 'church': 'simbahan',
         'park': 'parke', 'coffee': 'cafe', 'restaurant': 'cafe', 'garden': 'parke', 'outside': 'kalye'}

def norm_setting(s):
    s = (s or '').lower()
    for k in SETTINGS:
        if k in s: return k
    for k, v in ALIAS.items():
        if k in s: return v
    return 'bahay'

def shadow_color(setting):
    f = SETTINGS.get(setting, SETTINGS['bahay'])[1].lstrip('#')
    return tuple(int(int(f[i:i + 2], 16) * .78) for i in (0, 2, 4))

def draw_bg(d, setting):
    wall, floor = SETTINGS.get(setting, SETTINGS['bahay'])
    d.rectangle((-300, -300, W + 300, H + 300), fill=wall)
    d.rectangle((-300, 830, W + 300, H + 300), fill=floor); d.line((-300, 830, W + 300, 830), fill=OL, width=6)
    def win(x, y, w, h, c='#bfe6ff'):
        d.rectangle((x, y, x + w, y + h), fill=c, outline=OL, width=6); d.line((x + w // 2, y, x + w // 2, y + h), fill=OL, width=5); d.line((x, y + h // 2, x + w, y + h // 2), fill=OL, width=5)
    if setting == 'opisina':
        win(40, 200, 240, 240); d.ellipse((520, 190, 640, 310), fill='white', outline=OL, width=6); d.line((580, 250, 580, 205), fill=OL, width=6); d.line((580, 250, 612, 262), fill=OL, width=6)
        d.rectangle((560, 700, 640, 830), fill='#8a5a3c', outline=OL, width=6); d.ellipse((540, 600, 660, 720), fill='#3fa34d', outline=OL, width=6)
    elif setting in ('bahay', 'kwarto'):
        win(60, 220, 220, 260, '#cfeeff'); d.rectangle((40, 200, 90, 500), fill='#e76f51', outline=OL, width=5); d.rectangle((250, 200, 300, 500), fill='#e76f51', outline=OL, width=5)
        d.rectangle((450, 230, 620, 360), fill='#fff', outline=OL, width=6); d.ellipse((490, 255, 580, 335), fill='#f4a261', outline=OL, width=5)
    elif setting == 'kusina':
        for x in range(0, W, 90):
            for y in range(0, 830, 90): d.rectangle((x, y, x + 90, y + 90), outline='#c9d8c0', width=3)
        d.rectangle((40, 260, 360, 380), fill='#c49a6c', outline=OL, width=6); d.rectangle((460, 640, 700, 830), fill='#cfd8dc', outline=OL, width=6)
    elif setting == 'paaralan':
        d.rectangle((70, 200, 650, 520), fill='#2f6f4f', outline='#8a5a3c', width=14); d.line((130, 300, 330, 300), fill='white', width=6); d.line((130, 360, 420, 360), fill='white', width=6); d.line((130, 420, 260, 420), fill='white', width=6)
    elif setting == 'kalye':
        d.ellipse((560, 70, 660, 170), fill='#ffe066', outline=OL, width=5)
        for x, h, c in [(20, 420, '#e5989b'), (230, 520, '#b5838d'), (470, 380, '#6d6875')]:
            d.rectangle((x, 830 - h, x + 200, 830), fill=c, outline=OL, width=6)
            for yy in range(830 - h + 40, 800, 90): d.rectangle((x + 30, yy, x + 70, yy + 50), fill='#ffe8a3', outline=OL, width=4); d.rectangle((x + 120, yy, x + 160, yy + 50), fill='#ffe8a3', outline=OL, width=4)
    elif setting == 'palengke':
        for i in range(9): d.rectangle((i * 80, 180, i * 80 + 80, 300), fill='#ef476f' if i % 2 == 0 else '#fff', outline=OL, width=4)
        d.rectangle((0, 640, W, 830), fill='#c08552', outline=OL, width=6)
        for i, c in enumerate(['#f94144', '#f9c74f', '#90be6d', '#f8961e', '#43aa8b']): d.ellipse((30 + i * 130, 590, 120 + i * 130, 650), fill=c, outline=OL, width=4)
    elif setting == 'simbahan':
        d.rounded_rectangle((250, 150, 470, 560), radius=110, fill='#b8d8f0', outline=OL, width=7); d.line((360, 190, 360, 380), fill=OL, width=8); d.line((310, 250, 410, 250), fill=OL, width=8)
        d.rectangle((0, 650, W, 830), fill='#7a5a3a', outline=OL, width=6)
    elif setting == 'cafe':
        win(40, 200, 260, 230, '#ffe9c7'); d.rectangle((430, 230, 680, 330), fill='#3d2b1f', outline=OL, width=6); d.rectangle((460, 560, 680, 830), fill='#a47148', outline=OL, width=6)
    elif setting == 'parke':
        d.ellipse((540, 80, 650, 190), fill='#ffe066', outline=OL, width=5)
        for x in (90, 560): d.rectangle((x - 25, 480, x + 25, 830), fill='#8a5a3c', outline=OL, width=6); d.ellipse((x - 130, 220, x + 130, 540), fill='#3fa34d', outline=OL, width=6)

# ======================= "sketch" style (minimal black & white cartoon) =======================
def _shade(hexc, f):
    h = hexc.lstrip('#'); return tuple(int(int(h[i:i + 2], 16) * f) for i in (0, 2, 4))

def _lum(hexc):
    h = hexc.lstrip('#'); r, g, b = [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    return .3 * r + .59 * g + .11 * b

def draw_char_sketch(d, look, x0, gy, s, A):
    t, g, a, ph = A['t'], A['g'], A['a'], A['ph']
    lw = 4.5 * s; GREY = '#cfcfcf'
    hip = -262 + A['bob']; shy = hip - 220
    xu = x0 + 5 * math.sin(t * 1.3 + ph) * s
    U = lambda lx, ly: (xu + lx * s, gy + ly * s)
    dark = _lum(look['shirt']) < 105
    hairc = '#4a4a4a' if _lum(look['hair']) < 150 else '#a8a8a8'
    style = look['style']
    d.ellipse((x0 - 90 * s, gy - 6 * s, x0 + 90 * s, gy + 12 * s), fill='#e6e6e6')
    for sd in (-1, 1):
        hp = (xu + sd * 30 * s, gy + hip * s); an = (x0 + sd * 40 * s, gy - 4 * s)
        d.line([hp, an], fill=OL, width=lw); d.line([an, (an[0] + sd * 26 * s, an[1])], fill=OL, width=lw)
    box = (xu - 76 * s, gy + (shy - 8) * s, xu + 76 * s, gy + (hip + 20) * s)
    if A.get('colored'):
        d.rounded_rectangle(box, radius=60 * s, fill=_shade(look['shirt'], .72)); d.rounded_rectangle((box[0], box[1], box[2] - 30 * s, box[3]), radius=60 * s, fill=look['shirt'])
    elif dark: d.rounded_rectangle(box, radius=60 * s, fill='#6b6b6b')
    else:
        d.rounded_rectangle(box, radius=60 * s, fill=GREY)
        d.rounded_rectangle((box[0], box[1], box[2] - 30 * s, box[3]), radius=60 * s, fill='white')
    d.rounded_rectangle(box, radius=60 * s, outline=OL, width=lw)
    if look.get('tie'): d.polygon([U(-12, shy + 8), U(12, shy + 8), U(18, shy + 90), U(0, shy + 118), U(-18, shy + 90)], fill='#222222', outline=OL, width=lw * .6)
    for sd in (-1, 1):
        gest = sd == A['arm_side']
        if gest: au = 12 + g * (46 + 22 * math.sin(2 * math.pi * .9 * t + ph) + 28 * a); bend = 10 + g * (34 + 18 * math.sin(2 * math.pi * 1.3 * t + ph))
        else: au = 10 + 4 * math.sin(1.2 * t + ph + sd) + g * 10; bend = 8 + 4 * math.sin(1.7 * t + ph) + g * 8
        sx, sy = U(sd * 66, shy + 18); a1, a2 = math.radians(au), math.radians(au + bend)
        e = (sx + sd * math.sin(a1) * 118 * s, sy + math.cos(a1) * 118 * s); h = (e[0] + sd * math.sin(a2) * 108 * s, e[1] + math.cos(a2) * 108 * s)
        d.line([(sx, sy), e, h], fill=OL, width=lw); d.ellipse((h[0] - 9 * s, h[1] - 9 * s, h[0] + 9 * s, h[1] + 9 * s), fill=OL)
    hx, hy = U(0, shy - 112 + 5 * a)
    rot = math.radians(3 * math.sin(1.1 * t + ph) + g * 4 * math.sin(2.3 * t + ph)); cs, sn = math.cos(rot), math.sin(rot)
    HP = lambda dx, dy: (hx + (dx * cs - dy * sn) * s, hy + (dx * sn + dy * cs) * s)
    if style == 'long': d.rounded_rectangle((hx - 126 * s, hy - 100 * s, hx + 126 * s, hy + 120 * s), radius=70 * s, fill=hairc, outline=OL, width=lw)
    d.ellipse((hx - 118 * s, hy - 118 * s, hx + 118 * s, hy + 118 * s), fill=GREY)
    d.ellipse((hx - 14 * s - 102 * s, hy - 8 * s - 102 * s, hx - 14 * s + 102 * s, hy - 8 * s + 102 * s), fill='white')
    d.ellipse((hx - 118 * s, hy - 118 * s, hx + 118 * s, hy + 118 * s), outline=OL, width=lw)
    if style == 'helmet':
        d.pieslice((hx - 128 * s, hy - 128 * s, hx + 128 * s, hy + 40 * s), 180, 360, fill='#f2c200')
        d.arc((hx - 128 * s, hy - 128 * s, hx + 128 * s, hy + 40 * s), 180, 360, fill=OL, width=lw)
        d.rounded_rectangle((hx - 136 * s, hy - 50 * s, hx + 136 * s, hy - 30 * s), radius=8 * s, fill='#f2c200', outline=OL, width=lw)
        d.line([(hx, hy - 128 * s), (hx, hy - 52 * s)], fill='#fff3a0', width=8 * s)
        d.ellipse((hx - 18 * s, hy - 112 * s, hx + 18 * s, hy - 82 * s), fill='#fff6b0', outline=OL, width=lw * .8)
    elif style != 'bald':
        c = '#9a9a9a' if style == 'cap' else hairc
        d.pieslice((hx - 122 * s, hy - 122 * s, hx + 122 * s, hy + 50 * s), 180, 360, fill=c)
        d.arc((hx - 122 * s, hy - 122 * s, hx + 122 * s, hy + 50 * s), 180, 360, fill=OL, width=lw)
        if style == 'bun': d.ellipse((hx - 36 * s, hy - 168 * s, hx + 36 * s, hy - 100 * s), fill=hairc, outline=OL, width=lw)
        elif style == 'cap': d.rounded_rectangle((hx - 10 * s, hy - 40 * s, hx + 160 * s, hy - 14 * s), radius=12 * s, fill='#b5b5b5', outline=OL, width=lw)
        else: d.line([(hx - 30 * s, hy - 118 * s), (hx + 12 * s, hy - 62 * s)], fill='white', width=3.5 * s)
    tilt, lift, es, smile = A['emo']
    for sd in (-1, 1):
        ex, ey = HP(sd * 42, 8)
        if smile > .6: d.arc((ex - 17 * s, ey - 10 * s, ex + 17 * s, ey + 10 * s), 20, 160, fill=OL, width=lw)
        elif A['blink'] > .6: d.line([(ex - 14 * s, ey), (ex + 14 * s, ey)], fill=OL, width=lw)
        else: hh = 15 * es * s * (1 - .7 * A['blink']); d.line([(ex, ey - hh), (ex, ey + hh)], fill=OL, width=lw)
        if abs(tilt) > .25 or lift > 8:
            inner = HP(sd * 20, -24 + tilt * 8 - lift * .5); outer = HP(sd * 58, -30 - tilt * 8 - lift * .5)
            d.line([inner, outer], fill=OL, width=lw * .9)
        if look.get('glasses'): d.rectangle((ex - 27 * s, ey - 21 * s, ex + 27 * s, ey + 21 * s), outline=OL, width=lw * .8)
    if look.get('glasses'): d.line([HP(-15, 8), HP(15, 8)], fill=OL, width=lw * .8)
    mx, my = HP(0, 68)
    if a > .05:
        w = 11 + 12 * a; h = 6 + 32 * a
        d.ellipse((mx - w * s, my - 4 * s, mx + w * s, my - 4 * s + h * s), fill='#222222', outline=OL, width=lw * .7)
    elif abs(smile) < .2: d.line([HP(-14, 68), HP(14, 68)], fill=OL, width=lw)
    elif smile > 0: d.arc((mx - 22 * s, my - 14 * s, mx + 22 * s, my + 8 * s), 20, 160, fill=OL, width=lw)
    else: d.arc((mx - 20 * s, my + 4 * s, mx + 20 * s, my + 28 * s), 200, 340, fill=OL, width=lw)

def draw_bg_sketch(d, setting):
    d.rectangle((-300, -300, W + 300, H + 300), fill='white')
    d.line((-300, 830, W + 300, 830), fill='#c4c4c4', width=3)
    if setting in ('opisina', 'bahay', 'kwarto', 'kusina', 'cafe'):
        d.rectangle((70, 330, 250, 500), outline='#d2d2d2', width=3); d.line((160, 330, 160, 500), fill='#d2d2d2', width=2); d.line((70, 415, 250, 415), fill='#d2d2d2', width=2)
    elif setting == 'paaralan': d.rectangle((70, 320, 650, 560), outline='#d2d2d2', width=4)
    elif setting == 'kalye':
        for x, h in ((40, 380), (260, 520), (480, 300)): d.rectangle((x, 830 - h, x + 190, 830), fill='#ececec', outline='#9a9a9a', width=3)
    elif setting == 'parke':
        d.rectangle((420, 700, 690, 730), fill='#cfcfcf', outline=OL, width=4); d.line((440, 730, 440, 830), fill=OL, width=4); d.line((670, 730, 670, 830), fill=OL, width=4)


# ======================= story style: rich scenery for narrated "did you know" / true stories =======================
import re as _re
def _hex(c):
    c = c.lstrip('#'); return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))

def _grad(d, y0, y1, c0, c1, steps=26):
    a, b = _hex(c0), _hex(c1); h = (y1 - y0) / steps
    for i in range(steps):
        f = i / (steps - 1); d.rectangle((-300, y0 + i * h, W + 300, y0 + (i + 1) * h + 1), fill=tuple(int(a[k] + (b[k] - a[k]) * f) for k in range(3)))

THEMES = {'mine': ('#1b130d', '#4a3220', '#3a2817'), 'cave': ('#0e1d28', '#244557', '#2a3b45'), 'desert': ('#7ec8f2', '#f6e2b3', '#d9a95b'),
          'mountain': ('#7aa9d6', '#dbe8f5', '#e8eef2'), 'snow': ('#c4d3e3', '#f4f7fa', '#ffffff'), 'ocean': ('#6bb6ea', '#cfe9f8', '#2e78b7'),
          'forest': ('#9fd6f0', '#e5f4d8', '#4f9a4a'), 'city': ('#7db7e8', '#ecdcc6', '#6b7280'), 'indoor': ('#efe5d6', '#efe5d6', '#a67c52'),
          'night': ('#0b1230', '#27386b', '#1b2a2f'), 'sky': ('#4a90d9', '#d6ecfb', '#cfe8fb')}
KEYS = [('mine', 'mine'), ('tunnel', 'mine'), ('underground', 'mine'), ('cave', 'cave'), ('desert', 'desert'), ('mountain', 'mountain'), ('everest', 'mountain'),
        ('alps', 'mountain'), ('summit', 'mountain'), ('cliff', 'mountain'), ('snow', 'snow'), ('ice', 'snow'), ('arctic', 'snow'), ('glacier', 'snow'), ('winter', 'snow'),
        ('sea', 'ocean'), ('ocean', 'ocean'), ('boat', 'ocean'), ('ship', 'ocean'), ('raft', 'ocean'), ('island', 'ocean'), ('beach', 'ocean'), ('river', 'ocean'), ('lake', 'ocean'),
        ('forest', 'forest'), ('jungle', 'forest'), ('wood', 'forest'), ('farm', 'forest'), ('field', 'forest'), ('city', 'city'), ('street', 'city'), ('town', 'city'),
        ('village', 'city'), ('ruin', 'city'), ('building', 'city'), ('hospital', 'indoor'), ('house', 'indoor'), ('home', 'indoor'), ('room', 'indoor'), ('office', 'indoor'),
        ('lab', 'indoor'), ('control', 'indoor'), ('indoor', 'indoor'), ('night', 'night'), ('space', 'night'), ('moon', 'night'), ('plane', 'sky'), ('sky', 'sky'),
        ('desert', 'desert'), ('rescue', 'desert'), ('surface', 'desert')]

def story_theme(s):
    s = (s or '').lower()
    for k, v in KEYS:
        if _re.search(r'\b' + k, s): return v
    return 'city'

def draw_bg_story(d, theme):
    top, bot, floor = THEMES.get(theme, THEMES['city'])
    _grad(d, -300, 830, top, bot)
    d.rectangle((-300, 830, W + 300, H + 300), fill=floor)
    rnd = random.Random(theme)
    if theme == 'mine':
        d.polygon([(-300, -300), (130, -300), (70, 250), (150, 560), (60, 830), (-300, 830)], fill='#241810')
        d.polygon([(W + 300, -300), (590, -300), (650, 250), (570, 560), (660, 830), (W + 300, 830)], fill='#241810')
        d.ellipse((230, 330, 490, 830), fill='#100a06'); d.ellipse((300, 470, 420, 700), fill='#6b4a2b')
        for x in (150, 570):
            for y in (200, 420, 640): d.ellipse((x - 16, y - 16, x + 16, y + 16), fill='#ffd66b'); d.ellipse((x - 7, y - 7, x + 7, y + 7), fill='#fff3c4')
        for y in (120, 360): d.rectangle((-300, y, W + 300, y + 22), fill='#5a3d22', outline='#2b1b0e', width=4)
    elif theme == 'cave':
        for x in range(-40, W + 60, 80): hgt = 120 + rnd.randint(0, 170); d.polygon([(x, -300), (x + 70, -300), (x + 35, hgt)], fill='#16303f', outline='#0a1a24', width=3)
        for x in range(0, W, 110): hgt = 60 + rnd.randint(0, 120); d.polygon([(x, 830), (x + 80, 830), (x + 40, 830 - hgt)], fill='#33505f', outline='#0a1a24', width=3)
        d.ellipse((460, 260, 640, 440), fill='#2f6f8f')
    elif theme == 'desert':
        d.ellipse((520, 90, 640, 210), fill='#fff0a8'); d.polygon([(-300, 830), (80, 690), (460, 830)], fill='#e8c27c'); d.polygon([(250, 830), (560, 640), (1000, 830)], fill='#dfb468')
    elif theme == 'mountain':
        d.polygon([(-120, 830), (240, 330), (620, 830)], fill='#7d8fa3', outline='#51606f', width=4); d.polygon([(240, 330), (170, 470), (240, 430), (300, 490), (330, 420)], fill='white')
        d.polygon([(330, 830), (560, 450), (900, 830)], fill='#92a3b5', outline='#51606f', width=4); d.polygon([(560, 450), (510, 540), (560, 510), (610, 550)], fill='white')
    elif theme == 'snow':
        d.polygon([(-100, 830), (250, 430), (600, 830)], fill='#dbe6f0', outline='#a9bccd', width=4)
        for _ in range(60): x, y = rnd.randint(0, W), rnd.randint(0, 800); d.ellipse((x - 4, y - 4, x + 4, y + 4), fill='white')
    elif theme == 'ocean':
        d.rectangle((-300, 700, W + 300, H + 300), fill='#2e78b7')
        for y in range(730, 1100, 55):
            for x in range(-40, W + 60, 120): d.arc((x, y, x + 100, y + 36), 200, 340, fill='#7fc0ee', width=4)
        d.rectangle((20, 1095, 700, 1200), fill='#8a5a3c', outline=OL, width=5); d.line((20, 1130, 700, 1130), fill='#5e3b25', width=4)
        d.ellipse((540, 90, 660, 210), fill='#fff0a8')
    elif theme == 'forest':
        for i, x in enumerate(range(20, W + 80, 120)):
            hgt = 260 + (i * 53) % 140; d.rectangle((x - 14, 830 - hgt, x + 14, 830), fill='#6b4a2b', outline='#3d2a16', width=4); d.ellipse((x - 80, 830 - hgt - 110, x + 80, 830 - hgt + 70), fill='#2f7d3a', outline='#1d4f25', width=4)
    elif theme == 'city':
        for x, h, c in ((10, 460, '#cfd8e3'), (190, 600, '#aebccd'), (380, 400, '#d9c7b0'), (560, 520, '#b9c4d1')):
            d.rectangle((x, 830 - h, x + 170, 830), fill=c, outline='#6b7280', width=4)
            for yy in range(830 - h + 30, 790, 70):
                for xx in (x + 24, x + 96): d.rectangle((xx, yy, xx + 40, yy + 34), fill='#f6f0c4', outline='#6b7280', width=3)
        d.line((-300, 960, W + 300, 960), fill='#9aa3ad', width=6)
    elif theme == 'indoor':
        d.rectangle((70, 210, 300, 470), fill='#cfeeff', outline='#7a6a58', width=8); d.line((185, 210, 185, 470), fill='#7a6a58', width=6); d.line((70, 340, 300, 340), fill='#7a6a58', width=6)
        d.rectangle((470, 230, 640, 380), fill='white', outline='#7a6a58', width=6); d.ellipse((510, 255, 600, 355), fill='#9cc3e8')
        d.line((-300, 830, W + 300, 830), fill='#7a6a58', width=8)
    elif theme == 'night':
        for _ in range(90): x, y = rnd.randint(0, W), rnd.randint(0, 800); d.ellipse((x - 3, y - 3, x + 3, y + 3), fill='#e8efff')
        d.ellipse((500, 110, 620, 230), fill='#f5f0d0')
    elif theme == 'sky':
        for x, y in ((90, 220), (430, 140), (300, 520), (560, 640)): d.ellipse((x, y, x + 190, y + 70), fill='white'); d.ellipse((x + 40, y - 30, x + 150, y + 40), fill='white')

def draw_crowd(d, n, cx, gy, s, t, seed='crowd'):
    rnd = random.Random(seed); n = min(n, 14); cols = (n + 1) // 2 if n > 6 else n; rows = [(gy - 150, n - cols), (gy, cols)] if n > 6 else [(gy, n)]
    k = 0
    for y, cnt in rows:
        for i in range(cnt):
            x = cx + (i - (cnt - 1) / 2) * (92 if n <= 6 else 80) + (rnd.random() - .5) * 10
            look = dict(skin='#ffffff', hair=rnd.choice(['#2e1f16', '#1b1b22', '#4a2e1f']), shirt='#f97316', style='helmet', glasses=False, tie=False, scale=1.0)
            draw_char_sketch(d, look, x, y, s, dict(t=t, g=0, a=0, ph=rnd.random() * 6, bob=0, emo=EMO['neutral'], blink=0, gaze=0, arm_side=1, colored=True)); k += 1
