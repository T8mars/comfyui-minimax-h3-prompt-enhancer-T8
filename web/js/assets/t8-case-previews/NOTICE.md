# T8 case preview GIFs

This directory contains lightweight GIF previews bundled for the non-official T8 template library.

- 317 preview references are included: 315 released case previews and 2 standalone community-Skill previews.
- They are human UI previews only. The node never connects or sends them as image, video, model, or LLM reference material.
- Files are indexed by `manifest.json`; both source and bundled SHA-256 values are pinned.
- The distributable encoding profile is 2 fps, maximum width 160 px, and a 32-color palette.
- Source videos are not included.

Regenerate the directory with `tools/bundle_t8_case_previews.py` whenever the selector catalog changes. Generate into an empty directory, validate the manifest and tests, then replace this directory as one reviewed change.
