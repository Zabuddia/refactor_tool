import subprocess, sys, datetime
from pathlib import Path

POST_LOG = Path("log/post_log.txt")
LAST_OUT = Path("log/post_last.txt")

def _ensure_logdir():
    POST_LOG.parent.mkdir(parents=True, exist_ok=True)

def run_post_command(command, code_dir):
    if not command or not command.strip():
        return 0, ""
    print(f"[post] running in {code_dir}: {command}")
    p = subprocess.Popen(
        command, shell=True, cwd=str(code_dir),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1
    )
    lines = []
    for line in p.stdout:
        sys.stdout.write(line)
        lines.append(line)
    p.wait()
    out = "".join(lines)
    return p.returncode, out

def log_post_output(command, code_dir, rc, output):
    _ensure_logdir()
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with POST_LOG.open("a", encoding="utf-8") as f:
        f.write(f"\n=== {ts} | rc={rc} | {code_dir} ===\n")
        f.write(f"$ {command}\n")
        f.write(output)
        f.write("\n" + "="*60 + "\n")

def run_post_with_llm_retry(command, code_dir, retries, llm, refactor_fn):
    rc, out = run_post_command(command, code_dir)
    log_post_output(command, code_dir, rc, out)
    print(f"[post] exit code: {rc}")

    can_retry = (
        retries and int(retries) > 0 and
        llm and isinstance(llm, dict) and
        callable(refactor_fn) and
        llm.get("editable_expanded")
    )

    if not can_retry:
        print(f"[post] cannot retry. Exiting.")
        return rc

    attempts = 0
    while rc != 0 and attempts < int(retries):
        attempts += 1
        try:
            _ensure_logdir()
            LAST_OUT.write_text(out or "", encoding="utf-8")
        except Exception as e:
            print(f"[post] failed to write last output: {e}")
            return rc

        ro_plus = list(llm.get("read_only_expanded", [])) + [LAST_OUT]
        ed_abs = llm.get("editable_expanded", [])
        if not ed_abs:
            print("[post] no editable files; cannot retry LLM")
            return rc

        print(f"[post] giving build output to LLM (retry {attempts}/{retries})")
        try:
            ok = refactor_fn(
                cfg={
                    "base_url": llm.get("base_url", ""),
                    "api_key":  llm.get("api_key", ""),
                    "model":    llm.get("model", ""),
                    "log": True,
                    "params": llm.get("params", {}),
                    "chunk_size": llm.get("chunk_size", "")
                },
                editable_files=ed_abs,
                read_only_files=ro_plus,
            )
            if not ok:
                print("[post] LLM retry returned failure; stopping retries")
                return rc
        except Exception as e:
            print(f"[post] LLM retry error: {e}")
            return rc

        rc, out = run_post_command(command, code_dir)
        log_post_output(command, code_dir, rc, out)
        print(f"[post] exit code: {rc}")

    return rc