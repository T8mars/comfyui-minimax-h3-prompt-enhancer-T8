# MiniMax H3 Prompt Enhancer (T8)

Compiles the user's idea and connected media into MiniMax H3 prompt text using a pinned snapshot of the official `h3-prompt-writing` Skill.

## Notes

- **Hybrid** requires first and/or last frame plus an additional reference image/video. One image per slot; up to nine extra images plus two keyframes and three videos. Picture order is first, last, then numeric reference slots; videos are numbered independently. Extra references never silently become keyframes. No audio track is analyzed.
- Hybrid uses six reference fields with the existing providers, local visual GGUF and Relay. Five old tasks, defaults and 38 saved fields are unchanged. Structural checks cannot verify pixels, video facts or rendered quality; review the result. Downstream resource limits still apply.
- The prompt is the only required creative input. Task type, duration, and shot count constrain the result together.
- Cloud providers can receive complete videos. Local GGUF models read timestamped visual samples and never analyze the video audio track.
- Models and mmproj files may live anywhere below `ComfyUI/models/LLM`; the node can rescan, auto-pair projectors, and reuse an installed llama-cpp-python runtime.
- API keys may be connected through the STRING socket or entered in the masked node control; a connected value wins.
- Official MiniMax presets and T8/community case templates are separate authority layers.
- GIFs are human-only UI previews and are never sent to an LLM or used as model reference media.

The primary output is `enhanced_prompt` STRING, alongside the existing Relay global/local/time/length/report ports. Hybrid retains Relay timing; padding only holds the achieved ending. Off preserves non-empty upstream content even without a complete field set. Check/Repair retain a complete draft on failure and report unresolved issues instead of claiming success.
