# Third-party notices

## Local Qwen provider

The optional local provider installs and runs third-party components that are not
included in this Git repository:

- `Qwen3.8-27B-Q4_K_M.gguf` and `mmproj-F16.gguf` are downloaded from
  `unsloth/Qwen3.8-27B-GGUF` at the pinned revision recorded in
  `install_local_qwen.py`. The model repository declares Apache License 2.0.
- `llama.cpp` is installed from the pinned `b10436` release and is licensed under
  the MIT License by the llama.cpp contributors.
- Runtime installation is delegated to a SHA256-pinned copy of
  `chflame163/ComfyUI_Qwen_H3_Prompt/install_runtime.py` at commit
  `f8ea17991ea39111ef2b2ebdf6ccb631e21e0300`. That project is licensed under the
  MIT License. The downloaded installer and its runtime payload remain under the
  ignored local `runtime/` directory.

The GGUF files, llama.cpp binaries, caches, machine-specific configuration and
user content are intentionally excluded from this repository.
