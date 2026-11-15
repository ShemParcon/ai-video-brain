import argparse, datetime, json, os, subprocess, sys, traceback
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from common import *
import art, audio, render, plan as planner

SFX = {"pop", "ding", "whoosh", "bonk", "sad", "laugh", "rimshot"}
EMOS = {"neutral", "happy", "angry", "sad", "surprised"}

def gen_script(item, page, cfg):
    if os.getenv("DRY_SCRIPT"): return load(os.getenv("DRY_SCRIPT"))
    prompt = """Write a short viral joke skit for a vertical cartoon video. Total spoken time 14 to 24 seconds: 5 to 9 short lines (max 12 words each), 1 to 3 characters.
Language: __LANG__.
Page: __PAGE__ (__NICHE__). Style guide: __GUIDE__. Joke title: __TITLE__. The joke or idea: __PREMISE__. Roles to use: __ROLES__.
The first line is the hook and must grab attention immediately. Build the setup fast and deliver the punchline in the final lines. You may add one short reaction line after the punchline (a groan, a laugh, or Dad stop). Keep it clean and wholesome: no real people, brands, copyrighted characters or lines from copyrighted comedy, no weapons, no violence, nothing harmful or sexual.
Write every line exactly as a text-to-speech voice should read it: plain words, NO hyphenated words, NO acronyms, NO emojis or symbols, numbers written in words, normal spelling.
Allowed settings: office, home, kitchen, bedroom, school, street, market, church, cafe, park.
Allowed emotions: neutral, happy, angry, sad, surprised. Allowed sfx (or null): pop, ding, whoosh, bonk, sad, laugh, rimshot (use rimshot right after the punchline).
Return ONLY JSON:
{"characters":[{"role":"Dad","gender":"M","age":"adult"}],"scenes":[{"setting":"kitchen","lines":[{"who":"Dad","text":"...","emotion":"happy","sfx":null}]}],"youtube_title":"max 70 chars","hook":"on-screen hook, max 5 words","caption":"1-2 funny sentences with emojis ending with a question for comments","hashtags":["#dadjokes","#tag2","#tag3","#tag4","#tag5","#tag6","#tag7","#tag8"]}
gender is M or F; age is kid, adult, or old.""".replace("__LANG__", cfg.get("language", "Filipino")).replace("__PAGE__", page["name"]) \
        .replace("__NICHE__", page["niche"]).replace("__GUIDE__", page.get("guide") or "natural, punchy and funny").replace("__TITLE__", item["title"]).replace("__PREMISE__", item["premise"]) \
        .replace("__ROLES__", ", ".join(item.get("roles", [])) or "your choice")
    return llm_json(prompt)

def posts(sc, item):
    tags = [("#" + t.lstrip("#")).replace(" ", "") for t in sc.get("hashtags", [])]
    tags = [t for t in dict.fromkeys(tags) if t.lower() not in ("#shorts", "#fyp", "#foryou")][:8]
    cap = (sc.get("caption") or item["title"]).strip()
    yt_title = (sc.get("youtube_title") or item["title"])[:90]
    return {"yt_title": yt_title, "yt_desc": f"{cap}\n\n{' '.join(tags[:6])} #shorts",
            "tiktok": f"{cap}\n\n{' '.join(tags[:5])} #fyp #foryou", "facebook": f"{cap}\n\n{' '.join(tags[:4])}"}

NARRATOR = "en-US-ChristopherNeural"

def gen_story_script(item, page, cfg):
    if os.getenv("DRY_SCRIPT"): return load(os.getenv("DRY_SCRIPT"))
    target = int(page.get("target_seconds") or 60); words = int(target * 2.3); n = max(5, round(target / 7))
    facts = "\n".join("- " + f for f in item.get("facts", [])) or "(use only very well documented facts)"
    prompt = """You are the scriptwriter for a narrated explainer video told with simple stick figure animation.
Topic: __TITLE__ (__KIND__, __COUNTRY__). Summary: __PREMISE__.
Verified facts you may use:
__FACTS__
Write a voice-over of about __WORDS__ words (about __TARGET__ seconds) split into __N__ scenes of 1 to 3 short sentences each.
Rules: use ONLY the verified facts above and other very well documented details. Do NOT invent names, numbers, dates, quotes or dialogue. If unsure, leave it out or say about. Tell it as a gripping story: open with a hook sentence (a surprising fact or a question), build tension step by step with concrete numbers, reach the turning point, end with the outcome and one memorable closing line. Respectful tone, nothing graphic. For trivia videos give 4 to 6 facts, each with a concrete number or detail, saving the most surprising for last. Write for text to speech: plain words, no hyphenated words, no acronyms, no symbols, numbers written the way a person would say them.
For each scene choose: setting (one of: mine, cave, desert, mountain, snow, ocean, forest, city, indoor, night, sky), 0 to 3 characters (a role such as Miner, Rescuer, President, Doctor, Hiker) with an emotion (neutral, happy, angry, sad, surprised), an optional label (short on-screen text with a key number or date, max 4 words, like DAY 17 or 33 MEN or 700 METERS DEEP), and an optional crowd (number of extra people, 0 to 14).
Language: __LANG__.
Return ONLY JSON:
{"scenes":[{"setting":"mine","narration":"...","characters":[{"role":"Miner","gender":"M","age":"adult","emotion":"sad"}],"label":"DAY 1","crowd":0}],"youtube_title":"max 70 chars","caption":"2 short sentences with emojis ending with a question for comments","hashtags":["#didyouknow","#truestory","#tag3","#tag4","#tag5","#tag6","#tag7","#tag8"]}"""
    for k, v in (("__TITLE__", item["title"]), ("__KIND__", item.get("kind", "story")), ("__COUNTRY__", item.get("country", "")), ("__PREMISE__", item["premise"]),
                 ("__FACTS__", facts), ("__WORDS__", str(words)), ("__TARGET__", str(target)), ("__N__", str(n)), ("__LANG__", cfg.get("language", "English"))):
        prompt = prompt.replace(k, v)
    return llm_json(prompt)

