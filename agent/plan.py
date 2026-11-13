import argparse, datetime, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from common import *

def make_plan(date, cfg):
    pages = cfg["pages"]
    hist = load(p("data", "history.json"), [])[-100:]
    spec = "\n".join(f"- id={g['id']} | {g['name']} | style: {g['niche']} {('(' + g['guide'] + ')') if g.get('guide') else ''} | videos: {g['per_day']}" for g in pages)
    prompt = f"""You are the content planner for a network of joke channels that post short vertical cartoon skits (15 to 30 seconds) on YouTube Shorts, TikTok and Facebook Reels.
Today is {date}. Use what is going viral right now (trending jokes, meme formats, popular joke styles) together with proven evergreen viral joke styles: classic dad jokes, puns, relatable POV humor, riddles with silly answers, me versus reality jokes, wholesome twists.
Plan the jokes for these pages:
{spec}
For every video write the FULL joke (setup and punchline) in the premise, so the scriptwriter can perform it. Keep each joke short enough to perform in about 20 seconds.
Rules: clean, wholesome humor. No politics, religion, tragedy, real people, brands or copyrighted characters. Do not copy lines from copyrighted comedy. Every joke must be new and different from these recent titles: {hist}.
Use the same recurring roles per page so characters stay consistent (for example Dad and Kid for the dad joke page).
Return ONLY JSON: {{"items":[{{"page":"<page id>","title":"short catchy title","premise":"the full joke: setup, punchline and the reaction beat","roles":["Role1","Role2"]}}]}}"""
    items = llm_json(prompt, search=True).get("items", [])
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
