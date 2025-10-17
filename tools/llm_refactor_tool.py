import re, requests, datetime, sys
from pathlib import Path

LOG_FILE = Path("llm_log.txt")
MARKER_RE = re.compile(r"<<<BEGIN FILE>>>\s*(.*?)\s*<<<END FILE>>>", re.DOTALL)

SYSTEM_PROMPT = (
    "You are a careful C/C++ refactoring assistant.\n"
    "Goals: modernize for clarity/safety without changing observable behavior, and use Intel oneAPI IPP as much as possible.\n"
    "\n"
    "Rules:\n"
    "• For files with .c extension: write valid ISO C11 code only.\n"
    "• For files with .cpp extension: C++17 style is allowed.\n"
    "• Do not modify read-only files; they are context only.\n"
)

def _build_request(model, filename, code, ro_context):
    file_hint = "C file (.c, use C11)" if str(filename).endswith(".c") else "C++17 file (.cpp)"
    user_content = (
        f"Refactor the {file_hint} below.\n"
        f"Use READ-ONLY files only for context.\n\n"
        f"=== READ-ONLY CONTEXT BEGIN ===\n{ro_context}\n=== READ-ONLY CONTEXT END ===\n\n"
        f"=== EDITABLE FILE: {filename} ===\n```\n{code}\n```\n\n"
        "Output format:\n<<<BEGIN FILE>>>\n<entire rewritten file>\n<<<END FILE>>>"
    )
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT + "Output exactly the full rewritten file with the required markers."},
            {"role": "user", "content": user_content},
        ],
    }
    return user_content, payload

def _parse_reply(reply_text):
    m = re.search(MARKER_RE, reply_text or "")
    return m.group(1).strip() if m else (reply_text or "").strip()

def _make_ro_context(read_only_files):
    chunks = []
    for fp in read_only_files:
        p = Path(fp)
        if not p.exists():
            chunks.append(f"[skip missing] {p}\n")
            continue
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            chunks.append(f"[error reading] {p}: {e}\n")
            continue
        chunks.append(f"FILE: {p.name}\n```\n{txt}\n```")
    return "\n\n".join(chunks).strip()

def _log_conversation(filename, prompt, reply):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(f"\n=== {ts} | {filename} ===\n")
        f.write("---- PROMPT ----\n")
        f.write((prompt or "").strip() + "\n\n")
        f.write("---- REPLY ----\n")
        f.write((reply or "").strip() + "\n")
        f.write("=" * 60 + "\n")

def _call_llm(cfg, filename, code, ro_context):
    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if cfg.get("api_key"):
        headers["Authorization"] = f"Bearer {cfg['api_key']}"

    prompt_for_log, payload = _build_request(cfg["model"], filename, code, ro_context)
    r = requests.post(url, headers=headers, json=payload, timeout=120)
    r.raise_for_status()
    data = r.json()
    reply = data["choices"][0]["message"]["content"]

    if cfg.get("log", True):
        _log_conversation(str(filename), prompt_for_log, reply)

    return _parse_reply(reply)

def refactor_with_context(cfg, editable_files, read_only_files):
    ro_context = _make_ro_context(read_only_files)
    for fp in editable_files:
        p = Path(fp)
        if not p.exists():
            print(f"[llm] skip missing editable: {p}")
            continue
        print(f"[llm] refactor -> {p}")
        original = p.read_text(encoding="utf-8", errors="ignore")
        try:
            new_text = _call_llm(cfg, p.name, original, ro_context)
        except Exception as e:
            print(f"[llm] error on {p}: {e}")
            continue
        p.write_text(new_text, encoding="utf-8")
        print(f"[llm] wrote -> {p}")

if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Refactor files with LLM using read-only context.")
    p.add_argument("--base-url", required=True, help="OpenAI-compatible base URL (e.g., https://openrouter.ai/api/v1 or http://localhost:8000/v1)")
    p.add_argument("--model",     required=True, help="Model name")
    p.add_argument("--api-key",   default="",    help="Bearer key (optional)")
    p.add_argument("--no-log",    action="store_true", help="Disable conversation logging")
    p.add_argument("--ro",        nargs="*", default=[], help="Read-only context files")
    p.add_argument("--edit",      nargs="+",           help="Editable files to rewrite")
    args = p.parse_args()

    cfg = {
        "base_url": args.base_url,
        "model": args.model,
        "api_key": args.api_key,
        "log": not args.no_log,
    }

    if not args.edit:
        print("No --edit files provided.")
        sys.exit(1)

    refactor_with_context(cfg, args.edit, args.ro)