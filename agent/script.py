"""Turns a pasted joke (title + conversation) into a script. No AI needed."""
import re

EMO = {"happy", "angry", "sad", "surprised", "neutral"}
SFX = {"rimshot", "laugh", "ding", "bonk", "pop", "whoosh", "trombone"}
FEM = {"mom", "mother", "mama", "mum", "girl", "daughter", "sister", "grandma", "grandmother", "lady", "woman", "wife", "girlfriend", "aunt", "nana", "granny", "waitress", "she"}
KID = {"kid", "child", "son", "daughter", "boy", "girl", "baby", "little", "junior", "sis", "bro"}
OLD = {"grandma", "grandpa", "grandmother", "grandfather", "old", "elder", "nana", "granny", "grandad"}
META = re.compile(r"^\s*(title|setting|scene|location|style|caption|hashtags|tags)\s*[:：]\s*(.*)$", re.I)
LINE = re.compile(r"^\s*(?:[-•*]\s*)?([^:：\[\]()]{1,30}?)\s*(?:[\[(]([^\])]*)[\])])?\s*[:：]\s*(.+?)\s*$")
TAGGROUP = re.compile(r"(\s*[\[(][A-Za-z ,]+[\])])+\s*$")

def guess(role):
    w = set(re.findall(r"[a-z]+", role.lower()))
    gender = "F" if w & FEM else "M"
    age = "old" if w & OLD else ("kid" if w & KID else "adult")
    return gender, age

def _tags(s):
    return [t.strip().lower() for t in re.split(r"[,\s]+", s or "") if t.strip()]

def split_jokes(text):
    blocks, cur = [], []
    for ln in (text or "").replace("\r", "").split("\n"):
        if re.match(r"^\s*(-{3,}|={3,}|_{3,})\s*$", ln):
            if any(x.strip() for x in cur): blocks.append("\n".join(cur))
            cur = []
        else: cur.append(ln)
    if any(x.strip() for x in cur): blocks.append("\n".join(cur))
    return blocks

def parse_joke(text, cfg=None):
    cfg = cfg or {}
    meta, raw = {}, []
    for ln in (text or "").replace("\r", "").split("\n"):
        ln = ln.strip().strip('"“”')
        if not ln: continue
        m = META.match(ln)
        if m: meta[m.group(1).lower()] = m.group(2).strip(); continue
        raw.append(ln)
    parsed = []
    for ln in raw:
        m = LINE.match(ln); parsed.append(m.groups() if m else None)
    roles_count = {}
    for g in parsed:
        if g: roles_count[g[0].strip().lower()] = roles_count.get(g[0].strip().lower(), 0) + 1
    title = meta.get("title", "")
    items = []   # [role, tagtext, text]
    for i, (ln, g) in enumerate(zip(raw, parsed)):
        if i == 0 and not title:
            is_title = g is None or (roles_count.get(g[0].strip().lower(), 0) == 1 and sum(roles_count.values()) >= 3)
            if is_title: title = ln; continue
        if g is None:
            if items: items[-1][2] += " " + ln
            elif not title: title = ln
            continue
        items.append([g[0].strip(), g[1], g[2]])
    # roles in order of appearance, max 3
    order = []
    for r, _, _ in items:
        if r.lower() not in [x.lower() for x in order]: order.append(r)
    warnings = []
    if len(order) > 3: warnings.append(f"More than 3 speakers; only {', '.join(order[:3])} are used."); order = order[:3]
    keep = [r.lower() for r in order]
    lines = []
    for r, tg, tx in items:
        if r.lower() not in keep: continue
        emo = sfx = None
        for t in _tags(tg):
            if t in EMO: emo = t
            elif t in SFX: sfx = t
        m = TAGGROUP.search(tx)
        if m:
            for t in _tags(re.sub(r"[\[\]()]", " ", m.group(0))):
                if t in EMO: emo = t
                elif t in SFX: sfx = t
            tx = tx[:m.start()]
        tx = re.sub(r"\[[^\]]*\]|\([^)]*\)", "", tx)
        tx = re.sub(r"\s+", " ", tx).strip()
        if tx: lines.append({"who": next(x for x in order if x.lower() == r.lower()), "text": tx, "emotion": emo, "sfx": sfx})
    if not lines: raise ValueError("No dialogue found. Write lines like  Dad: your line")
    first = order[0]
    punch = max([i for i, l in enumerate(lines) if l["who"] == first] or [len(lines) - 1])
    have_sfx = any(l["sfx"] for l in lines)
    for i, l in enumerate(lines):
        if l["sfx"] == "trombone": l["sfx"] = "sad"
        if not l["emotion"]:
            low = l["text"].lower()
            if i == punch and l["who"] == first: l["emotion"] = "happy"
            elif i == len(lines) - 1 and i != punch:
                l["emotion"] = "sad" if re.search(r"\b(no|stop|dad|please|ugh|seriously|why|really|oh my|groan)\b", low) else ("happy" if re.search(r"\b(ha|haha|lol|funny|good one)\b", low) else "surprised")
            elif i == 0 and l["who"] == first: l["emotion"] = "happy"
            else: l["emotion"] = "surprised" if l["text"].endswith("!") else "neutral"
    if not have_sfx and len(lines) >= 2: lines[punch]["sfx"] = "rimshot"
    if not title: title = lines[0]["text"][:50]
    title = title.strip()
    chars = []
    for r in order:
        g, a = guess(r); chars.append({"role": r, "gender": g, "age": a})
    tags = meta.get("hashtags") or meta.get("tags") or ""
    hashtags = [("#" + t.lstrip("#")) for t in re.split(r"[,\s]+", tags) if t.strip("#")] or list(cfg.get("hashtags") or ["#dadjokes", "#funny", "#jokes", "#comedy"])
    caption = meta.get("caption") or (title + " 😂\n" + (cfg.get("cta") or "Did this one make you groan?"))
    return {"title": title, "characters": chars, "warnings": warnings, "style": (meta.get("style") or "").lower() or None,
            "scenes": [{"setting": meta.get("setting") or meta.get("scene") or meta.get("location") or "home", "lines": lines}],
            "hook": title if len(title) <= 34 else title[:32].rsplit(" ", 1)[0] + "…", "caption": caption, "hashtags": hashtags, "youtube_title": title[:90]}
