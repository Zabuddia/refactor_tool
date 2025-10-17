import configparser, glob, sys
from pathlib import Path

CONF_FILE = "project.conf"

def die(msg):
    sys.exit(f"ERROR: {msg}")

def expand_list(s):
    return [t for t in (s or "").replace(";", " ").split() if t]

def expand_globs(patterns, base):
    toks = expand_list(patterns)
    out, seen = [], set()
    for t in toks:
        pat = str((base / t))
        hits = glob.glob(pat, recursive=True) or [pat]
        for h in hits:
            p = Path(h).resolve()
            k = str(p)
            if k not in seen:
                seen.add(k)
                out.append(p)
    return out

def load_config():
    if not Path(CONF_FILE).exists():
        die(f"missing {CONF_FILE}")

    cfg = configparser.ConfigParser()
    cfg.read(CONF_FILE)

    if "project" not in cfg:
        die("config must have [project] section")

    prj = cfg["project"]
    name = prj.get("name", "").strip()
    if not name:
        die("project.name is empty")

    code_dir = Path(prj.get("code_dir", ".")).expanduser()
    if not code_dir.is_absolute():
        code_dir = (Path.cwd() / code_dir).resolve()

    cmk = cfg["cmakelists"] if "cmakelists" in cfg else {}
    cps = cfg["cmakepresets"] if "cmakepresets" in cfg else {}
    llm = cfg["llm"] if "llm" in cfg else {}
    post = cfg["post"] if "post" in cfg else {}

    c_files_raw  = (cmk.get("c_files", "").strip() if hasattr(cmk, "get") else "")
    cpp_files_raw= (cmk.get("cpp_files", "").strip() if hasattr(cmk, "get") else "")

    ro_raw   = (llm.get("read_only_files", "").strip() if hasattr(llm, "get") else "")
    edit_raw = (llm.get("editable_files", "").strip()   if hasattr(llm, "get") else "")

    result = {
        "project": {
            "name": name,
            "code_dir": code_dir,
        },
        "cmakelists": {
            "c_files": expand_list(c_files_raw),
            "cpp_files": expand_list(cpp_files_raw),
            "c_files_expanded":  expand_globs(c_files_raw, code_dir),
            "cpp_files_expanded":expand_globs(cpp_files_raw, code_dir),
        },
        "cmakepresets": {
            "presets": expand_list(cps.get("presets", "") if hasattr(cps, "get") else ""),
            "output": (cps.get("output", "CMakePresets.json").strip() if hasattr(cps, "get") else "CMakePresets.json"),
        },
        "llm": {
            "base_url": (llm.get("base_url", "").strip() if hasattr(llm, "get") else "").rstrip("/"),
            "api_key":  (llm.get("api_key", "").strip()  if hasattr(llm, "get") else ""),
            "model":    (llm.get("model", "").strip()    if hasattr(llm, "get") else ""),
            "read_only_files": expand_list(ro_raw),
            "editable_files":  expand_list(edit_raw),
            "read_only_expanded": expand_globs(ro_raw, code_dir),
            "editable_expanded":  expand_globs(edit_raw, code_dir),
        },
        "post": {
            "command": (post.get("command", "").strip() if hasattr(post, "get") else ""),
        },
        "helpers": {
            "expand_globs": expand_globs,
            "expand_list": expand_list,
        },
    }

    return result