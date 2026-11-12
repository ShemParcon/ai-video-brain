import random, functools, json
from PIL import Image, ImageDraw

W, H = 720, 1280
OL = (35, 35, 45)
SKINS = ['#f6d1a7', '#e8b98a', '#d29b6b', '#b9784a', '#8d5a3b']
HAIRS = ['#1b1b22', '#2e1f16', '#4a2e1f', '#1f2a44', '#6b2d1a']
SHIRTS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#14b8a6', '#ec4899', '#64748b', '#f97316']
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
    reg[key] = dict(v=3, page=page, role=role, gender=gender, age=age, look=look, voice=voice,
                    pitch=-6 if age == 'old' else 0, rate={'kid': 4, 'old': -4}.get(age, r.randint(2, 8)))
    return reg[key]

class SD:
    def __init__(s, d, k): s.d, s.k = d, k
    def _s(s, v):
        return [(x * s.k, y * s.k) for x, y in v] if isinstance(v[0], (tuple, list)) else [x * s.k for x in v]
    def _w(s, w): return max(1, int(w * s.k))
    def ellipse(s, box, fill=None, outline=None, width=1): s.d.ellipse(s._s(box), fill=fill, outline=outline, width=s._w(width))
    def rectangle(s, box, fill=None, outline=None, width=1): s.d.rectangle(s._s(box), fill=fill, outline=outline, width=s._w(width))
    def rounded_rectangle(s, box, radius=0, fill=None, outline=None, width=1): s.d.rounded_rectangle(s._s(box), radius=radius * s.k, fill=fill, outline=outline, width=s._w(width))
    def polygon(s, pts, fill=None, outline=None): s.d.polygon(s._s(pts), fill=fill, outline=outline, width=s.k)
    def line(s, pts, fill=None, width=1, joint=None): s.d.line(s._s(pts), fill=fill, width=s._w(width), joint=joint)
    def arc(s, box, start, end, fill=None, width=1): s.d.arc(s._s(box), start, end, fill=fill, width=s._w(width))
    def pieslice(s, box, start, end, fill=None, outline=None, width=1): s.d.pieslice(s._s(box), start, end, fill=fill, outline=outline, width=s._w(width))