def word_times(text, start, dur):
    ws = audio.clean(text).split() or ["..."]
    wt = [len(w) + (6 if w[-1:] in ",;:" else 0) + (10 if w[-1:] in ".?!" else 0) for w in ws]; tot = sum(wt); acc = 0; out = []
    for w, x in zip(ws, wt): out.append((w, start + dur * acc / tot, start + dur * (acc + x) / tot)); acc += x
    return out

def build_story(item, page, cfg, reg, st, date, res):
    id = item["id"]
    def stage(state, pct, msg=""): set_item(st, id, state=state, pct=pct, msg=msg, date=date); git_push(f"{state} {id}")
    stage("scripting", 10)
    sc = gen_story_script(item, page, cfg)
    stage("voicing", 35)
    os.makedirs(p("out", "tmp"), exist_ok=True)
    narr = dict(voice=cfg.get("narrator_voice", NARRATOR), pitch=0, rate=-2, gender="M")
    scenes, t = [], 0.0; maxt = min(175, int(page.get("target_seconds") or 60) * 1.5 + 10)
    for i, s in enumerate(sc.get("scenes", [])):
        text = str(s.get("narration", "")).strip()
        if not text: continue
        a = audio.tts(text, narr, p("out", "tmp", f"{id}_{i}")); dur = len(a) / audio.SR
        if t + dur > maxt and len(scenes) >= 4: break
        vs = t + .3; t1 = vs + dur + .4; roles = []
        for c in (s.get("characters") or [])[:3]:
            role = str(c.get("role", "")).strip()
            if not role: continue
            ch = art.get_char(reg, page["id"], role, c.get("gender", "M"), c.get("age", "adult"))
            roles.append({"role": role, "look": ch["look"], "emotion": c.get("emotion") if c.get("emotion") in EMOS else "neutral"})
        try: crowd = max(0, min(14, int(s.get("crowd") or 0)))
        except Exception: crowd = 0
        scenes.append(dict(theme=art.story_theme(s.get("setting")), roles=roles, label=str(s.get("label") or "")[:28], crowd=crowd, t0=t, t1=t1,
                           words=word_times(text, vs, dur), audio=a, vstart=vs, cam=i))
        t = t1
    if not scenes: raise RuntimeError("empty script")
    total = t + 2.4
    stage("rendering", 60)
    wav = p("out", "tmp", f"{id}.wav")
    audio.mix(total, [dict(start=x["vstart"], audio=x["audio"], sfx="ding" if x["label"] else None) for x in scenes], wav, mood="pad")
    mp4 = p("out", f"{id}.mp4"); render.render_story(scenes, total, wav, mp4, page_name=page["name"])
    stage("uploading", 90)
    url = upload(date, mp4)
    res["items"][id] = dict(page=page["id"], title=item["title"], url=url, duration=round(total, 1), **posts(sc, item))
    save(p("data", "results", f"{date}.json"), res)
    set_item(st, id, state="done", pct=100, msg="", built_rev=item.get("rev", 0), date=date)
    hist = load(p("data", "history.json"), []); hist.append(item["title"]); save(p("data", "history.json"), hist[-200:])

def upload(date, path):
    if not os.getenv("GITHUB_ACTIONS"): return path
    tag = f"videos-{date}"; run = lambda *a: subprocess.run(a, capture_output=True, text=True)
    run("gh", "release", "create", tag, "--title", f"Videos {date}", "--notes", "AI generated videos")
    r = run("gh", "release", "upload", tag, path, "--clobber")
    if r.returncode: raise RuntimeError("upload failed: " + r.stderr[:200])
    return f"https://github.com/{os.environ['GITHUB_REPOSITORY']}/releases/download/{tag}/{os.path.basename(path)}"

