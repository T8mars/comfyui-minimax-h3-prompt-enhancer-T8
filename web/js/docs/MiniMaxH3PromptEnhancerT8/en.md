# MiniMax H3 Prompt Enhancer (T8)

Compiles the user's idea and connected media into MiniMax H3 prompt text using a pinned snapshot of the official `h3-prompt-writing` Skill.

## Notes

- The prompt is the only required creative input. Task type, duration, and shot count constrain the result together.
- Cloud providers can receive complete videos. Local GGUF models read timestamped visual samples and never analyze the video audio track.
- Models and mmproj files may live anywhere below `ComfyUI/models/LLM`; the node can rescan, auto-pair projectors, and reuse an installed llama-cpp-python runtime.
- API keys may be connected through the STRING socket or entered in the masked node control; a connected value wins.
- Official MiniMax presets and T8/community case templates are separate authority layers.
- GIFs are human-only UI previews and are never sent to an LLM or used as model reference media.

The node returns one `enhanced_prompt` STRING. Non-empty upstream content remains usable even when no complete official field set can be recognized.
