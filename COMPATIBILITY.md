# Workflow compatibility matrix

The current compatibility contract keeps all three public node IDs and output names stable. Frontend
migrations run only while an existing workflow is configured; newly saved
workflows use the current deterministic widget order.

| Node ID | Current serialized widgets | Accepted 1.0.x layouts | Migration behavior | Stable outputs |
| --- | ---: | --- | --- | --- |
| `MiniMaxH3PromptEnhancerT8` | 31 | 16, 17, 19, or 21 values | Inserts the historical shot-count, official-profile/preset, AI-Workshop model, and case-template defaults in sequence; all later 1.1 local-model controls use schema defaults. A removed `openai_upload_url` is not reused as a video URL. | `enhanced_prompt` |
| `Seedance20PromptEnhancerT8` | 35 | 23 or 25 values | Inserts the AI-Workshop model fields and case-template default; later 1.1 local-model controls use schema defaults. A removed `openai_upload_url` is not reused as a video URL. | `enhanced_prompt` |
| `MiniMaxMusic3PromptEnhancerT8` | 38 | Both published-order and ComfyUI runtime-order 31-value layouts | Detects the old layout from the API-mode position, maps values by widget name, then appends 1.1 local-model controls with defaults. | `lyrics`, `music_caption`, `music3_payload_json`, `enhancement_report_json` |

Compatibility invariants:

- Node IDs, categories, socket names, and output order do not change in 1.1.
- Existing case-template human names and stable IDs resolve to the same case.
- Existing API-key `STRING` links remain authoritative over the hidden widget.
- Missing new controls receive safe defaults; migrations never copy an obsolete
  upload endpoint into `openai_video_urls`.
- A workflow saved by 1.1 is not promised to load in older 1.0.x code because
  older code does not know the new local-provider controls.
- The optional `provider_config` socket remains after every existing serialized input. H3 and
  Seedance keep the existing connection-only `performance_director_config` immediately before it,
  then append the new `character_performance_bible` after it; Music 3 does not. None of these
  Custom Type sockets adds a serialized widget,
  so 1.0.x/1.1.x/1.2.0 workflows keep their 31/35/38 widget arrays and original provider path.
  An unconnected performance config uses conditional `AUTO`: it can improve character/acting
  requests but explicitly skips non-performance intent. Connecting `Off` restores the former
  prompt compiler without the performance-directing section.
- `T8LLMProviderConfig`, `T8PerformanceDirectorConfig`, `T8FilmProjectRouter`,
  `T8CharacterPerformanceBible`, `T8CharacterPerformanceBibleStack`, `T8PromptInspector`,
  `T8PromptText`, and `T8ShowText`
  are additional utility node IDs;
  they do not replace, rename, or reorder the original three node registrations.
- The multi-character Stack keeps the existing `T8_CHARACTER_PERFORMANCE_BIBLE` socket type,
  so the H3/Seedance/Storyboard connection contract stays compatible with a single Bible.
- Film Project Router adds only an optional connection-only `previous_state` socket. Existing
  serialized widgets retain their order, while a connected prior state can inherit blank project facts.
  Entering `[清空继承]` or `[CLEAR_INHERITED]` in one inheritable text widget clears only that field,
  without adding a widget or changing the saved input/connection order.
- Long-form and Storyboard also append their new project-state/character sockets after every prior
  socket, preserving the target-slot numbers of existing provider and performance-config links.
- Long-form and Storyboard contract cards use non-serialized DOM widgets and `ui` metadata only;
  output sockets, return order, and paid-request count remain unchanged. The cards follow `Comfy.Locale`
  and use bounded adaptive height instead of a clipping fixed height.
- Long-form and Storyboard append one serialized `contract_failure_policy` combo after every existing
  input. Missing values execute with compatibility-warning behavior; the strict option uses ComfyUI's
  native `ExecutionBlocker` only after a paid response fails the local contract, while retaining UI and
  JSON diagnostics. Existing socket positions and all output positions remain unchanged.
- A connected provider config does not mutate the original node widgets.
  Disconnecting it restores the saved per-node provider values immediately.
- Legacy H3 21/22-value, Seedance 25/26-value, and Music 31-value arrays are
  expanded with valid local-Qwen defaults before ComfyUI validates combo values.
  This prevents the historical seed control value `randomize` from being read as
  `local_model`; current 31/35/38-value workflows remain unchanged.
- The historical API-mode value `本地 Qwen3.8-27B（GGUF，离线）` remains an
  accepted execution alias for the current generic local-GGUF label.
- Historical bare filenames still resolve in `models/LLM/Qwen3.8`; new models
  may use recursive `models/LLM` relative paths, so duplicate basenames never
  silently select an arbitrary file.
- Existing explicit `mmproj-F16.gguf` values remain valid. New nodes default to
  metadata-based `AUTO（自动匹配）` without adding or reordering serialized
  widgets.
- The H3 `duration_seconds` widget keeps its existing integer value and
  serialized position while dropping only the old upper bound. Seedance keeps
  the same widget name and serialized position; its former combo value is now
  restored into an editable text field, so saved `AUTO` and `4`–`30` values
  remain valid while new positive integers above 30 are preserved unchanged.
- Bundled workflows use the repository's own `T8PromptText` and `T8ShowText`
  STRING utilities, so text entry and result display do not require Comfyroll or
  EasyUse.

The migration contracts are covered by `tests/test_nodes.py`,
`tests/test_seedance20.py`, `tests/test_music3.py`, and
`tests/test_local_qwen.py`.
