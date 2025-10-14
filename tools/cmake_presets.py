from __future__ import annotations
import json
from pathlib import Path
from typing import Dict, List, Any, Set

# Master template (full superset); we’ll prune based on selected names.
def _master_template() -> Dict[str, Any]:
    return {
      "version": 6,
      "cmakeMinimumRequired": { "major": 3, "minor": 24, "patch": 0 },

      "configurePresets": [
        {
          "name": "base", "hidden": True, "generator": "Ninja",
          "binaryDir": "${sourceDir}/out/build/${presetName}",
          "cacheVariables": {
            "ENABLE_IPP": "ON",
            "ENABLE_WARNINGS_AS_ERRORS": "OFF",
            "ENABLE_LTO": "OFF",
            "ENABLE_ASAN_UBSAN": "OFF",
            "ENABLE_COVERAGE": "OFF"
          }
        },
        {
          "name": "linux-base", "hidden": True, "inherits": "base",
          "condition": { "type": "notEquals", "lhs": "${hostSystemName}", "rhs": "Windows" },
          "cacheVariables": { "CMAKE_PREFIX_PATH": "/opt/intel/oneapi/ipp/latest/lib/cmake" }
        },
        {
          "name": "ninja-gcc-debug", "displayName": "Ninja + GCC (Debug, Linux)", "inherits": "linux-base",
          "cacheVariables": { "CMAKE_BUILD_TYPE": "Debug",   "CMAKE_C_COMPILER": "cc",    "CMAKE_CXX_COMPILER": "c++" }
        },
        {
          "name": "ninja-gcc-release", "displayName": "Ninja + GCC (Release, Linux)", "inherits": "linux-base",
          "cacheVariables": { "CMAKE_BUILD_TYPE": "Release", "CMAKE_C_COMPILER": "cc",    "CMAKE_CXX_COMPILER": "c++", "ENABLE_LTO": "ON" }
        },
        {
          "name": "ninja-clang-debug", "displayName": "Ninja + Clang (Debug, Linux)", "inherits": "linux-base",
          "cacheVariables": { "CMAKE_BUILD_TYPE": "Debug",   "CMAKE_C_COMPILER": "clang", "CMAKE_CXX_COMPILER": "clang++" }
        },
        {
          "name": "ninja-clang-release", "displayName": "Ninja + Clang (Release, Linux)", "inherits": "linux-base",
          "cacheVariables": { "CMAKE_BUILD_TYPE": "Release", "CMAKE_C_COMPILER": "clang", "CMAKE_CXX_COMPILER": "clang++", "ENABLE_LTO": "ON" }
        },

        {
          "name": "win-base", "hidden": True, "inherits": "base",
          "condition": { "type": "equals", "lhs": "${hostSystemName}", "rhs": "Windows" },
          "cacheVariables": {
            "CMAKE_PREFIX_PATH": "C:/Program Files (x86)/Intel/oneAPI/ipp/latest/lib/cmake",
            "CMAKE_MSVC_RUNTIME_LIBRARY": "MultiThreadedDebugDLL"
          }
        },
        {
          "name": "ninja-clangcl-debug", "displayName": "Ninja + clang-cl (Debug, Windows)", "inherits": "win-base",
          "cacheVariables": {
            "CMAKE_BUILD_TYPE": "Debug",
            "CMAKE_C_COMPILER": "C:/Program Files/LLVM/bin/clang-cl.exe",
            "CMAKE_CXX_COMPILER": "C:/Program Files/LLVM/bin/clang-cl.exe",
            "CMAKE_RC_COMPILER": "C:/Program Files/LLVM/bin/llvm-rc.exe",
            "CMAKE_MT":          "C:/Program Files/LLVM/bin/llvm-mt.exe"
          }
        },
        {
          "name": "ninja-clangcl-release", "displayName": "Ninja + clang-cl (Release, Windows)",
          "inherits": "ninja-clangcl-debug",
          "cacheVariables": { "CMAKE_BUILD_TYPE": "Release", "ENABLE_LTO": "ON" }
        },
        {
          "name": "vs-clangcl-debug", "displayName": "VS 2022 + ClangCL (Debug, Windows)",
          "generator": "Visual Studio 17 2022",
          "binaryDir": "${sourceDir}/out/build/${presetName}",
          "condition": { "type": "equals", "lhs": "${hostSystemName}", "rhs": "Windows" },
          "cacheVariables": {
            "CMAKE_PREFIX_PATH": "C:/Program Files (x86)/Intel/oneAPI/ipp/latest/lib/cmake",
            "CMAKE_GENERATOR_TOOLSET": "ClangCL"
          }
        },
        {
          "name": "vs-msvc-debug", "displayName": "VS 2022 + MSVC (Debug, Windows)",
          "generator": "Visual Studio 17 2022",
          "binaryDir": "${sourceDir}/out/build/${presetName}",
          "condition": { "type": "equals", "lhs": "${hostSystemName}", "rhs": "Windows" },
          "cacheVariables": {
            "CMAKE_PREFIX_PATH": "C:/Program Files (x86)/Intel/oneAPI/ipp/latest/lib/cmake"
          }
        }
      ],

      "buildPresets": [
        { "name": "ninja-gcc-debug",       "configurePreset": "ninja-gcc-debug" },
        { "name": "ninja-gcc-release",     "configurePreset": "ninja-gcc-release" },
        { "name": "ninja-clang-debug",     "configurePreset": "ninja-clang-debug" },
        { "name": "ninja-clang-release",   "configurePreset": "ninja-clang-release" },

        { "name": "ninja-clangcl-debug",   "configurePreset": "ninja-clangcl-debug" },
        { "name": "ninja-clangcl-release", "configurePreset": "ninja-clangcl-release" },
        { "name": "vs-clangcl-debug",      "configurePreset": "vs-clangcl-debug", "configuration": "Debug" },
        { "name": "vs-msvc-debug",         "configurePreset": "vs-msvc-debug",    "configuration": "Debug" }
      ],

      "testPresets": [
        { "name": "ninja-gcc-debug",       "configurePreset": "ninja-gcc-debug",       "output": { "outputOnFailure": True } },
        { "name": "ninja-gcc-release",     "configurePreset": "ninja-gcc-release",     "output": { "outputOnFailure": True } },
        { "name": "ninja-clang-debug",     "configurePreset": "ninja-clang-debug",     "output": { "outputOnFailure": True } },
        { "name": "ninja-clang-release",   "configurePreset": "ninja-clang-release",   "output": { "outputOnFailure": True } },

        { "name": "ninja-clangcl-debug",   "configurePreset": "ninja-clangcl-debug",   "output": { "outputOnFailure": True } },
        { "name": "ninja-clangcl-release", "configurePreset": "ninja-clangcl-release", "output": { "outputOnFailure": True } },
        { "name": "vs-clangcl-debug",      "configurePreset": "vs-clangcl-debug",      "output": { "outputOnFailure": True }, "configuration": "Debug" },
        { "name": "vs-msvc-debug",         "configurePreset": "vs-msvc-debug",         "output": { "outputOnFailure": True }, "configuration": "Debug" }
      ],

      "workflowPresets": [
        {
          "name": "ci-win-debug",
          "steps": [
            { "type": "configure", "name": "ninja-clangcl-debug" },
            { "type": "build",     "name": "ninja-clangcl-debug" },
            { "type": "test",      "name": "ninja-clangcl-debug" }
          ]
        },
        {
          "name": "ci-linux-gcc-debug",
          "steps": [
            { "type": "configure", "name": "ninja-gcc-debug" },
            { "type": "build",     "name": "ninja-gcc-debug" },
            { "type": "test",      "name": "ninja-gcc-debug" }
          ]
        },
        {
          "name": "ci-linux-clang-debug",
          "steps": [
            { "type": "configure", "name": "ninja-clang-debug" },
            { "type": "build",     "name": "ninja-clang-debug" },
            { "type": "test",      "name": "ninja-clang-debug" }
          ]
        },
        {
          "name": "ci-vs-msvc-debug",
          "steps": [
            { "type": "configure", "name": "vs-msvc-debug" },
            { "type": "build",     "name": "vs-msvc-debug" },
            { "type": "test",      "name": "vs-msvc-debug" }
          ]
        }
      ]
    }

