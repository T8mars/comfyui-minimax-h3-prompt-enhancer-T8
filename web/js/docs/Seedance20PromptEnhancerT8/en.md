# Seedance 2.0 Prompt Enhancer (T8)

Produces Seedance 2.0 prompt text from a task intent, media roles, reference syntax, and shot organization.

- Accepts text, images, and videos. Local Qwen uses visual frame samples and does not read audio tracks.
- AUTO can choose intent, duration, complexity, and shot count. A fixed 1–20 shot count is a soft constraint.
- Images may be sent inline as Base64. OpenAI-compatible mode can use one URL per connected video.
- T8 templates transfer reusable Creative DNA only; source characters, plots, copy, and media are not model inputs.

The node returns one `enhanced_prompt` STRING and preserves non-empty upstream content even when exact length or formatting targets are missed.
