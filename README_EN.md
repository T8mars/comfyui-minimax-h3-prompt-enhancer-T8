<p align="right">
  <a href="./README.md">简体中文</a> | <strong>English</strong>
</p>

# ComfyUI MiniMax H3 / Seedance 2.0 / Music 3 Prompt Enhancer T8

A ComfyUI node suite for improving MiniMax H3 and Seedance 2.0 video prompts and preparing MiniMax Music 3 lyrics and structured music captions. The H3 and Seedance nodes accept text plus real ComfyUI `IMAGE` and `VIDEO` inputs. The Music 3 node is text-only and returns lyrics, an official structured caption, a downstream-ready payload, and a redacted enhancement report as separate outputs.

The three core nodes can use ZhenZhen Affordable AI Shop, ZhenZhen AI Workshop, a user-supplied OpenAI-compatible endpoint, or a local llama.cpp-compatible GGUF model. Provider transport and error handling are shared, while the prompt contracts remain isolated for each target model.

> The repository homepage intentionally remains Chinese through [`README.md`](./README.md). Use the language switch above to move between the Chinese and English guides.

## Service entry points

| Service | Best for | Open |
| --- | --- | --- |
| ZhenZhen Affordable AI Shop (Mainland China) | Mainland users and domestic models | [Get an API key](https://api.seedance.nz/sign-up?aff=5f4w) |
| ZhenZhen AI Workshop (International) | International users and overseas models | [Create an account](https://ai.t8star.org/register?aff=dP7j) |
| RunningHub China | More hosted AI applications in Mainland China | [Open RunningHub China](https://www.runninghub.cn/user-center/1819214514410942465/webapp?inviteCode=rh-v1121) |
| RunningHub International | International models and applications | [Open RunningHub International](https://www.runninghub.ai/user-center/1907375370302308353/webapp?inviteCode=rh-v1121) |

## Core nodes

| Node | Purpose | Main modes |
| --- | --- | --- |
| `MiniMax H3 Prompt Enhancer (Cloud / Local GGUF)` | Generate MiniMax H3 prompts | T2VA, I2VA, FL2VA, L2VA, Ref2VA |
| `Seedance 2.0 Prompt Enhancer (Cloud / Local GGUF)` | Generate Seedance 2.0 prompts | Text-to-video, first frame, first/last frame, multimodal reference, edit, extend, track completion, combined tasks |
| `MiniMax Music 3 Prompt & Lyrics Enhancer (T8)` | Prepare Music 3 lyrics and captions | AUTO, new lyrics, preserve, scoped rewrite, instrumental |

This project does not currently provide a Seedance 2.5 prompt node. It does not call video or music generation, polling, preview, or download APIs.

## Highlights

- Cloud providers can analyze text, images, and complete video inputs for H3 and Seedance 2.0. Music 3 is deliberately text-only.
- Local GGUF mode recursively discovers compatible models under `ComfyUI/models/LLM`, supports matched visual projectors, and requires no API key.
- Supports first frame, last frame, first-and-last-frame, multiple reference images, and multiple reference videos.
- Includes the pinned official MiniMax H3 core prompt-writing Skill and all eight optional official scene Skills.
- Includes the complete pinned MiniMax Music 3 `music-caption-rewriter` snapshot: 18 family indexes and 1,000 templates with progressive disclosure.
- Includes 260 released T8 case records consolidated into 213 stable selectors, including 47 evidence variants, plus two independent community Skills. All 215 non-official selectors include Chinese names, concise suggested inputs, structural anchors, and bundled lightweight GIF previews.
- Chinese and English prompt output.
- `strict`, `balanced`, and `creative` rewrite levels.
- `AUTO` or fixed 1–20 shot control.
- Optional user-template fusion with user intent and observable media facts taking priority.
- ComfyUI seed controls: `fixed`, `randomize`, `increment`, and `decrement`.
- In-node API-key entry, masked display, workflow save, clear, and registration links; standard `STRING` API-key connections remain supported.
- OpenAI-compatible Base URL and model ID persist in the workflow and do not need to be re-entered on every run. API keys remain separate.
- Native progress reporting, memory-only redacted diagnostics, provider capability preflight, and local prompt inspection.
- A searchable T8 template browser with categories, search, favorites, recent items, lazy GIF previews, deterministic Top-3 recommendations, and comparison.

## Installation

### ComfyUI-Manager / Registry

Search for:

```text
MiniMax H3 / Seedance 2.0 / Music 3 Prompt Enhancer (T8)
```

Or install with Comfy CLI:

```bash
comfy node install minimax-h3-seedance-music3-prompt-enhancer-t8
```

The Registry package contains the runtime code, pinned official Skills, non-official case library, and lightweight preview GIFs. It does not contain API keys, tests, source delivery batches, local runtimes, or GGUF weights.

### Git installation

Run this inside the ComfyUI `custom_nodes` directory:

```bash
git clone https://github.com/T8mars/comfyui-minimax-h3-prompt-enhancer-T8.git
```

Expected layout:

```text
ComfyUI/
└─ custom_nodes/
   └─ comfyui-minimax-h3-prompt-enhancer-T8/
```

Restart ComfyUI after installation. If the frontend still shows an older node layout, refresh the browser with `Ctrl+F5`.

## Quick start: MiniMax H3

1. Add `MiniMax H3 Prompt Enhancer (Cloud / Local GGUF)`.
2. Enter a basic idea in the video concept/prompt field.
3. Select the generation type, duration, shot count, rewrite mode, output language, core Skill protocol, and optional official or T8 template. The H3 duration field accepts any positive whole number of seconds; the node imposes no maximum, although downstream generators may still do so.
4. Connect the images or videos required by I2VA, FL2VA, L2VA, or Ref2VA.
5. Supply the selected cloud provider's API key, or choose local GGUF mode without a key.
6. Click the run button at the bottom of the node.
7. Read the final `STRING` from `enhanced_prompt`.

H3 generation types:

| Mode | Meaning | Required media |
| --- | --- | --- |
| `T2VA` | Text-to-audio-video prompt | None |
| `I2VA` | Develop forward from a first frame | `first_frame` |
| `FL2VA` | Design motion between first and last frames | `first_frame` and `last_frame` |
| `L2VA` | Build a plausible lead-in that resolves at the last frame | `last_frame` |
| `Ref2VA` | Reference-based generation or editing | At least one reference image or video |

Import [`example_workflows/minimax_h3_prompt_enhancer_example.json`](./example_workflows/minimax_h3_prompt_enhancer_example.json) for a ready-to-use cloud example.

## Quick start: Seedance 2.0

1. Add `Seedance 2.0 Prompt Enhancer (Cloud / Local GGUF)`.
2. Enter the video concept. Task intent, organization, duration, and shot count can remain `AUTO` initially. Seedance duration also accepts any positive whole number of seconds, with no node-imposed maximum; downstream generator limits still apply.
3. Connect the required first frame, last frame, reference images, or reference videos.
4. Choose official Chinese references such as `@图片N/@视频N` or Seedance.nz English references such as `@Image N/@Video N`.
5. Optionally select a T8 case or community Skill to transfer causal structure, rhythm, camera grammar, and transitions without copying its subject matter.
6. Supply a cloud API key or select local GGUF mode.
7. Connect `enhanced_prompt` to the prompt input of the downstream Seedance 2.0 video node.

Task intentions:

| Mode | Purpose | Media rule |
| --- | --- | --- |
| `AUTO` | Infer from intent and connected media | Used when the task is unambiguous |
| `T2V` | Text-to-video | No media |
| `I2V` | First-frame image-to-video | `first_frame` only |
| `FL-I2V` | First/last-frame transition | `first_frame` and `last_frame` |
| Multimodal reference | Reuse identity, motion, camera, style, or other observable traits | At least one reference asset |
| Video edit | Add, remove, or change content in an existing video | At least one reference video |
| Video extend | Extend a video forward or backward | Exactly one reference video |
| Track completion | Generate a bridge between clips | Two or three reference videos |
| Combined task | Reference one asset while editing another | An edited video plus at least one other asset |

Simple requests use one compact paragraph. Complex requests use consecutive shot events. Fixed shot counts are generation constraints sent to the LLM, not local response-validation rules.

Import [`example_workflows/seedance20_prompt_enhancer_example.json`](./example_workflows/seedance20_prompt_enhancer_example.json) for a cloud example.

## Quick start: MiniMax Music 3

1. Add `MiniMax Music 3 Prompt & Lyrics Enhancer (T8)`.
2. Describe genre, theme, mood, use case, vocal direction, and arrangement development.
3. Choose `AUTO`, generate new lyrics, strictly preserve lyrics, scoped lyric rewrite, or instrumental.
4. Use the full official mode for official routing and progressive reference selection, or the fast core mode for the three-section caption contract only.
5. Supply a cloud API key or choose local GGUF mode.
6. Send `lyrics` to Music 3 `input` and `music_caption` to Music 3 `instructions`, or parse `music3_payload_json` directly.

Outputs:

```text
lyrics
music_caption
music3_payload_json = {"input": lyrics, "instructions": music_caption}
enhancement_report_json
```

The official Skill generates this ordered caption contract, normally in English:

```text
### Global Metadata
### Vocal Details
### Arrangement
```

Lyrics and captions are intentionally isolated. Lyric generation and scoped rewriting are clearly marked T8 extensions; strict preserve mode passes the original lyrics through byte-for-byte. The lyric-language setting controls only `lyrics` and does not change the language of `music_caption`.

Import [`example_workflows/music3_prompt_lyrics_enhancer_example.json`](./example_workflows/music3_prompt_lyrics_enhancer_example.json).

## Example workflows

| Workflow | Purpose |
| --- | --- |
| [`minimax_h3_prompt_enhancer_example.json`](./example_workflows/minimax_h3_prompt_enhancer_example.json) | H3 cloud example |
| [`seedance20_prompt_enhancer_example.json`](./example_workflows/seedance20_prompt_enhancer_example.json) | Seedance 2.0 cloud example |
| [`music3_prompt_lyrics_enhancer_example.json`](./example_workflows/music3_prompt_lyrics_enhancer_example.json) | Music 3 cloud example |
| [`basic_workflow_multi_task_connections.json`](./example_workflows/basic_workflow_multi_task_connections.json) | One shared provider configuration connected to all three core nodes |
| [`minimax_h3_local_qwen_example.json`](./example_workflows/minimax_h3_local_qwen_example.json) | H3 with local Qwen and shared provider configuration |
| [`seedance20_local_qwen_example.json`](./example_workflows/seedance20_local_qwen_example.json) | Seedance 2.0 with local Qwen and shared provider configuration |
| [`music3_local_qwen_example.json`](./example_workflows/music3_local_qwen_example.json) | Music 3 with local Qwen and no visual projector |
| [`prompt_inspector_local_qwen_example.json`](./example_workflows/prompt_inspector_local_qwen_example.json) | Local H3 enhancement followed by local structural inspection |
| [`text_utilities_example.json`](./example_workflows/text_utilities_example.json) | Built-in `T8 Prompt Text` to `T8 Show Text` STRING workflow |

All bundled workflows omit API keys and use only nodes included in this repository where practical.

## Official Skills and T8 templates

MiniMax's nine H3 Skills consist of one always-on core writing Skill and eight optional scene Skills. The core Skill defines shared fields, timelines, speaker labels, media roles, and sound contracts; it is not a visual preset and cannot be disabled.

The eight optional scene Skills cover minimalist product ads, 3D animation shorts, brand promos, music-video typography, co-op game intros, paper-collage explainers, papercraft stop-motion explainers, and live-action/hand-drawn fusion. The node adapts the prompt-writing constraints that fit a single H3 prompt. It does not claim to run MiniMax Hub agents, canvas tools, asset generation, approval, editing, or delivery workflows.

T8 non-official cases and community Skills are maintained separately from all official Skills. When a T8 non-official selector and an optional official scene Skill are both selected, the T8 selector takes precedence and the optional official scene Skill is temporarily inactive. The always-on H3 core Skill remains active. Clearing the T8 selector restores the saved official scene selection without changing workflow wiring.

Preview GIFs are human-interface previews only. They are never attached to or sent as model reference material.

## Rewrite modes

| Mode | Temperature | Behavior |
| --- | ---: | --- |
| `strict` | `0.2` | Preserve intent and media facts; add only necessary structure and continuity |
| `balanced` | `0.7` | Add reasonable shots, lighting, motion, ambience, sound, and rhythm while preserving the brief |
| `creative` | `1.2` | Expand visual direction, camera design, action transitions, sound layers, and music direction |

These temperatures are product defaults, not provider recommendations.

## Providers

### ZhenZhen Affordable AI Shop

The fixed service root is:

```text
https://api.seedance.nz
```

The visual model is fixed to `bytedance/doubao-seed-evolving`. Connect any `STRING` output to the API-key socket, enter a key inside the node, or set `SEEDANCE_API_KEY`. A connected value takes priority.

The Seedance.nz transport performs bounded retries for safe SSL/connection and transient gateway failures. Authentication, balance, rate-limit, read-timeout, and user-defined OpenAI-compatible failures are not blindly retried when that could duplicate a paid request. Music 3 official reference selection uses a larger bounded retry budget because at least one official reference is required in full official mode.

### ZhenZhen AI Workshop

The fixed chat endpoint is:

```text
https://ai.t8star.org/v1/chat/completions
```

The default model is `gemini-3.5-flash`. Select Custom to enter another complete model ID. H3 and Seedance require a model that actually understands images and videos; Music 3 requires text Chat Completions only. Images and complete videos are sent as Base64 Data URLs using the representation verified against this gateway.

Use `T8STAR_API_KEY` when the node key is empty.

### OpenAI-compatible provider

Only one Base URL and one model ID are required. The Base URL may be a service root, a versioned root such as `/v1` or `/api/v3`, or a complete `/chat/completions` URL. The node normalizes the final chat endpoint.

- Images are always encoded as PNG Base64 Data URLs in the same Chat Completions request.
- Videos are Base64 by default. Optional HTTP(S) video material URLs can replace connected videos in connection order.
- There is no second upload URL.
- The provider and selected model must actually support the multimodal content parts used by H3 or Seedance.
- Base URL and model ID are saved in the current workflow and restored across runs and API-mode switches. API keys are not stored in this compatibility state.

Environment fallbacks are `OPENAI_API_KEY` and `OPENAI_BASE_URL`.

## Shared provider configuration and helper nodes

The repository also includes:

- `T8 LLM Provider Config`
- `T8 Prompt Inspector`
- `T8 Prompt Text`
- `T8 Show Text`

The green shared-provider socket is not a `STRING` socket. Add `T8 LLM Provider Config` and connect its provider-config output to the matching optional input on a core node. Normal API-key `STRING` wiring remains separate and retains priority.

When connected, the shared node controls provider, model, Base URL, local GGUF settings, temperature policy, and allowlisted extra parameters. Disconnecting it immediately restores each core node's own saved settings. Local credential aliases can keep real keys in the ComfyUI user directory while workflows store only an alias.

`T8 Prompt Inspector` is local and non-blocking. It preserves the original text, reports reproducible structural warnings, does not call an LLM, and does not judge creative quality.

## Local GGUF / llama.cpp

Local mode is the fourth mutually exclusive provider and requires no API key, Base URL, or cloud model ID. The node recursively scans:

```text
ComfyUI/models/LLM/
```

Subdirectories are supported. The scanner reads lightweight GGUF metadata, separates main models from `mmproj` projectors, preserves legacy filenames, and recommends a compatible visual projector. Discovery means the file can be offered to llama.cpp; it does not mean every third-party model has passed this project's quality suite.

Runtime fallback order:

1. The pinned `llama-server` installed by this repository.
2. A `llama-server` available on system `PATH`.
3. `llama-cpp-python` already installed in the active ComfyUI Python environment.

The node does not download large models during execution. From the node directory, run:

```powershell
& "path\to\ComfyUI\python.exe" install_local_qwen.py --dry-run
& "path\to\ComfyUI\python.exe" install_local_qwen.py --runtime
& "path\to\ComfyUI\python.exe" install_local_qwen.py --model --model-variant official
& "path\to\ComfyUI\python.exe" install_local_qwen.py --model --model-variant uncensored
& "path\to\ComfyUI\python.exe" install_local_qwen.py --model --model-variant heretic-9b
& "path\to\ComfyUI\python.exe" install_local_qwen.py --model --model-variant all
```

Pinned installer assets:

| Asset | File | Approximate size |
| --- | --- | ---: |
| Default model | `Qwen3.8-27B-Q4_K_M.gguf` | 15.93 GiB |
| Optional third-party model | `qwen3.8-27b-uncensored-fp8-q4_k_m.gguf` | 15.66 GiB |
| Optional compact third-party model | `Qwen3.8-9B-heretic-uncensored.i1-Q6_K.gguf` | 6.85 GiB |
| Visual projector | `mmproj-F16.gguf` | 0.86 GiB |
| Runtime | llama.cpp `b10436` | Platform-dependent |

`heretic-9b` installs only the pinned text model because its upstream repository does not publish a matching mmproj. It works directly for Music 3 and text-only H3/Seedance requests; image or sampled-video use requires a separately supplied compatible 9B projector, selected through AUTO matching or explicitly by the user. The existing 27B default remains unchanged for workflow compatibility. More generally, H3 and Seedance require a compatible `mmproj` whenever images or sampled video frames are connected. Music 3 is text-only and never loads a visual projector. Local video analysis uses timestamped sampled frames in an ordered contact sheet; it analyzes visible sequence only and never claims to read or transcribe the original audio track.

The compact 9B Q6_K model passed a real llama.cpp compatibility run with 12/12 deterministic checks: exact text token, image OCR/shapes/colors, early/late sampled-video codes, motion directions, temporal order, media counts, and the no-audio-analysis boundary. The visual run used a separately supplied `mmproj-Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-BF16.gguf`; this installer does not download or distribute that projector. The redacted report is [`tests/fixtures/local_qwen_heretic_9b_compatibility_2026-08-25.json`](./tests/fixtures/local_qwen_heretic_9b_compatibility_2026-08-25.json).

For responsive use, 24 GB or more VRAM is recommended. A 16 GB GPU can partially offload to system memory with the standalone server's fit strategy; at least 32 GB RAM is recommended in that configuration. CPU-only execution may work but is not expected to be interactive.

See [`THIRD_PARTY_NOTICES.md`](./THIRD_PARTY_NOTICES.md) for pinned revisions, hashes, licenses, and attribution.

## API-key security

- A connected API-key `STRING` takes priority over the in-node value.
- Masking prevents casual display on the canvas; it is not encryption.
- Clicking Save to Workflow stores the key in workflow JSON. Click Clear before sharing a workflow.
- Prefer environment variables or local credential aliases for shared workflows.
- Examples and tests contain no real API keys.
- The node does not write keys, request bodies, provider URLs, media URLs, or response bodies to logs.

Recent execution diagnostics are memory-only and redacted. They include node class, provider name, result, stage durations, attempt count when available, media count, cache status, and error category. They disappear when ComfyUI exits.

## Media handling

- Cloud images use PNG. Seedance.nz uploads them; AI Workshop and OpenAI-compatible mode inline them as Base64 Data URLs.
- Cloud video uses the complete native ComfyUI `VIDEO` stream. AI Workshop and OpenAI-compatible mode inline complete bytes unless an optional video URL is supplied.
- Local GGUF mode samples frames at real timestamps and respects the active crop window. It does not upload original video bytes or analyze audio.
- Supported containers include MP4, AVI, MOV, and MKV, up to 50 MB per file.
- H3 Ref2VA accepts up to nine images, three videos, and twelve total reference assets. A single reference video must be 2–15 seconds, and multiple reference videos must total no more than 15 seconds.

## Output and error behavior

H3 and Seedance return:

```text
enhanced_prompt: STRING
```

Non-empty upstream content is returned even if it misses a requested word count, shot count, Markdown style, time-code shape, or provider `finish_reason`. H3 performs a local field reorder only when every expected field is present exactly once and only the order is wrong. If fields are missing, duplicated, unrecognized, or already ordered, the upstream text is preserved. Seedance has no fixed H3 field contract and passes non-empty content through without structural rejection.

The node still reports genuine failures such as invalid credentials, insufficient balance, network/timeout/rate-limit/provider errors, media encoding or upload failure, malformed JSON, empty response content, missing or damaged local GGUF/mmproj/runtime files, context-budget overflow, and local inference crashes.

Music 3 uses soft post-generation checks for caption order, lyric leakage, instrumental/vocal conflicts, selected-reference overlap, timeline omissions, and token budget. Non-empty useful results are not discarded merely because a soft target was missed.

## Testing

Run the deterministic test suite from the directory above the ComfyUI root:

```powershell
.\python\python.exe -m unittest discover -s ComfyUI\custom_nodes\comfyui-minimax-h3-prompt-enhancer-T8\tests -v
```

Release verification:

```powershell
.\python\python.exe ComfyUI\custom_nodes\comfyui-minimax-h3-prompt-enhancer-T8\tools\verify_repository.py
.\python\python.exe ComfyUI\custom_nodes\comfyui-minimax-h3-prompt-enhancer-T8\tools\release.py --check-prepush
```

The deterministic suite uses mocked providers, local media fixtures, and pinned Skill resources. It does not upload assets, call paid APIs, or incur charges. Live smoke scripts require an explicit confirmation flag and may incur provider costs. Large local-model quality tests load approximately 18 GB of weights and should only be run when that resource use is intentional.

## Community and resources

| Resource | Link |
| --- | --- |
| Bilibili | [T8 on Bilibili](https://space.bilibili.com/385085361) |
| YouTube | [T8star-Aix](https://www.youtube.com/@T8star-Aix/) |
| API | [Get a ZhenZhen API key](https://api.seedance.nz/sign-up?aff=5f4w) |
| Online AI applications | [RunningHub profile and applications](https://www.runninghub.ai/zh-cn/user-center/1907375370302308353/userPost?inviteCode=rh-v1121) |
| ComfyUI package | [Quark Drive](https://pan.quark.cn/s/264edb7e36bd) |
| Model package | [Quark Drive](https://pan.quark.cn/s/c9c267081fbf) |
| Hugging Face | [t8star](https://huggingface.co/t8star) |
| Local Skills and integration package | [T8 MiniMax and Seedance local Skills](https://github.com/T8mars/minimax-h3-prompt-skill-T8) |

## References

- [MiniMax H3 base prompt-writing guide](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_base_en.md)
- [MiniMax H3 full reference-mode guide](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_ref_en.md)
- [Pinned MiniMax H3 creative Skills snapshot](https://github.com/MiniMax-AI/MiniMax-H3/tree/743d51e83329cbae6c7694f1c7b89576e7c25e07/skills)
- [Pinned MiniMax H3 core prompt-writing Skill](https://github.com/MiniMax-AI/MiniMax-H3/blob/d21241f0a4b3acbb34c97dae47fa417b7065e438/skills/h3-prompt-writing/SKILL.md)
- [Seedance API documentation](https://api.seedance.nz/docs/llms.txt)
- [Seedance 2.0 official model page](https://seed.bytedance.com/en/seedance2_0)
- [Seedance 2.0 official Prompt Optimizer Skill](https://arkdocs.tos-cn-beijing.volces.com/files/video-generation/SKILL.md)
- [MiniMax Music 3 official repository](https://github.com/MiniMax-AI/MiniMax-Music3)
- [Pinned MiniMax Music 3 caption-rewriter Skill](https://github.com/MiniMax-AI/MiniMax-Music3/tree/91410fb657c007ae57c60df8240f5ece5be089c7/skills/music-caption-rewriter)
- [Qwen3.8-27B GGUF](https://huggingface.co/unsloth/Qwen3.8-27B-GGUF)
- [llama.cpp](https://github.com/ggml-org/llama.cpp)

## Disclaimer

This is a third-party ComfyUI custom-node project. It is not affiliated with or endorsed by MiniMax, ByteDance, Seedance, or ComfyUI. Provider capabilities, pricing, and availability may change. Users are responsible for securing appropriate identity and content rights for human reference media and for following the policies of downstream services.
