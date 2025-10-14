from __future__ import annotations
import configparser, glob, sys
from pathlib import Path
from typing import Dict, Any, List

CONF_FILE = "project.conf"

def die(msg: str) -> None:
    sys.exit(f"ERROR: {msg}")

def _get_bool(sec: configparser.SectionProxy | dict, key: str, default: bool) -> bool:
    v = (sec.get(key, "") if hasattr(sec, "get") else "") or ""
    v = v.strip().lower()
    if v in ("1", "true", "yes", "on"):  return True
    if v in ("0", "false", "no", "off"): return False
    return default

def expand_list(s: str) -> List[str]:
    """Space/semicolon tokenization (no globbing)."""
    return [t for t in s.replace(";", " ").split() if t]

def _expand_globs(patterns: str, base: Path) -> List[Path]:
    """Expand space/semicolon-separated globs relative to `base`; return absolute Paths."""
    toks = expand_list(patterns)
    out: List[Path] = []
    seen = set()
    for t in toks:
        pat = str((base / t))
        hits = glob.glob(pat, recursive=True) or [pat]
        for h in hits:
            p = Path(h).resolve()
            if str(p) not in seen:
                seen.add(str(p))
                out.append(p)
    return out

def load_config() -> Dict[str, Any]:
    if not Path(CONF_FILE).exists():
        die(f"missing {CONF_FILE}")

    cfg = configparser.ConfigParser()
    cfg.read(CONF_FILE)

    if "project" not in cfg or "llm" not in cfg:
        die("config must have [project] and [llm] sections")

    # ---- [project]
    prj = cfg["project"]
    project_name = prj.get("name", "").strip()
    if not project_name:
        die("project.name is empty")

    code_dir = Path(prj.get("code_dir", ".")).expanduser()
    if not code_dir.is_absolute():
        code_dir = (Path.cwd() / code_dir).resolve()

    # ---- [cmakelists] (optional)
    cmk = cfg["cmakelists"] if "cmakelists" in cfg else {}
    cmakelists = {
        "enable": _get_bool(cmk, "enable", False),
        "c_files": cmk.get("c_files", "").strip() if hasattr(cmk, "get") else "",
        "cpp_files": cmk.get("cpp_files", "").strip() if hasattr(cmk, "get") else "",
    }

    # ---- [cmakepresets] (optional)
    cps = cfg["cmakepresets"] if "cmakepresets" in cfg else {}
    cmakepresets = {
        "enable": _get_bool(cps, "enable", False),
        # list of preset names (space/semicolon separated); empty => keep ALL
        "presets": expand_list(cps.get("presets", "")) if hasattr(cps, "get") else [],
        "output": "CMakePresets.json",
    }

    # ---- [llm]
    llm = cfg["llm"]
    llm_cfg = {
        "enable": _get_bool(llm, "enable", True),
        "base_url": llm.get("base_url", "").rstrip("/"),
        "api_key": llm.get("api_key", "").strip(),
        "model": llm.get("model", "").strip(),
        "read_only_files": llm.get("read_only_files", "").strip(),
        "editable_files":  llm.get("editable_files", "").strip(),
    }
    if llm_cfg["enable"] and not llm_cfg["model"]:
        die("llm.model is empty")

    # ---- [post] (optional)
    post_cfg = {"enable": False, "command": ""}
    if "post" in cfg:
        post = cfg["post"]
        post_cfg = {
            "enable": _get_bool(post, "enable", False),
            "command": post.get("command", "").strip() if hasattr(post, "get") else "",
        }

    return {
        "project": {"name": project_name, "code_dir": code_dir},
        "cmakelists": { **cmakelists },
        "cmakepresets": { **cmakepresets },
        "llm": { **llm_cfg },
        "post": { **post_cfg },
        "helpers": {"expand_globs": _expand_globs},
    }