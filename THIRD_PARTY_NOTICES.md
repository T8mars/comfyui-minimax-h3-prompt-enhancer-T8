# Third-party notices

## MiniMax official Skill resources

- `official_skills/h3-prompt-writing/` is pinned to MiniMax-AI/MiniMax-H3
  commit `d21241f0a4b3acbb34c97dae47fa417b7065e438`. Exact file and tree hashes
  are recorded in `official_skills/H3_SOURCE.json`.
- `official_skills/music-caption-rewriter/` is pinned to
  MiniMax-AI/MiniMax-Music3 commit
  `91410fb657c007ae57c60df8240f5ece5be089c7`. Its complete provenance is
  recorded in `official_skills/SOURCE.json`.
- The eight MiniMax-H3 creative prompt profiles and their human-facing preview
  assets are reviewed at MiniMax-AI/MiniMax-H3 commit
  `743d51e83329cbae6c7694f1c7b89576e7c25e07`. Upstream declares the complete
  Skills compatible with MiniMax Hub agent/canvas/hub tools; this project only
  adapts their prompt-writing constraints and does not port the full workflows.
  Preview hashes and encoding provenance are recorded in
  `web/js/assets/official-previews/manifest.json`.

Those official materials remain copyright MiniMax-AI and are not relicensed by
the T8 project license. They are bundled solely to implement the corresponding
official prompt-writing contracts with deterministic provenance.

## Local Qwen provider

The optional local provider installs and runs third-party components that are not
included in this Git repository:

- `Qwen3.8-27B-Q4_K_M.gguf` and `mmproj-F16.gguf` are downloaded from
  `unsloth/Qwen3.8-27B-GGUF` at the pinned revision recorded in
  `install_local_qwen.py`. The model repository declares Apache License 2.0.
- The optional `qwen3.8-27b-uncensored-fp8-q4_k_m.gguf` is downloaded from
  `theresa00l/Qwen3.8-27B-Uncensored-FP8-Q4_K_M-GGUF` at pinned revision
  `5bdf224e6f9b1e18c7598fea63e238e014ee8e3e`. Its LFS SHA256 is
  `66bb238d41de38b11dd406d932d8fb97433d529022cef60f2f422b9221cae743`.
  The repository declares Apache License 2.0 and identifies
  `orcarouter/Qwen3.8-27B-Uncensored-FP8` as the quantized source model. This
  third-party variant remains opt-in and does not replace the default model.
- `llama.cpp` is installed from the pinned `b10436` release and is licensed under
  the MIT License by the llama.cpp contributors.
- Runtime installation is delegated to a SHA256-pinned copy of
  `chflame163/ComfyUI_Qwen_H3_Prompt/install_runtime.py` at commit
  `f8ea17991ea39111ef2b2ebdf6ccb631e21e0300`. That project is licensed under the
  MIT License. The downloaded installer and its runtime payload remain under the
  ignored local `runtime/` directory.

The GGUF files, llama.cpp binaries, caches, machine-specific configuration and
user content are intentionally excluded from this repository.
