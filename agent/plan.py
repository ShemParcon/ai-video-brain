import argparse, datetime, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from common import *

def make_plan(date, cfg):
    pages = cfg["pages"]
    hist = load(p("data", "history.json"), [])[-100:]
    spec = "\n".join(f"- id={g['id']} | {g['name']} | topics: {g['niche']} {('(' + g['guide'] + ')') if g.get('guide') else ''} | videos: {g['per_day']}" for g in pages)
    prompt = f"""You are the content planner for faceless channels that post narrated stick figure animation videos on YouTube Shorts, TikTok and Facebook Reels. Today is {date}.
Pages:
{spec}
For each video choose a topic people will want to watch right now: either (a) Did you know trivia with surprising TRUE facts, or (b) a TRUE survival or rescue story from a specific country (trapped miners, lost hikers, shipwreck survivors, earthquake, cave or sea rescues) or a famous historical story retold. Use web search to confirm the event is real and to collect its key verifiable facts (dates, numbers, places, outcomes).
Rules: only real, well documented events; never invent details; respectful and non graphic; vary countries and eras; every topic must be new and different from these recent titles: {hist}.
Return ONLY JSON: {{"items":[{{"page":"<page id>","title":"catchy title","kind":"did you know or rescue story or famous story","country":"country or region","premise":"2 to 3 sentence summary","facts":["8 to 12 short verified facts with numbers or dates"],"roles":["Miner","Rescuer"]}}]}}"""
    items = llm_json(prompt, search=True).get("items", [])
    ids = {g["id"] for g in pages}; counts = {}; out = []
    for it in items:
        pg = it.get("page")
        if pg not in ids: continue
        counts[pg] = counts.get(pg, 0) + 1
        if counts[pg] > next(g["per_day"] for g in pages if g["id"] == pg): continue
        out.append({"id": f"{date}-{pg}-{counts[pg]}", "page": pg, "title": it.get("title", "Untitled"), "kind": it.get("kind", ""), "country": it.get("country", ""),
                    "premise": it.get("premise", ""), "facts": [str(x) for x in it.get("facts", [])][:14], "roles": it.get("roles", []), "status": "planned", "rev": 0})
    return out[: cfg.get("max_videos_per_day", 15)]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--date", default=""); ap.add_argument("--force", default="")
    a = ap.parse_args()
    date = a.date or str(today() + datetime.timedelta(days=1))
    path = p("data", "plans", f"{date}.json")
    if os.path.exists(path) and a.force.lower() != "true":
        print("plan exists, keeping your edits"); return
    items = make_plan(date, config())
    if not items: raise SystemExit("no items planned")
    save(path, {"date": date, "items": items}); git_push(f"plan {date}"); print("planned", len(items))

if __name__ == "__main__": main()
