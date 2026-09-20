# Qwen Image 2.1 Prompt Enhancer

Use this node before an image-generation or image-editing node.

- Choose **Text-to-image** and leave the ordered image inputs empty for a text-only brief.
- Choose **Image edit** when connecting one to ten ordered `IMAGE` inputs. Every connected image is preserved in the request; the node never silently drops an image.
- `Maximum prompt characters = 0` lets the model choose the complete Skill-compliant length. A nonzero limit requests one bounded correction and never cuts a sentence locally.
- `auto` lets the Skill choose its horizontal or vertical ratio. A fixed ratio is returned in `wh_ratio` and is never repeated in the prose.
- Enable **Transparent RGBA** only when the finished image needs an alpha channel and a transparent background.

The default cloud route is ZhenZhen Affordable AI Shop with model
`qwen/qwen3.8-flash-next`. The shared provider configuration can switch to AI
Workshop, an OpenAI-compatible endpoint, or local GGUF. Cloud requests use an
8192-token budget by default (including reasoning); an explicit
`max_tokens`/`max_completion_tokens` setting takes precedence.

Outputs are the rewritten English prompt, the chosen aspect ratio, a redacted
request description, and a redacted enhancement report. API keys and response
bodies are never written to those outputs.
