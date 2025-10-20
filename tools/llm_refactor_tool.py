import re, requests, datetime, sys, json
from pathlib import Path
from json import JSONDecodeError

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
    "response_format",
    # tool use (if your backend supports it)
    "tools", "tool_choice", "parallel_tool_calls",
    # logits controls (provider-specific; pass-through)
    "logit_bias",
    # metadata/user (auditing/rate-limits)
    "user", "metadata",
)

SYSTEM_PROMPT = (
    "You are a careful C/C++ refactoring assistant.\n"
    "Goals: modernize for clarity/safety without changing observable behavior, "
    "and use Intel oneAPI IPP as much as possible.\n"
    "\n"
    "Prioritization:\n"
    "• Build and compiler error logs are the highest priority. "
    "Fix compile/test failures before any cleanup or modernization.\n"
    "• Only when code compiles and tests pass may you do stylistic changes.\n"
    "\n"
    "Header policy (MANDATORY):\n"
    "• When using Intel IPP, include ONLY <ipp.h>.\n"
    "• DO NOT include ipps.h, ippcore.h, ippvm.h, ipptypes.h, or any other IPP sub-headers directly.\n"
    "• If the input code contains those, replace them with #include <ipp.h>.\n"
    "\n"
    "Rules:\n"
    "• For .c files: strictly ISO C11.\n"
    "• For .cpp files: C++17 allowed.\n"
    "• Do not modify read-only files; they are context only.\n"
    "\n"
    "Before finalizing, verify: (a) the code compiles in isolation, (b) the header policy is obeyed, "
    "and (c) all referenced symbols are provided by <ipp.h>.\n"
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

# --- minimal additions for multi-file per chunk ---

def _build_request_multi(model, file_names, codes, ro_context):
    parts = ["Refactor the following files. Use READ-ONLY files only for context.\n"]
    parts.append(f"=== READ-ONLY CONTEXT BEGIN ===\n{ro_context}\n=== READ-ONLY CONTEXT END ===\n")
    for fn, code in zip(file_names, codes):
        file_hint = "C file (.c, use C11)" if str(fn).endswith(".c") else "C++17 file (.cpp)"
        parts.append(f"\n=== EDITABLE FILE: {fn} ({file_hint}) ===\n```\n{code}\n```")
    parts.append(
        "\nOutput format:\n"
        "For EACH input file, in the SAME ORDER, output:\n"
        "<<<BEGIN FILE>>>\n<entire rewritten file for that input>\n<<<END FILE>>>\n"
        "Repeat once per input file."
    )
    user_content = "\n".join(parts)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT + "Output one BEGIN/END block per input file, in order."},
            {"role": "user", "content": user_content},
        ],
    }
    return user_content, payload

def _parse_reply(reply_text):
    m = re.search(MARKER_RE, reply_text or "")
    return m.group(1).strip() if m else (reply_text or "").strip()

def _parse_many(reply_text):
    return [m.group(1).strip() for m in MARKER_RE.finditer(reply_text or "")]

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

def _iter_chunks(items, size):
    size = max(int(size or 1), 1)
    for i in range(0, len(items), size):
        yield items[i:i+size]

