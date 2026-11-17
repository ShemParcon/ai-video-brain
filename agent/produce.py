import argparse, datetime, os, subprocess, sys, traceback, json
sys.path.insert(0, os.path.dirname(__file__))
from common import *
import art, audio, render
from script import parse_joke

PAGE = "dadjokes"

def posts(sc, cfg):
    tags = [t for t in dict.fromkeys(sc["hashtags"]) if t.lower() not in ("#shorts", "#fyp", "#foryou")][:8]
    cap = sc["caption"].strip()
    return {"yt_title": sc["youtube_title"], "yt_desc": f"{cap}\n\n{' '.join(tags[:6])} #shorts",
            "tiktok": f"{cap}\n\n{' '.join(tags[:5])} #fyp #foryou", "facebook": f"{cap}\n\n{' '.join(tags[:4])}"}

def upload(date, path):
    if not os.getenv("GITHUB_ACTIONS"): return path
    tag = f"videos-{date}"; run = lambda *a: subprocess.run(a, capture_output=True, text=True)
    run("gh", "release", "create", tag, "--title", f"Videos {date}", "--notes", "Dad joke videos")
    r = run("gh", "release", "upload", tag, path, "--clobber")
    if r.returncode: raise RuntimeError("upload failed: " + r.stderr[:200])
    return f"https://github.com/{os.environ['GITHUB_REPOSITORY']}/releases/download/{tag}/{os.path.basename(path)}"

def build(item, cfg, reg, st, date, res):
    id = item["id"]
    def stage(state, pct, msg=""): set_item(st, id, state=state, pct=pct, msg=msg, date=date); git_push(f"{state} {id}")
    stage("scripting", 10)
    sc = parse_joke(item["text"], cfg)
    order = [c["role"] for c in sc["characters"]]
    chars = {c["role"]: art.get_char(reg, PAGE, c["role"], c["gender"], c["age"]) for c in sc["characters"]}
    stage("voicing", 35)
    os.makedirs(p("out", "tmp"), exist_ok=True)
    lines, t = [], 1.0
    L = sc["scenes"][0]["lines"]
    for li, l in enumerate(L):
        a = audio.tts(l["text"], chars[l["who"]], p("out", "tmp", f"{id}_{li}"))
        if t + len(a) / audio.SR > 58 and len(lines) >= 3: break
        lines.append(dict(scene=0, who=l["who"], text=l["text"], emotion=l["emotion"], sfx=l["sfx"], start=t, end=t + len(a) / audio.SR, audio=a))
        t += len(a) / audio.SR + (.45 if li == len(L) - 1 else .28)
    used = [r for r in order if any(x["who"] == r for x in lines)]
    rscenes = [{"setting": art.norm_setting(sc["scenes"][0]["setting"]), "roles": used, "hook": audio.clean(sc["hook"])}]
    total = lines[-1]["end"] + 1.4
    stage("rendering", 60)
    wav = p("out", "tmp", f"{id}.wav"); audio.mix(total, lines, wav)
    style = sc.get("style") or cfg.get("style", "color")
    wm = cfg.get("watermark") or ("@DADJOKES" if style == "sketch" else "")
    mp4 = p("out", f"{id}.mp4"); render.render(rscenes, lines, chars, total, wav, mp4, style=style, watermark=wm)
    stage("uploading", 90)
    url = upload(date, mp4)
    res["items"][id] = dict(date=date, title=sc["title"], url=url, duration=round(total, 1), **posts(sc, cfg))
    keep = sorted(res["items"].items(), key=lambda kv: kv[1].get("date", ""), reverse=True)[:80]; res["items"] = dict(keep)
    save(p("data", "results.json"), res)
    set_item(st, id, state="done", pct=100, msg="", built_rev=item.get("rev", 0), date=date)

def cleanup():
    if not os.getenv("GITHUB_ACTIONS"): return
    try:
        out = subprocess.run(["gh", "release", "list", "--json", "tagName", "--limit", "60"], capture_output=True, text=True).stdout
        tags = sorted(t["tagName"] for t in json.loads(out) if t["tagName"].startswith("videos-"))
        for tg in tags[:-7]: subprocess.run(["gh", "release", "delete", tg, "--cleanup-tag", "-y"], capture_output=True)
    except Exception: pass

def main():
    cfg = config(); date = str(today())
    q = load(p("data", "queue.json"), {"items": []}); st = status()
    ids = {i["id"] for i in q["items"]}
    st["items"] = {k: v for k, v in st["items"].items() if k in ids}
    todo = [i for i in q["items"] if i.get("status", "queued") == "queued"
            and not (st["items"].get(i["id"], {}).get("state") == "done" and st["items"][i["id"]].get("built_rev") == i.get("rev", 0))]
    todo = todo[: int(cfg.get("max_per_run", 20))]
    for i in todo: set_item(st, i["id"], state="queued", pct=0, msg="", date=date)
    set_run(st, state="running", date=date, total=len(todo), message=f"making {len(todo)} video(s)"); git_push("run started")
    reg = load(p("data", "characters.json"), {}); res = load(p("data", "results.json"), {"items": {}}); ok = bad = 0
    for it in todo:
        try: build(it, cfg, reg, st, date, res); ok += 1
        except Exception as e:
            traceback.print_exc(); bad += 1; set_item(st, it["id"], state="error", pct=100, msg=str(e)[:300], date=date)
        save(p("data", "characters.json"), reg); git_push(f"finished {it['id']}")
    set_run(st, state="finished", message=f"{ok} done, {bad} failed"); git_push("run finished"); cleanup()

if __name__ == "__main__": main()