def _prune_presets(doc: Dict[str, Any], selected: List[str]) -> Dict[str, Any]:
    """
    Keep only the selected configure preset names. Build/test/workflow entries are
    filtered to those whose referenced preset names remain valid. Hidden bases
    (base/linux-base/win-base) are auto-kept if they are inherited by any kept preset.
    If selected is empty -> keep everything.
    """
    if not selected:
        return doc

    sel: Set[str] = set(selected)

    # 1) Configure presets: keep selected + their inheritance chain (base nodes).
    name_to_cfg = {p["name"]: p for p in doc.get("configurePresets", [])}
    keep_cfg: Set[str] = set()

    def mark_chain(name: str):
        if name in keep_cfg or name not in name_to_cfg:
            return
        keep_cfg.add(name)
        inherits = name_to_cfg[name].get("inherits")
        if isinstance(inherits, str):
            for parent in inherits.split(";"):
                mark_chain(parent.strip())
        elif isinstance(inherits, list):
            for parent in inherits:
                mark_chain(parent)

    for n in sel:
        mark_chain(n)

    doc["configurePresets"] = [p for p in doc.get("configurePresets", []) if p["name"] in keep_cfg]

    # 2) Build presets: keep if configurePreset in selected set
    doc["buildPresets"] = [
        p for p in doc.get("buildPresets", [])
        if p.get("configurePreset") in sel
    ]

    # 3) Test presets: same filter
    doc["testPresets"] = [
        p for p in doc.get("testPresets", [])
        if p.get("configurePreset") in sel
    ]

    # 4) Workflows: keep only those whose steps all reference available items
    valid_step_names = set()
    valid_step_names.update(p["name"] for p in doc["buildPresets"])
    valid_step_names.update(p["name"] for p in doc["testPresets"])
    valid_step_names.update(keep_cfg)  # configure preset names are valid configure step names

    pruned_workflows = []
    for wf in doc.get("workflowPresets", []):
        steps = wf.get("steps", [])
        if steps and all(step.get("name") in valid_step_names for step in steps):
            pruned_workflows.append(wf)
    doc["workflowPresets"] = pruned_workflows

    return doc

def write_cmakepresets(selected_presets: List[str], output: str = "CMakePresets.json") -> None:
    doc = _master_template()
    doc = _prune_presets(doc, selected_presets)
    # Ensure output directory exists (in case a full path is provided)
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps(doc, indent=2), encoding="utf-8")
    print(f"[presets] wrote -> {output} ({'all' if not selected_presets else ','.join(selected_presets)})")