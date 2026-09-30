# Qwen Image 2.1 Prompt Enhancer

`QwenImage21PromptEnhancerT8` prepares a prompt for an image model. It does not
generate an image and it does not download Qwen weights.

## Basic use

1. Enter a visual brief in **图像描述 / Prompt**, or convert that widget to an
   input and connect an upstream `STRING` node such as CR Prompt Text. A linked
   prompt is validated after the upstream node runs, not while its value is
   still unavailable during graph validation.
2. Select **文生图 / Text-to-image** when no reference image is connected.
3. Select **图像编辑 / Image edit** when connecting one to ten `IMAGE` inputs.
4. Keep **最大提示词字数** at `0` unless a specific upper bound is needed.
5. Select a ratio or leave it at `auto`. The ratio is returned separately and is not written into the prompt prose.
6. Enable **透明通道 / Transparent RGBA** only when the result must have an alpha channel and transparent background.

The main output is `rewritten_prompt`. `wh_ratio` is the selected or model-chosen
ratio. `qwen_image_request_json` is a downstream request description and
`enhancement_report_json` records parsing, correction, image count and length
status without storing API keys or response bodies.

## 两种规则 / Two profiles

高级设置中的 **编辑规则 / Edit rules**：

- **经典兼容 / Classic**：默认值，旧工作流仍使用原来的英文画面描述规则。
- **编辑专用（T8）/ Edit-aware**：仅在 Image edit 生效。先写清改哪里、怎么改，
  不改的身份、饰品、产品与构图引用原图保留，不强迫小修改扩成一大段。
  中文需求默认中文描述，英文及其他语言默认英文；可在需求写“用英文描述”等。
  描述语言与画内文字分开，指定的文字原样保留，不自动翻译。

Example: `把图1人物放进图2的街道，保持人物身份，招牌写上“OPEN”`.
The new contract identifies the person source as `<image1>` and the canvas as
`<image2>`. If that canvas is chosen, its original dimensions determine the
ratio. The LLM's semantic choice still needs human review; structural validation
cannot prove identity preservation or the quality of the final image.

This opt-in contract is written for general-purpose cloud/local LLMs. It is not
a dedicated Qwen PE checkpoint. Dedicated PE users can install the separate
[T8 Qwen Image Prompt Rewrite nodes](https://github.com/T8mars/Comfyui-Qwen-Image-Prompt-Rewrite-T8);
this node does not load or bridge those weights and has no mandatory dependency
on that project. Reviewed upstream sources and scope are recorded in
`research_sources/qwen-image-edit-t8.json`; upstream licensing remains separate.

### Classic contract

The bundled Skill describes the finished image as an observer: fixed user facts,
visible text, counts, colors and positions are preserved; unspecified visual
content is completed; the description is English except for text visible in the
image; lighting and overall composition are stated; the result is one JSON object
with `rewritten_prompt` and `wh_ratio`.

`auto` means that the user has not imposed a ratio. The Skill may choose its
horizontal or vertical default and returns that choice in `wh_ratio`. A fixed
ratio must never be repeated inside `rewritten_prompt`.

### Edit-aware output and canvas

The internal LLM response has exactly three fields: `rewritten_prompt`,
`wh_ratio`, `ratio_follow`. Exactly one ratio decision field must be nonempty.
The existing **four output ports remain unchanged**:

| Port | Edit-aware meaning |
| --- | --- |
| `rewritten_prompt` | Complete edit directive, with `<imageN>` source roles for multiple images. |
| `wh_ratio` | Resolved positive integer W:H; a follow decision uses the original source width/height. |
| `qwen_image_request_json` | v2 metadata with original brief, rewritten prompt, decision and image map. Not a ready-to-submit renderer API body. |
| `enhancement_report_json` | v2 structural checks, warnings, contract hash and logical request count. Not an artistic score. |

固定 UI 比例优先，其次是需求明确的输出尺寸/比例，再由模型判断画布。`auto` 不强制
预设比例；局部修改可跟随原图，多图不能错把风格/服装供体当作目标画布。扩图与新场景
可选择新的比例。原图 `1080×1590` 跟随结果是 `36:53`，不会偷偷改成 `2:3`。
需要下游比例 Combo 时请手动确认是否支持非预设值；本节点不裁剪、缩放或操作 latent。
图片按数字 socket 顺序、再按 batch 内顺序映射，最多十张；上传缩放不改变记录的原始尺寸。
单图允许自然称呼；多图使用 `<image1>` 等精确标记。未引用的多图来源会提示核对。

The nonserializable status action shows the last profile, checked language,
follow target and resolved ratio. Changing widgets marks it **Changed** until
the next execution. It checks structure only, never promises actual RGBA output
or preservation quality. Repeated changes do not append status widgets or height.
Classic normally keeps this action hidden. Unchecked drafts are visibly warned.

## Length and failure behavior

`0` lets the model decide the complete length. Both routes use one initial
generation plus **at most one logical correction in total**, for length and/or
format; a bad length repair never starts a third generation. Transport retries
retain the existing provider policy and are not these logical correction counts.
The node never cuts a sentence silently. If repair fails but the first draft was
valid, keep that complete draft and mark `repair_failed`, `used_first_draft` and
`over_limit` as applicable. If neither response validates, preserve available final
text as an **unchecked draft**, `structured_response=false`; never expose an
unclosed thinking block as the prompt. No final text or an initial request failure
still raises an error. Invalid model decisions are not presented as checked follow
metadata; Edit-aware may retain an explicit fixed UI ratio, otherwise leave it empty.

“恢复上次云端结果” returns the original four cached strings with **zero new
generation/upload requests**, including a v2 result when the current selector
has changed. This is process-memory recovery, not persistent storage across a
ComfyUI restart and not retrieval from a provider's task backend.

The model's hidden reasoning also consumes generation budget. Cloud requests
default to 8192 output tokens (including reasoning). If a shared provider
configuration explicitly supplies `max_tokens` or `max_completion_tokens`, that
value wins. If a response is truncated, increase the provider's output/context
budget before reducing the image description target.

## Provider notes

The default cloud route uses `qwen/qwen3.8-flash-next` through ZhenZhen
Affordable AI Shop. AI Workshop, OpenAI-compatible, shared provider config and
local GGUF settings follow the same provider family used by the existing T8
enhancers. Local image editing requires a matching visual `mmproj` and enough
context for every connected image; images are never silently dropped.
The local GGUF mode does **not** require an API Key. The `API Key` socket is
only for cloud modes and may be left unconnected locally. If a saved example
still has the old title saying to fill an API Key, update this node from GitHub;
the current example title no longer implies a key is required for local mode.

The original 22 serialized fields keep their order; a versioned 23rd field is
appended for the profile. Older 20/22-field layouts, linked text, force-input
API-key placeholders, seed controls and UI tails migrate by name. Existing H3,
Seedance, Music 3 and YuE2 schemas/provider behavior are not changed here.
Local browser compatibility is not a RunningHub production acceptance test.