def _draw(look, mouth, emo, blink, pose=0):
    im = Image.new('RGBA', (1200, 2360), (0, 0, 0, 0)); d = SD(ImageDraw.Draw(im), 2)
    skin, hair, shirt, style = look['skin'], look['hair'], look['shirt'], look['style']; w = 9
    pants = look.get('pants', '#334155'); shoe = look.get('shoe', '#1f2937'); skirt = look.get('skirt', False)
    d.ellipse((120, 1110, 480, 1160), fill=(0, 0, 0, 45))
    if style == 'long': d.rounded_rectangle((115, 190, 485, 720), radius=120, fill=hair, outline=OL, width=w)
    if skirt:
        for x0 in (205, 315): d.rectangle((x0, 960, x0 + 80, 1100), fill=skin, outline=OL, width=w)
    else:
        for x0 in (195, 315): d.rounded_rectangle((x0, 850, x0 + 90, 1100), radius=30, fill=pants, outline=OL, width=w)
    for x0 in (165, 305): d.ellipse((x0, 1065, x0 + 130, 1135), fill=shoe, outline=OL, width=w)
    d.rectangle((255, 450, 345, 600), fill=skin, outline=OL, width=w)
    d.rounded_rectangle((140, 570, 460, 890), radius=80, fill=shirt, outline=OL, width=w)
    if skirt: d.polygon([(150, 860), (450, 860), (490, 1000), (110, 1000)], fill=look.get('skirtc', pants), outline=OL)
    d.polygon([(262, 572), (338, 572), (300, 640)], fill=skin, outline=OL)
    if look.get('tie'): d.polygon([(288, 600), (312, 600), (322, 700), (300, 735), (278, 700)], fill='#b3202a', outline=OL)
    def arm(pts):
        d.line(pts, fill=OL, width=66, joint='curve'); d.line(pts, fill=shirt, width=48, joint='curve')
        x, y = pts[-1]; d.ellipse((x - 34, y - 34, x + 34, y + 34), fill=skin, outline=OL, width=w)
    arm([(150, 625), (105, 740), (98, 840)] if pose != 2 else [(150, 625), (80, 700), (80, 540)])
    arm([(450, 625), (495, 740), (502, 840)] if pose != 1 else [(450, 625), (520, 700), (520, 540)])
    for x0 in (122, 428): d.ellipse((x0, 320, x0 + 50, 395), fill=skin, outline=OL, width=w)
    d.ellipse((150, 170, 450, 500), fill=skin, outline=OL, width=w)
    if style != 'bald':
        c = look['cap'] if style == 'cap' else hair
        d.pieslice((138, 150, 462, 440), 180, 360, fill=c); d.arc((138, 150, 462, 440), 180, 360, fill=OL, width=w)
        if style == 'bun': d.ellipse((250, 85, 350, 175), fill=hair, outline=OL, width=w)
        if style == 'cap': d.rounded_rectangle((300, 268, 500, 302), radius=16, fill=c, outline=OL, width=w)
    for cx in (240, 360):
        if emo == 'happy': d.arc((cx - 28, 335, cx + 28, 380), 200, 340, fill=OL, width=9)
        elif blink: d.line((cx - 26, 352, cx + 26, 352), fill=OL, width=8)
        else:
            rw, rh = (34, 42) if emo == 'surprised' else (28, 34)
            d.ellipse((cx - rw, 350 - rh, cx + rw, 350 + rh), fill='white', outline=OL, width=6)
            pr = 8 if emo == 'surprised' else 13
            d.ellipse((cx - pr, 350 - pr * 1.2, cx + pr, 350 + pr * 1.2), fill=OL)
            d.ellipse((cx - 5, 340, cx + 3, 348), fill='white')
    if emo == 'angry': d.line((200, 308, 272, 335), fill=OL, width=10); d.line((400, 308, 328, 335), fill=OL, width=10)
    elif emo == 'sad': d.line((205, 335, 272, 308), fill=OL, width=10); d.line((395, 335, 328, 308), fill=OL, width=10)
    elif emo == 'surprised': d.line((210, 290, 270, 285), fill=OL, width=9); d.line((390, 290, 330, 285), fill=OL, width=9)
    else: d.line((210, 312, 268, 306), fill=OL, width=9); d.line((390, 312, 332, 306), fill=OL, width=9)
    d.ellipse((182, 398, 228, 424), fill='#f4a6a0'); d.ellipse((372, 398, 418, 424), fill='#f4a6a0')
    if mouth == 'closed':
        if emo == 'happy': d.arc((255, 410, 345, 465), 20, 160, fill=OL, width=9)
        elif emo == 'sad': d.arc((265, 445, 335, 485), 200, 340, fill=OL, width=9)
        else: d.line((272, 442, 328, 442), fill=OL, width=9)
    else:
        box = {'small': (278, 425, 322, 458), 'open': (264, 420, 336, 478), 'wide': (250, 414, 350, 492)}[mouth]
        d.ellipse(box, fill='#7a1f2b', outline=OL, width=7)
        if mouth != 'small': d.ellipse((box[0] + 16, box[3] - 24, box[2] - 16, box[3] - 6), fill='#e8707a')
    if look.get('glasses'):
        for cx in (240, 360): d.ellipse((cx - 46, 304, cx + 46, 396), outline=OL, width=6)
        d.line((286, 350, 314, 350), fill=OL, width=6)
    return im

@functools.lru_cache(maxsize=160)
def sprite(look_json, mouth, emo, blink, pose, w, h):
    return _draw(json.loads(look_json), mouth, emo, blink, pose).resize((w, h), Image.LANCZOS)

SETTINGS = {'opisina': ('#dbe7f3', '#8d99a6'), 'bahay': ('#fde8c8', '#b98b5e'), 'kusina': ('#e9f5e1', '#c9b28a'),
            'kwarto': ('#e6dcf5', '#a58bc9'), 'paaralan': ('#f7f1cf', '#9c8456'), 'kalye': ('#bfe3f7', '#6b7280'),
            'palengke': ('#ffe3d6', '#a8825a'), 'simbahan': ('#f3efe6', '#8b7355'), 'cafe': ('#f1e0d0', '#7a5a42'),
            'parke': ('#c7ecff', '#6abf69')}
ALIAS = {'office': 'opisina', 'home': 'bahay', 'sala': 'bahay', 'kitchen': 'kusina', 'bedroom': 'kwarto', 'school': 'paaralan',
         'classroom': 'paaralan', 'street': 'kalye', 'labas': 'kalye', 'market': 'palengke', 'tindahan': 'palengke',
         'church': 'simbahan', 'park': 'parke', 'coffee': 'cafe', 'restaurant': 'cafe'}

def norm_setting(s):
    s = (s or '').lower()
    for k in SETTINGS:
        if k in s: return k
    for k, v in ALIAS.items():
        if k in s: return v
    return 'bahay'

def make_bg(setting):
    wall, floor = SETTINGS.get(setting, SETTINGS['bahay'])
    im = Image.new('RGB', (W, H), wall); d = ImageDraw.Draw(im)
    d.rectangle((0, 830, W, H), fill=floor); d.line((0, 830, W, 830), fill=OL, width=6)
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
    return im
