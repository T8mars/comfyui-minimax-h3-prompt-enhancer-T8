# Security Policy

## Supported versions

Security fixes are applied to the latest published Comfy Registry/GitHub release. Users should update before reporting a defect.

## Reporting a vulnerability

Do not put API keys, private prompts, lyrics, media, provider response bodies, local paths, or unpublished model files in a public issue. Use GitHub's private vulnerability reporting for this repository when available, or contact the maintainer through the email listed in `pyproject.toml`.

Include the node version, ComfyUI version, operating system, provider mode, redacted error category, and minimal reproduction steps. The local diagnostics endpoint intentionally excludes request bodies, secrets, media, URLs, and model reasoning.

## Secret handling

Example workflows never contain API keys. The repository release gate rejects tracked API-key patterns, GGUF files, runtime state, and `roadmap.md`. GIF previews are human-only UI assets and are never sent to an LLM.
