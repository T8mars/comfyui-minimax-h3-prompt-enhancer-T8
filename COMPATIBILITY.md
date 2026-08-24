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
- The optional `provider_config` socket is appended after every existing input.
  It has no serialized widget and defaults to `None`, so 1.0.x/1.1.x/1.2.0
  workflows keep their 31/35/38 widget arrays and original execution path.
- `T8LLMProviderConfig` and `T8PromptInspector` are additional utility node IDs;
  they do not replace, rename, or reorder the original three node registrations.
- A connected provider config does not mutate the original node widgets.
  Disconnecting it restores the saved per-node provider values immediately.

The migration contracts are covered by `tests/test_nodes.py`,
`tests/test_seedance20.py`, `tests/test_music3.py`, and
`tests/test_local_qwen.py`.
