# MOSS collection / per-reference authoring

For generation, connect **T8 LLM Provider Config → provider_config**, enter a brief
and the actual canvas. This node writes prompts, not images. It is separate from
the H3/Seedance storyboard configuration.

## Choose a profile

- **Comic**: 1–16 pages, or 0 for automatic planning. One collection plan, then an
  English source and Chinese caption mapping per page. References are shared
  context, not one book per image. Geometry, labels, reading order and exact visible
  text are shared across both languages.
- **Fisher**: default `independent` creates one complete unit per reference, or one
  unit without images. Explicit `fusion` alone combines references into one image.
  It generates one selected descriptive language; Auto defaults to Chinese.
  Without a short/length constraint, automatic Chinese prefers roughly 1500–2500
  Han characters. This is a soft creative preference, not a minimum quota.

At most ten images after slot/batch expansion, in that order. Cloud providers
receive the brief, context and references, possibly through uploads. Local ComfyUI
does not imply a local model: explicitly choose the provider in shared config.

## Wire outputs and budget calls

Output 0 `bundle_json` → **MOSS Authoring Page T8**. Select its 1-based page and
`en/zh`. **Only Page output 0 goes to positive; outputs 1/2 are INT width/height.**
Bundles, reading copies, source drafts and reports are never positive prompts.

Before corrections: Comic N pages uses `1 + 2N` logical calls; Fisher N units uses
N calls; fusion uses one. Each stage permits at most one additional correction
(or zero), not automatic retries after network failures. The soft character cap
counts descriptive Unicode code points per unit/language, excluding Layout
visible copy, JSON and coordinates. It is not Tokens and never truncates a draft.

## Revisions, recovery and failures

Put explicit human continuity facts in `continuity_context`. Revision JSON has
exactly `schema_version="t8-moss-authoring-context/v1"`, `mode="full_layout"` or
`"panels_only"`, `bundle` containing the complete prior bundle object, and
`edit_unit_ids` listing its actual stable IDs, not page indices. The repository
guide `docs/moss-image.md` includes a complete parseable JSON example.

With `preserve_layout=true`, full_layout locks non-caption structure;
panels_only locks comic frames, canvas and reading order. Existing visible text
stays exact even with layout preservation disabled. Reattach the exact original
ordered references. Unselected units are copied unchanged. An empty outer edit
list is a zero-call copy requiring no provider, brief or reloaded images.

Restore returns an old complete result without generation. In-process cache:
at most 50 slots, at most one hour; restart/eviction can remove it. Failure never
overwrites or renews last-good success. Restore skips irrelevant lazy branches,
not host static validation. Failed-draft inspection is same-origin/read-only,
never queues, and remains `inspection_only=true`, `complete=false`: not a bundle
for Page. Same-origin is not multi-user isolation; avoid secrets/sensitive inputs.

Shared geometry does not prove translation semantics or rendered quality. The
target 4096-token budget is unmeasured; no live-LLM aesthetic benefit is claimed.
Review the sources, then verify actual MOSS images.
