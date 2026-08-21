# MiniMax Music 3 Prompt & Lyrics Enhancer (T8)

This is a text-only node; it does not generate or listen to audio. Lyrics and the official Music 3 structured caption are separate outputs.

- `lyrics`: generated, preserved, selectively edited, or empty for instrumental mode.
- `music_caption`: the official `Global Metadata / Vocal Details / Arrangement` structure, English by default.
- `music3_payload_json`: Music 3 `input` and `instructions` fields.
- `enhancement_report_json`: redacted stage and quality diagnostics without API keys, full lyrics, or template bodies.

Official Full mode follows progressive disclosure and selects at most two genre indexes and three role-distinct templates. Lyrics writing/editing is a clearly labeled T8 capability, not an official Skill feature.
