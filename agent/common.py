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
def _gemini_models(key):
    base = ["gemini-flash-latest", "gemini-2.5-flash", "gemini-2.0-flash"]
    try:
        r = requests.get("https://generativelanguage.googleapis.com/v1beta/models", headers={"x-goog-api-key": key}, params={"pageSize": 200}, timeout=30)
        names = [m["name"].split("/")[-1] for m in r.json().get("models", []) if "generateContent" in m.get("supportedGenerationMethods", [])]
        bad = ("lite", "image", "tts", "audio", "live", "thinking", "8b", "robotics", "embedding", "computer", "vision")
        flash = [n for n in names if "flash" in n and not any(x in n for x in bad)]
        late = ("omni", "preview", "exp")
        main = sorted([n for n in flash if not any(x in n for x in late)], reverse=True)
        rest = sorted([n for n in flash if any(x in n for x in late)], reverse=True)
        lite = sorted([n for n in names if "flash-lite" in n and "image" not in n and "tts" not in n], reverse=True)
        return list(dict.fromkeys(["gemini-flash-latest"] + main + base[1:] + lite + rest))
    except Exception:
        return base

def _gemini(prompt, search=False):
    key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if not key: raise RuntimeError("GEMINI_API_KEY is empty or missing in this run")
    errs = []
    for m in _gemini_models(key)[:(3 if search else 9)]:
        base = {"responseMimeType": "application/json", "temperature": 1.0, "maxOutputTokens": 8192}
        nomime = {k: v for k, v in base.items() if k != "responseMimeType"}
        variants = [nomime] if search else ([{**base, "thinkingConfig": {"thinkingBudget": 0}}] if "2.5" in m else []) + [base, nomime]
        for cfg in variants:
            try:
                r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent",
                    headers={"x-goog-api-key": key, "Content-Type": "application/json"}, timeout=90,
                    json={"contents": [{"parts": [{"text": prompt}]}], "generationConfig": cfg, **({"tools": [{"google_search": {}}]} if search else {})})
            except Exception as e:
                errs.append(f"{m} {str(e)[:40]}"); break
            if r.ok:
                try: return r.json()["candidates"][0]["content"]["parts"][0]["text"]
                except Exception: errs.append(f"{m} empty"); break
            if r.status_code == 400: continue
            errs.append(f"{m} {r.status_code}"); time.sleep(1); break
    raise RuntimeError("; ".join(errs[-4:]))

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

def llm_json(prompt, retries=3, search=False):
    errs = []
    for i in range(retries):
        tries = ([("gemini+search", lambda: _gemini(prompt, True))] if search else []) + [("gemini", lambda: _gemini(prompt)), ("pollinations", lambda: _pollinations(prompt))]
        for name, fn in tries:
            try: return parse_json(fn())
            except Exception as e: errs.append(f"{name}: {str(e)[:170]}")
        time.sleep(30 if any('429' in e for e in errs[-3:]) else 4 * (i + 1))
    raise RuntimeError("AI writer failed. " + " | ".join(errs[-2:]))
