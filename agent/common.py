import json, os, subprocess, datetime, time, re
from zoneinfo import ZoneInfo
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PH = ZoneInfo("Asia/Manila")

def p(*a): return os.path.join(ROOT, *a)
def today(): return datetime.datetime.now(PH).date()
def now_iso(): return datetime.datetime.now(PH).strftime("%Y-%m-%d %H:%M:%S")

def load(path, default=None):
    try:
        with open(path, encoding="utf-8") as f: return json.load(f)
    except Exception: return default

def save(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f: json.dump(obj, f, ensure_ascii=False, indent=2)

def config(): return load(p("config.json"), {"pages": []})

STATUS = p("data", "status.json")
def status(): return load(STATUS, {"run": {}, "items": {}})
def set_item(st, id, **kw):
    st["items"].setdefault(id, {}).update(kw); st["items"][id]["updated"] = now_iso(); save(STATUS, st)
def set_run(st, **kw):
    st.setdefault("run", {}).update(kw); st["run"]["updated"] = now_iso(); save(STATUS, st)

def git_push(msg):
    if not os.getenv("GITHUB_ACTIONS"): return
    sh = lambda *a: subprocess.run(a, cwd=ROOT, capture_output=True, text=True)
    sh("git", "config", "user.name", "video-brain"); sh("git", "config", "user.email", "bot@users.noreply.github.com")
    sh("git", "add", "data")
    if sh("git", "diff", "--cached", "--quiet").returncode == 0: return
    sh("git", "commit", "-m", msg)
    for _ in range(5):
        sh("git", "pull", "--rebase", "--autostash")
        if sh("git", "push").returncode == 0: return
        time.sleep(2)

# ---------- LLM (free): Gemini if key present, else Pollinations ----------
def _gemini(prompt):
    key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if not key: raise RuntimeError("GEMINI_API_KEY is empty or missing in this run")
    err = ""
    for m in ("gemini-2.5-flash", "gemini-2.0-flash", "gemini-flash-latest", "gemini-2.5-flash-lite"):
        for attempt in range(2):
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                headers={"x-goog-api-key": key, "Content-Type": "application/json"}, timeout=120,
                json={"contents": [{"parts": [{"text": prompt}]}],
                      "generationConfig": {"responseMimeType": "application/json", "temperature": 1.0, "maxOutputTokens": 8192}})
            if r.ok:
                try: return r.json()["candidates"][0]["content"]["parts"][0]["text"]
                except Exception: err = f"{m}: empty answer"; break
            err = f"{m} HTTP {r.status_code}: {r.text[:120]}"
            if r.status_code == 429 and attempt == 0: time.sleep(25); continue
            break
    raise RuntimeError(err)

def _pollinations(prompt):
    err = ""
    for m in ("openai-fast", "mistral", "llama", "openai"):
        try:
            r = requests.post("https://text.pollinations.ai/openai", timeout=180,
                json={"model": m, "max_tokens": 6000, "messages": [{"role": "user", "content": prompt}], "jsonMode": True})
            if r.ok:
                txt = r.json()["choices"][0]["message"]["content"]
                if txt and txt.strip(): return txt
            err = r.text[:150]
        except Exception as e: err = str(e)[:150]
    raise RuntimeError("pollinations: " + err)

def parse_json(txt):
    txt = re.sub(r"^```(?:json)?|```$", "", txt.strip(), flags=re.M).strip()
    a = min([i for i in (txt.find("{"), txt.find("[")) if i >= 0] or [0])
    b = max(txt.rfind("}"), txt.rfind("]")) + 1
    return json.loads(txt[a:b])

def llm_json(prompt, retries=3):
    errs = []
    for i in range(retries):
        for fn in (_gemini, _pollinations):
            try: return parse_json(fn(prompt))
            except Exception as e: errs.append(f"{fn.__name__[1:]}: {str(e)[:170]}")
        time.sleep(4 * (i + 1))
    raise RuntimeError("AI writer failed. " + " | ".join(errs[-2:]))
