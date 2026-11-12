import argparse, datetime, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from common import *

def make_plan(date, cfg):
    pages = cfg["pages"]
    hist = load(p("data", "history.json"), [])[-80:]
    spec = "\n".join(f"- id={g['id']} | {g['name']} | niche: {g['niche']} | videos: {g['per_day']}" for g in pages)
    prompt = f"""You are the content planner for short vertical cartoon skit videos (under 1 minute) for a broad English-speaking audience on YouTube Shorts, TikTok and Facebook Reels.
Plan the ideas for {date}. One list item per video, for these pages:
{spec}
Language: {cfg.get('language','Filipino')}.
Rules: relatable, genuinely funny, wholesome, strong hook in the first 3 seconds, a punchline or lesson at the end. Every idea must be new and different from these recent titles: {hist}.
Reuse recurring roles (Boss, Employee, Mom, Dad, Teen, Grandma, Teacher, Student, etc.) so characters stay consistent.
Return ONLY JSON: {{"items":[{{"page":"<page id>","title":"short catchy English title","premise":"2-3 sentence outline including the punchline","roles":["Role1","Role2"]}}]}}"""
    items = llm_json(prompt).get("items", [])
    ids = {g["id"] for g in pages}; counts = {}; out = []
    for it in items:
        pg = it.get("page")
        if pg not in ids: continue
        counts[pg] = counts.get(pg, 0) + 1
        out.append({"id": f"{date}-{pg}-{counts[pg]}", "page": pg, "title": it.get("title", "Untitled"),
                    "premise": it.get("premise", ""), "roles": it.get("roles", []), "status": "planned", "rev": 0})
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
