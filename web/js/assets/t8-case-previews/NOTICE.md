# T8 case preview GIFs

This directory contains lightweight GIF previews bundled for the 60 non-official T8 selectors.

- 68 previews are included: 66 released case previews and 2 standalone community-Skill previews.
- They are human UI previews only. The node never connects or sends them as image, video, model, or LLM reference material.
- Files are deterministically indexed by `manifest.json`; both source and bundled SHA-256 values are pinned.
- The distributable encoding profile is 6 fps, maximum width 320 px, and a 64-color palette.
- Source videos are not included.

Regenerate the directory with `tools/bundle_t8_case_previews.py` whenever the selector catalog changes. Generate into an empty directory, validate the manifest and tests, then replace this directory as one reviewed change.
