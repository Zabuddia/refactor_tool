from __future__ import annotations
import re, requests, datetime
from pathlib import Path
from typing import List, Dict

LOG_FILE = Path("llm_log.txt")

MARKER_RE = re.compile(r"<<<BEGIN FILE>>>\s*(.*?)\s*<<<END FILE>>>", re.DOTALL)

SYSTEM_PROMPT = (
    "You are a careful C/C++ refactoring assistant. "
    "Rewrite ONLY the provided *editable* file for clarity and safety without changing behavior. "
    "Use the read-only files as context, but do not modify them. "
    "Return only the complete new file between <<<BEGIN FILE>>> and <<<END FILE>>>."
)

def _extract_new_code(reply: str) -> str:
    """Extract code from <<<BEGIN FILE>>> ... <<<END FILE>>> markers."""
    m = MARKER_RE.search(reply)
    return m.group(1).strip() if m else reply.strip()

def _call_llm(llm_cfg: Dict[str, str], filename: str, code: str, ro_context: str) -> str:
    """Call the LLM API for a single file refactor request."""
    url = llm_cfg["base_url"] + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if llm_cfg.get("api_key"):
        headers["Authorization"] = f"Bearer {llm_cfg['api_key']}"

    user_content = (
        f"Refactor the *editable* file below.\n"
        f"Use READ-ONLY files only for context.\n\n"
        f"=== READ-ONLY CONTEXT BEGIN ===\n{ro_context}\n=== READ-ONLY CONTEXT END ===\n\n"
        f"=== EDITABLE FILE: {filename} ===\n```\n{code}\n```\n\n"
        "Output format:\n<<<BEGIN FILE>>>\n<entire rewritten file>\n<<<END FILE>>>"
    )

    payload = {
        "model": llm_cfg["model"],
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
    }

    r = requests.post(url, headers=headers, json=payload)
    r.raise_for_status()
    data = r.json()
    reply = data["choices"][0]["message"]["content"]

    if llm_cfg.get("log", True):
        _log_conversation(filename, user_content, reply)

    return reply

def _make_ro_context(read_only_files: List[Path]) -> str:
    """Combine read-only files into one context blob."""
    chunks = []
    for fp in read_only_files:
        p = Path(fp)
        if not p.exists():
            chunks.append(f"[skip missing] {p}\n")
            continue
        txt = p.read_text(encoding="utf-8", errors="ignore")
        chunks.append(f"FILE: {p.name}\n```\n{txt}\n```")
    return "\n\n".join(chunks).strip()


def _log_conversation(filename: str, prompt: str, reply: str) -> None:
    """Append one LLM exchange to a log file."""
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"\n=== {ts} | {filename} ===\n")
        f.write("---- PROMPT ----\n")
        f.write(prompt.strip() + "\n\n")
        f.write("---- REPLY ----\n")
        f.write(reply.strip() + "\n")
        f.write("=" * 60 + "\n")

def refactor_with_context(
    llm_cfg: Dict[str, str],
    editable_files: List[Path],
    read_only_files: List[Path],
) -> None:
    """Refactor each editable file using LLM context from the read-only ones."""
    ro_context = _make_ro_context(read_only_files)

    for fp in editable_files:
        p = Path(fp)
        if not p.exists():
            print(f"[llm] skip missing editable: {p}")
            continue

        print(f"[llm] refactor -> {p}")
        original = p.read_text(encoding="utf-8", errors="ignore")
        try:
            reply = _call_llm(llm_cfg, p.name, original, ro_context)
        except Exception as e:
            print(f"[llm] error on {p}: {e}")
            continue

        new_text = _extract_new_code(reply)
        p.write_text(new_text, encoding="utf-8")
        print(f"[llm] wrote -> {p}")