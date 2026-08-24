# T8 Shared LLM Provider Config

Optional shared configuration for all three T8 enhancer nodes. Connect `provider_config` to centralize the provider, model, OpenAI Base URL, local Qwen options, temperature policy, and allowlisted extra parameters.

The optional shared-provider socket is a dedicated configuration type, not a `STRING`. Add `T8 LLM Provider Config` and connect its output to the green shared-provider input. `Local Qwen` requires no API key; models are discovered recursively below `ComfyUI/models/LLM`, H3 and Seedance can AUTO-pair an mmproj, and Music 3 loads the text model only.

- Leaving it disconnected preserves the original node behavior and old workflows.
- A connected or saved `api_key` on the enhancer node takes priority over a credential alias.
- Workflows store only the alias; the real secret stays in the ComfyUI user directory.
- Unknown OpenAI-compatible endpoints are not assumed to support images or video. Use the provider capability preflight first.
- Extra parameters cannot replace core fields such as `model`, `messages`, `stream`, or `temperature`.

Disconnect the socket to restore the original per-node fields.
