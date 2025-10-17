import subprocess
from pathlib import Path

def run_post_command(command, code_dir):
    if not command.strip():
        return 0
    print(f"[post] running in {code_dir}: {command}")
    return subprocess.call(command, shell=True, cwd=str(code_dir))