def _post_and_extract(cfg, payload, prompt_for_log, log_name):
    base_url = cfg["base_url"].rstrip("/")
    headers = {"Content-Type": "application/json"}
    if cfg.get("api_key"):
        headers["Authorization"] = f"Bearer {cfg['api_key']}"
    try:
        ping_url = base_url + "/models"
        ping_resp = requests.get(ping_url, headers=headers, timeout=10)
        ping_resp.raise_for_status()
        print("[llm] connected to server, llm is writing...")
    except Exception as e:
        raise RuntimeError(f"[llm] failed to connect to server at {base_url}: {e}")

    # merge params (no clobber of required keys)
    if not cfg.get("force_json_mode", False):
        rf = payload.get("response_format")
        if isinstance(rf, dict) and rf.get("type") == "json_object":
            payload.pop("response_format", None)
    params = cfg.get("params", {})
    if params:
        for k, v in params.items():
            if k not in ("model", "messages") and v is not None:
                payload[k] = v

    url = base_url + "/chat/completions"
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=120)
    except requests.RequestException as e:
        raise RuntimeError(f"[llm] POST error: {e}")

    ct = r.headers.get("Content-Type", "")
    if not r.ok:
        body_head = r.text[:1200] if hasattr(r, "text") else "<no body>"
        raise RuntimeError(f"[llm] HTTP {r.status_code} {ct}\n{body_head}")

    try:
        data = r.json()
    except JSONDecodeError as e:
        body_head = r.text[:1200] if hasattr(r, "text") else "<no body>"
        raise RuntimeError(f"[llm] JSON decode error: {e}\nContent-Type: {ct}\nBody(head):\n{body_head}")

    choices = data.get("choices")
    if not choices or not isinstance(choices, list):
        raise RuntimeError(f"[llm] No 'choices' in response. Head: {str(data)[:400]}")
    msg = choices[0].get("message") or {}
    reply = msg.get("content")
    if not reply:
        raise RuntimeError(f"[llm] Empty content. Head: {str(data)[:400]}")

    if cfg.get("log", True):
        _log_conversation(log_name, prompt_for_log, reply)
    return reply

def _call_llm(cfg, filename, code, ro_context):
    prompt_for_log, payload = _build_request(cfg["model"], filename, code, ro_context)
    reply = _post_and_extract(cfg, payload, prompt_for_log, str(filename))
    return _parse_reply(reply)

def _call_llm_multi(cfg, file_names, codes, ro_context):
    prompt_for_log, payload = _build_request_multi(cfg["model"], file_names, codes, ro_context)
    log_name = ", ".join(file_names)
    reply = _post_and_extract(cfg, payload, prompt_for_log, log_name)
    blocks = _parse_many(reply)
    if len(blocks) != len(file_names):
        raise RuntimeError(f"[llm] Expected {len(file_names)} output blocks, got {len(blocks)}.")
    return blocks

def refactor_with_context(cfg, editable_files, read_only_files):
    ro_context = _make_ro_context(read_only_files)
    had_error = False
    chunk_size = max(int(cfg.get("chunk_size", 1) or 1), 1)

    files = list(editable_files)
    for ci, group in enumerate(_iter_chunks(files, chunk_size), 1):
        print(f"[llm] chunk {ci} ({len(group)} file(s))")

        file_paths, file_names, codes = [], [], []
        for fp in group:
            p = Path(fp)
            if not p.exists():
                print(f"[llm] skip missing editable: {p}")
                had_error = True
                continue
            file_paths.append(p)
            file_names.append(p.name)
            codes.append(p.read_text(encoding="utf-8", errors="ignore"))

        if not file_paths:
            continue

        try:
            if len(file_paths) == 1:
                new_texts = [_call_llm(cfg, file_names[0], codes[0], ro_context)]
            else:
                new_texts = _call_llm_multi(cfg, file_names, codes, ro_context)
        except Exception as e:
            print(f"[llm] error in chunk {ci}: {e}")
            had_error = True
            break

        for p, new_text in zip(file_paths, new_texts):
            p.write_text(new_text, encoding="utf-8")
            print(f"[llm] wrote -> {p}")

        if had_error:
            break
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
    p.add_argument("--chunk-size", type=int, default=1, help="Number of files to process per chunk (default: 1)")
    args = p.parse_args()

    cfg = {
        "base_url": args.base_url,
        "model": args.model,
        "api_key": args.api_key,
        "log": not args.no_log,
        "chunk_size": args.chunk_size,
    }

    if not args.edit:
        print("No --edit files provided.")
        sys.exit(1)

    refactor_with_context(cfg, args.edit, args.ro)