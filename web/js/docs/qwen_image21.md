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

## Skill contract

The bundled Skill describes the finished image as an observer: fixed user facts,
visible text, counts, colors and positions are preserved; unspecified visual
content is completed; the description is English except for text visible in the
image; lighting and overall composition are stated; the result is one JSON object
with `rewritten_prompt` and `wh_ratio`.

`auto` means that the user has not imposed a ratio. The Skill may choose its
horizontal or vertical default and returns that choice in `wh_ratio`. A fixed
ratio must never be repeated inside `rewritten_prompt`.

## Length and failure behavior

`0` leaves the Skill-compliant length to the model. A nonzero value triggers at
most one length correction. The node never cuts a sentence silently. If a model
returns nonempty text but cannot produce valid JSON after one correction, the text
is preserved in `rewritten_prompt`, while the report marks
`structured_response=false` and leaves `wh_ratio` empty.

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

The node is an independent addition. Existing H3, Seedance 2.0, Music 3 and YuE2
workflows do not need migration.
