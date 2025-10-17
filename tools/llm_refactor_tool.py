import re, requests, datetime, sys, json
from pathlib import Path

LOG_FILE = Path("log/llm_log.txt")
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
MARKER_RE = re.compile(r"<<<BEGIN FILE>>>\s*(.*?)\s*<<<END FILE>>>", re.DOTALL)

# Common chat params you can set under [llm] -> params in project.conf.
# Only 'model' and 'messages' are reserved by the payload builder.
POSSIBLE_PARAMS = (
    # sampling / output control
    "temperature", "top_p", "max_tokens", "n", "stop", "seed",
    # penalties
    "presence_penalty", "frequency_penalty",
    # log probs (where supported)
    "logprobs", "top_logprobs",
    # response shaping / structured output
    "response_format",  # e.g. {"type":"json_object"} if you switch parsers later
    # tool use (if your backend supports it)
    "tools", "tool_choice", "parallel_tool_calls",
    # logits controls (provider-specific; pass-through)
    "logit_bias",
    # metadata/user (auditing/rate-limits)
    "user", "metadata",
)

SYSTEM_PROMPT = (
    "You are a careful C/C++ refactoring assistant.\n"
    # "Goals: modernize for clarity/safety without changing observable behavior, and use Intel oneAPI IPP as much as possible.\n"
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
    base_url = cfg["base_url"].rstrip("/")
    headers = {"Content-Type": "application/json"}
    if cfg.get("api_key"):
        headers["Authorization"] = f"Bearer {cfg['api_key']}"

    # --- Ping the server first ---
    try:
        ping_url = base_url + "/models"
        ping_resp = requests.get(ping_url, headers=headers, timeout=10)
        ping_resp.raise_for_status()
        print("[llm] connected to server, llm is writing...")
    except Exception as e:
        raise RuntimeError(f"[llm] failed to connect to server at {base_url}: {e}")

    # --- Now build and send the actual chat completion ---
    url = base_url + "/chat/completions"
    prompt_for_log, payload = _build_request(cfg["model"], filename, code, ro_context)

    params = cfg.get("params", {})
    if params:
        for k, v in params.items():
            if k not in ("model", "messages") and v is not None:
                payload[k] = v

    # print("[llm] sending payload:")
    # print(json.dumps(payload, indent=2))

    r = requests.post(url, headers=headers, json=payload, timeout=120)
    r.raise_for_status()
    data = r.json()
    reply = data["choices"][0]["message"]["content"]

    if cfg.get("log", True):
        _log_conversation(str(filename), prompt_for_log, reply)

    return _parse_reply(reply)

def refactor_with_context(cfg, editable_files, read_only_files):
    ro_context = _make_ro_context(read_only_files)
    had_error = False
    for fp in editable_files:
        p = Path(fp)
        if not p.exists():
            print(f"[llm] skip missing editable: {p}")
            had_error = True
            continue
        print(f"[llm] refactor -> {p}")
        original = p.read_text(encoding="utf-8", errors="ignore")
        try:
            new_text = _call_llm(cfg, p.name, original, ro_context)
        except Exception as e:
            print(f"[llm] error on {p}: {e}")
            had_error = True
            break  # fail-fast within the LLM step
        p.write_text(new_text, encoding="utf-8")
        print(f"[llm] wrote -> {p}")
    return not had_error

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