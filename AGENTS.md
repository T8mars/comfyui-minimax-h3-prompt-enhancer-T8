# Repository maintenance instructions

## GitHub push and Comfy Registry versioning

- Before every authorized `git push` to a GitHub remote, update `[project].version` in `pyproject.toml` first and include that version change in the same push. Never push while the local version still matches the version already present on `origin/main`.
- Use semantic versioning and never reuse, decrease, or overwrite a version that has reached the Comfy Registry:
  - documentation, metadata, bug fixes, case-library refreshes, preview updates, and other compatible maintenance: increment `PATCH`;
  - backward-compatible features or new capabilities: increment `MINOR`;
  - breaking workflow, node ID, input/output, or compatibility changes: increment `MAJOR`.
- If one push contains several change types, use the highest applicable increment. When uncertain, default to a `PATCH` increment rather than pushing without a new version.
- Before pushing, parse `pyproject.toml`, confirm the new version is valid `X.Y.Z`, check that it is newer than both `origin/main` and the latest Registry version, run the relevant tests and secret scan, and confirm `roadmap.md`, API keys, local runtime state, and GGUF files are not staged.
- A `pyproject.toml` change triggers `.github/workflows/publish_action.yml`; after pushing, verify the GitHub Action and the corresponding Comfy Registry version instead of treating `git push` alone as a completed release.
