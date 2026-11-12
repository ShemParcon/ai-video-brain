import argparse, datetime, json, os, subprocess, sys, traceback
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
from common import *
import art, audio, render, plan as planner

SFX = {"pop", "ding", "whoosh", "bonk", "sad", "laugh"}
EMOS = {"neutral", "happy", "angry", "sad", "surprised"}

def gen_script(item, page, cfg):
    if os.getenv("DRY_SCRIPT"): return load(os.getenv("DRY_SCRIPT"))
    prompt = """Write a script for a funny vertical cartoon skit video that is under 45 seconds when spoken.
Language: __LANG__. Fast back-and-forth: 10 to 14 short lines (max 10 words each), 2 to 3 characters.
Page: __PAGE__ (__NICHE__). Title: __TITLE__. Story: __PREMISE__. Roles to use: __ROLES__.
Open with a hook line that grabs attention in the first 2 seconds. Escalate the situation with each line and finish with a surprising twist or a punchline. Relatable and wholesome: no real people, brands, copyrighted characters, harmful or sexual content.
Write every line exactly as a text-to-speech voice should read it: plain words, NO hyphenated words, NO acronyms, NO emojis or symbols, numbers written in words, normal spelling.
Allowed settings: office, home, kitchen, bedroom, school, street, market, church, cafe, park.
Allowed emotions: neutral, happy, angry, sad, surprised. Allowed sfx (or null): pop, ding, whoosh, bonk, sad, laugh.
Return ONLY JSON:
{"characters":[{"role":"Boss","gender":"M","age":"adult"}],"scenes":[{"setting":"office","lines":[{"who":"Boss","text":"...","emotion":"angry","sfx":null}]}],"youtube_title":"max 70 chars","hook":"on-screen hook, max 6 words","caption":"1-2 funny sentences with emojis ending with a question for comments","hashtags":["#tag1","#tag2","#tag3","#tag4","#tag5","#tag6","#tag7","#tag8"]}
gender is M or F; age is kid, adult, or old.""".replace("__LANG__", cfg.get("language", "Filipino")).replace("__PAGE__", page["name"]) \
        .replace("__NICHE__", page["niche"]).replace("__TITLE__", item["title"]).replace("__PREMISE__", item["premise"]) \
        .replace("__ROLES__", ", ".join(item.get("roles", [])) or "your choice")
    return llm_json(prompt)

def posts(sc, item):
    tags = [("#" + t.lstrip("#")).replace(" ", "") for t in sc.get("hashtags", [])]
    tags = [t for t in dict.fromkeys(tags) if t.lower() not in ("#shorts", "#fyp", "#foryou")][:8]
    cap = (sc.get("caption") or item["title"]).strip()
    yt_title = (sc.get("youtube_title") or item["title"])[:90]
    return {"yt_title": yt_title, "yt_desc": f"{cap}\n\n{' '.join(tags[:6])} #shorts",
            "tiktok": f"{cap}\n\n{' '.join(tags[:5])} #fyp #foryou", "facebook": f"{cap}\n\n{' '.join(tags[:4])}"}

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
    lines, rscenes, t = [], [], 0.4
    for si, s in enumerate(scenes):
        used = [r for r in order if any(l["who"].strip().lower() == r.lower() for l in s["lines"])]
        if not used: continue
        rscenes.append({"setting": s["setting"], "roles": used})
        for li, l in enumerate(s["lines"]):
            who = next((r for r in order if r.lower() == l["who"].strip().lower()), None)
            if not who: continue
            a = audio.tts(l["text"], chars[who], p("out", "tmp", f"{id}_{len(lines)}"))
            if t + len(a) / audio.SR > 57 and len(lines) >= 4: break
            emo = l.get("emotion") if l.get("emotion") in EMOS else "neutral"
            lines.append(dict(scene=len(rscenes) - 1, who=who, text=l["text"], emotion=emo, sfx=l.get("sfx") if l.get("sfx") in SFX else None,
                              start=t, end=t + len(a) / audio.SR, audio=a))
            t += len(a) / audio.SR + (.45 if li == len(s["lines"]) - 1 else .28)
    if not lines: raise RuntimeError("empty script")
    rscenes[0]["hook"] = audio.clean(sc.get("hook", ""))
    total = lines[-1]["end"] + .9
    stage("rendering", 60)
    wav = p("out", "tmp", f"{id}.wav"); audio.mix(total, lines, wav)
    mp4 = p("out", f"{id}.mp4"); render.render(rscenes, lines, chars, total, wav, mp4)
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
            build(it, pages[it["page"]], cfg, reg, st, date, res); ok += 1
        except Exception as e:
            traceback.print_exc(); bad += 1; set_item(st, it["id"], state="error", pct=100, msg=str(e)[:300], date=date)
        save(p("data", "characters.json"), reg); git_push(f"finished {it['id']}")
    set_run(st, state="finished", message=f"{ok} done, {bad} failed"); git_push("run finished"); cleanup()

if __name__ == "__main__": main()
