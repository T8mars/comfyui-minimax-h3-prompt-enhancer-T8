# T8 case preview GIFs

This directory contains lightweight GIF previews bundled for the non-official T8 template library.

- 377 preview references are included: 375 released case previews and 2 standalone community-Skill previews.
- They are human UI previews only. The node never connects or sends them as image, video, model, or LLM reference material.
- Files are indexed by `manifest.json`; both source and bundled SHA-256 values are pinned.
- The distributable encoding profile is 2 fps, maximum width 160 px, and a 32-color palette.
- Source videos are not included.

This 377-preview directory is the frozen offline baseline for full GitHub clones. Generate complete candidates with `tools/bundle_t8_case_previews.py` in an external staging directory, validate them, and publish future preview growth only through the versioned dynamic asset channel; do not append new GIFs here.
