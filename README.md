# AI Refactor Toolsuite

A lightweight, modular toolsuite for automating C/C++ project setup and AI-powered code refactoring.

It can:
- Generate consistent **CMakeLists.txt** and **CMakePresets.json**
- Use an **LLM** (local or remote) to refactor code safely
- Optionally run a **post-command** (build/test step)
- Work entirely declaratively from a single `project.conf`

---

## 🧱 Project Structure

```
refactor_tool/
├── main.py                     # Entry point orchestrating all steps
├── config.py                   # Old config loader (superseded by config_tool.py)
├── project.conf                # Active project configuration
├── example-project.conf        # Example config
├── llm_log.txt                 # Logs of LLM prompts and replies
├── shell.nix                   # Nix shell environment
└── tools/
    ├── cmakelists_tool.py      # Writes CMakeLists.txt
    ├── cmakepresets_tool.py    # Writes CMakePresets.json
    ├── llm_refactor_tool.py    # Handles AI-based refactoring
    ├── post_cmd_tool.py        # Runs post build/test command
    └── __init__.py
```

---

## ⚙️ Installation (NixOS or Linux)

Enter a Nix shell with Python + dependencies:

```bash
nix-shell
```

This gives you `python3` and `requests`, everything the tools need.

---

## 🧩 Configuration

The toolsuite reads all settings from `project.conf` (or a path you pass with `--config`).

Example:

```ini
[project]
name = AddC_32f_I
code_dir = ../AddC_32f_I

[cmakelists]
c_files   = c_AddC_32f_I.c
cpp_files = test_a_AddC_32f_I.cpp

[cmakepresets]
presets = ninja-clang-debug ninja-clangcl-debug
output  = CMakePresets.json

[llm]
base_url = https://openrouter.ai/api/v1
api_key  = sk-your-api-key
model    = openai/gpt-oss-20b
read_only_files = instructions.md
editable_files  = hello_world.c

[post]
command = cmake --workflow --preset ci-win-debug
```

---

## 🚀 Usage

### Run the full workflow
```bash
python3 main.py
```

This will:
1. Generate `CMakeLists.txt`
2. Generate `CMakePresets.json`
3. Refactor listed editable files with context from read-only files
4. Run your post command (if defined)

### Skip certain steps
```bash
python3 main.py --skip llm post
```

---

## 🧠 LLM Integration

The refactor tool uses an OpenAI-compatible API endpoint.  
You can point it to:
- **OpenRouter** (`https://openrouter.ai/api/v1`)
- **Local models** (e.g. `http://localhost:8000/v1` with `llama.cpp`, Ollama, etc.)

The assistant follows strict rules:
- For `.c`: emits valid ISO C11 code  
- For `.cpp`: emits C++17 code  
- Preserves observable behavior  
- Wraps output between `<<<BEGIN FILE>>>` and `<<<END FILE>>>`

Logs of every exchange are saved in `llm_log.txt`.

---

## 🧩 Extending the Toolsuite

Each tool is modular:
- `_build_request()` and `_parse_reply()` in `llm_refactor_tool.py` can be swapped for JSON-mode responses later.
- Add new generators under `tools/` (e.g., `tests_tool.py`) and hook them in `main.py`.
- The configuration loader (`config_tool.py`) already handles list + glob expansion.

---

## 🧰 Tips

- Use `example-project.conf` as a template for new projects.
- `CMakePresets.json` name can be changed if generating multiple variants.
- For debugging, set `base_url` to a mock LLM or log-only endpoint.
- The tools never overwrite files unless content changes.

---

**Created by:** Alan Fife