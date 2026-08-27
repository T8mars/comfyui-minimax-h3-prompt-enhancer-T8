# T8 case preview GIFs

This directory contains lightweight GIF previews bundled for the non-official T8 template library.

- 277 preview references are included: 275 released case previews and 2 standalone community-Skill previews.
- They are human UI previews only. The node never connects or sends them as image, video, model, or LLM reference material.
- Files are indexed by `manifest.json`; both source and bundled SHA-256 values are pinned.
- The distributable encoding profile is 2 fps, maximum width 180 px, and a 32-color palette.
- Source videos are not included.

Regenerate this directory whenever the selector catalog changes, then validate the manifest and repository release gates before publishing.
