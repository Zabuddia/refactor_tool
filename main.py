from __future__ import annotations
from pathlib import Path
from typing import List
from config import load_config
from tools.cmake_lists import write_cmakelists
from tools.cmake_presets import write_cmakepresets
from tools.llm_refactor import refactor_with_context
from tools.post_cmd import run_post_command

def _rel_strings(paths: List[Path], base: Path) -> List[str]:
    out: List[str] = []
    for p in paths:
        try:
            out.append(p.relative_to(base).as_posix())
        except ValueError:
            out.append(p.as_posix())
    return out

def main() -> None:
    conf = load_config()

    project       = conf["project"]
    cmakelists    = conf["cmakelists"]
    cmakepresets  = conf["cmakepresets"]
    llm           = conf["llm"]
    expand_globs  = conf["helpers"]["expand_globs"]

    code_dir: Path = project["code_dir"]

    # ----- CMakeLists.txt (optional)
    if cmakelists["enable"]:
        c_files_abs   = expand_globs(cmakelists["c_files"],  code_dir)
        cpp_files_abs = expand_globs(cmakelists["cpp_files"], code_dir)

        write_cmakelists(
            project_name=project["name"],
            c_files=_rel_strings(c_files_abs, code_dir),
            cpp_files=_rel_strings(cpp_files_abs, code_dir),
            output=str(code_dir / "CMakeLists.txt"),
        )

    # ----- CMakePresets.json (optional)
    if cmakepresets["enable"]:
        write_cmakepresets(
            selected_presets=cmakepresets["presets"],   # [] => write ALL
            output=str(code_dir / cmakepresets["output"]),
        )

    # ----- LLM refactor (operate inside code_dir)
    if llm["enable"]:
        ro_files_abs = expand_globs(llm["read_only_files"], code_dir)
        ed_files_abs = expand_globs(llm["editable_files"],  code_dir)
        if ed_files_abs:
            refactor_with_context(
                llm_cfg=llm,
                editable_files=ed_files_abs,
                read_only_files=ro_files_abs,
            )
        else:
            print("[llm] no editable_files listed; skipping refactor")
    
    # ----- Post command
    if post["enable"]:
        post_cmd = conf["post"]["command"]
        if post_cmd:
            rc = run_post_command(post_cmd, code_dir)
            print(f"[post] exit code: {rc}")

    print("Done.")

if __name__ == "__main__":
    main()