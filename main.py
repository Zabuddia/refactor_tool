from pathlib import Path
import argparse, sys
from config import load_config
from tools.cmakelists_tool import write_cmakelists
from tools.cmakepresets_tool import write_cmakepresets
from tools.llm_refactor_tool import refactor_with_context
from tools.post_cmd_tool import run_post_command

def _rel_strings(paths, base):
    out = []
    for p in paths:
        p = Path(p)
        try:
            out.append(p.relative_to(base).as_posix())
        except ValueError:
            out.append(p.as_posix())
    return out

def main():
    ap = argparse.ArgumentParser(description="Generate CMake files, refactor with LLM, then run an optional post command.")
    ap.add_argument("--config", default="project.conf", help="Path to project.conf (default: project.conf)")
    ap.add_argument("--skip", nargs="*", choices=["cmakelists","presets","llm","post"], default=[],
                    help="Skip one or more steps")
    args = ap.parse_args()

    import config
    config.CONF_FILE = args.config

    conf = load_config()
    project      = conf["project"]
    cmakelists   = conf["cmakelists"]
    cmakepresets = conf["cmakepresets"]
    llm          = conf["llm"]
    post         = conf["post"]

    code_dir = Path(project["code_dir"])

    # ---- CMakeLists
    if "cmakelists" not in args.skip:
        c_abs   = cmakelists.get("c_files_expanded", [])
        cpp_abs = cmakelists.get("cpp_files_expanded", [])
        if c_abs or cpp_abs:
            write_cmakelists(
                project_name=project["name"],
                c_files=_rel_strings(c_abs, code_dir),
                cpp_files=_rel_strings(cpp_abs, code_dir),
                output=str(code_dir / "CMakeLists.txt"),
            )

    # ---- Presets
    if "presets" not in args.skip:
        write_cmakepresets(
            selected_presets=cmakepresets.get("presets", []),
            output=str(code_dir / cmakepresets.get("output", "CMakePresets.json")),
        )

    # ---- LLM (only fail-fast step)
    if "llm" not in args.skip:
        ro_abs = llm.get("read_only_expanded", [])
        ed_abs = llm.get("editable_expanded", [])
        if ed_abs:
            try:
                ok = refactor_with_context(
                    cfg={
                        "base_url": llm.get("base_url", ""),
                        "api_key":  llm.get("api_key", ""),
                        "model":    llm.get("model", ""),
                        "log": True,
                        "params": llm.get("params", {}),
                    },
                    editable_files=ed_abs,
                    read_only_files=ro_abs,
                )
                if not ok:
                    print("[llm] refactor failed — aborting remaining steps.")
                    sys.exit(1)
            except Exception as e:
                print(f"[llm] failed: {e}")
                print("[llm] aborting remaining steps.")
                sys.exit(1)
        else:
            print("[llm] no editable files; skipping refactor")

    # ---- Post command (only runs if LLM succeeded or was skipped)
    if "post" not in args.skip:
        cmd = post.get("command", "")
        if cmd:
            rc = run_post_command(cmd, code_dir)
            print(f"[post] exit code: {rc}")

    print("Done.")

if __name__ == "__main__":
    main()