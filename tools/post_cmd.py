from __future__ import annotations
import subprocess
from pathlib import Path

def run_post_command(command: str, code_dir: Path) -> int:
    """
    Run a single shell command in code_dir. Streams output to the console.
    Returns the process exit code.
    """
    if not command.strip():
        return 0
    print(f"[post] running in {code_dir}: {command}")
    # shell=True so '&&' works cross-platform (cmd.exe / sh)
    return subprocess.call(command, shell=True, cwd=str(code_dir))