def build(item, page, cfg, reg, st, date, res):
    id = item["id"]
    def stage(state, pct, msg=""): set_item(st, id, state=state, pct=pct, msg=msg, date=date); git_push(f"{state} {id}")
    stage("scripting", 10)
    sc = gen_script(item, page, cfg)
    scenes, order = [], []
    for s in sc["scenes"]:
        ls = [l for l in s.get("lines", []) if str(l.get("text", "")).strip() and l.get("who")]
        for l in ls:
            if l["who"].strip().lower() not in [r.lower() for r in order]: order.append(l["who"].strip())
        if ls: scenes.append({"setting": art.norm_setting(s.get("setting")), "lines": ls})
    order = order[:3]; low = [r.lower() for r in order]
    declared = {c.get("role", "").strip().lower(): c for c in sc.get("characters", [])}
    chars = {r: art.get_char(reg, page["id"], r, declared.get(r.lower(), {}).get("gender", "M"), declared.get(r.lower(), {}).get("age", "adult")) for r in order}
    stage("voicing", 35)
    os.makedirs(p("out", "tmp"), exist_ok=True)
    lines, rscenes, t = [], [], 1.0
    for si, s in enumerate(scenes):
        used = [r for r in order if any(l["who"].strip().lower() == r.lower() for l in s["lines"])]
        if not used: continue
        rscenes.append({"setting": s["setting"], "roles": used})
        for li, l in enumerate(s["lines"]):
            who = next((r for r in order if r.lower() == l["who"].strip().lower()), None)
            if not who: continue
            a = audio.tts(l["text"], chars[who], p("out", "tmp", f"{id}_{len(lines)}"))
            if t + len(a) / audio.SR > 27.5 and len(lines) >= 3: break
            emo = l.get("emotion") if l.get("emotion") in EMOS else "neutral"
            lines.append(dict(scene=len(rscenes) - 1, who=who, text=l["text"], emotion=emo, sfx=l.get("sfx") if l.get("sfx") in SFX else None,
                              start=t, end=t + len(a) / audio.SR, audio=a))
            t += len(a) / audio.SR + (.45 if li == len(s["lines"]) - 1 else .28)
    if not lines: raise RuntimeError("empty script")
    rscenes[0]["hook"] = audio.clean(sc.get("hook", ""))
    total = lines[-1]["end"] + 1.4
    stage("rendering", 60)
    wav = p("out", "tmp", f"{id}.wav"); audio.mix(total, lines, wav)
    mp4 = p("out", f"{id}.mp4"); render.render(rscenes, lines, chars, total, wav, mp4, style=page.get('style', 'color'), watermark=page.get('watermark') or ('@' + page['name'].replace(' ', '_') if page.get('style') == 'sketch' else ''))
    stage("uploading", 90)
    url = upload(date, mp4)
    res["items"][id] = dict(page=page["id"], title=item["title"], url=url, duration=round(total, 1), **posts(sc, item))
    save(p("data", "results", f"{date}.json"), res)
    set_item(st, id, state="done", pct=100, msg="", built_rev=item.get("rev", 0), date=date)
    hist = load(p("data", "history.json"), []); hist.append(item["title"]); save(p("data", "history.json"), hist[-200:])

def cleanup():
    if not os.getenv("GITHUB_ACTIONS"): return
    try:
        out = subprocess.run(["gh", "release", "list", "--json", "tagName", "--limit", "60"], capture_output=True, text=True).stdout
        tags = sorted(t["tagName"] for t in json.loads(out) if t["tagName"].startswith("videos-"))
        for tg in tags[:-5]: subprocess.run(["gh", "release", "delete", tg, "--cleanup-tag", "-y"], capture_output=True)
    except Exception: pass

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--date", default=""); a = ap.parse_args()
    date = a.date or str(today()); cfg = config(); pages = {g["id"]: g for g in cfg["pages"]}
    path = p("data", "plans", f"{date}.json")
    if not os.path.exists(path):
        items = planner.make_plan(date, cfg); save(path, {"date": date, "items": items}); git_push(f"plan {date}")
    plan = load(path); st = status()
    cut = str(today() - datetime.timedelta(days=7))
    st["items"] = {k: v for k, v in st["items"].items() if k[:10] >= cut}
    todo = [i for i in plan["items"] if i.get("status", "planned") == "planned" and i["page"] in pages
            and not (st["items"].get(i["id"], {}).get("state") == "done" and st["items"][i["id"]].get("built_rev") == i.get("rev", 0))]
    todo = todo[: cfg.get("max_videos_per_day", 15)]
    for i in todo: set_item(st, i["id"], state="queued", pct=0, msg="", date=date)
    set_run(st, state="running", date=date, total=len(todo), message="started"); git_push("run started")
    reg = load(p("data", "characters.json"), {}); res = load(p("data", "results", f"{date}.json"), {"items": {}}); ok = bad = 0
    for it in todo:
        try:
            (build_story if pages[it["page"]].get("style") == "story" else build)(it, pages[it["page"]], cfg, reg, st, date, res); ok += 1
        except Exception as e:
            traceback.print_exc(); bad += 1; set_item(st, it["id"], state="error", pct=100, msg=str(e)[:300], date=date)
        save(p("data", "characters.json"), reg); git_push(f"finished {it['id']}")
    set_run(st, state="finished", message=f"{ok} done, {bad} failed"); git_push("run finished"); cleanup()

if __name__ == "__main__": main()
