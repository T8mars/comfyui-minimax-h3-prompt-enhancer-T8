---
pipeline_tag: text-generation
license: other
license_name: minimax-h3-image-community-license-agreement
license_link: https://huggingface.co/MiniMaxAI/MiniMax-H3-Image/blob/main/LICENSE
library_name: transformers
language:
- en
tags:
- prompt-expansion
- text-to-image
- minimax-h3
- fp4
- sglang
base_model:
- Qwen/Qwen3.8-27B
---

<div align="center">
  <img width="100%" src="assets/minimax-h3-image.jpg" alt="MiniMax H3 image, Open Weights">
</div>

<p align="center">
  <a href="https://hailuoai.video" target="_blank"><img src="https://img.shields.io/badge/Hailuo%20AI-FF6C37?logo=minimax&logoColor=white" alt="Hailuo AI"></a>
  <a href="https://platform.minimax.io" target="_blank"><img src="https://img.shields.io/badge/API-FF6C37?logo=minimax&logoColor=white" alt="API"></a>
  <a href="https://www.minimax.io" target="_blank"><img src="https://img.shields.io/badge/MiniMax%20Website-FF6C37?logo=minimax&logoColor=white" alt="MiniMax Website"></a>
  <a href="https://github.com/MiniMax-AI/MiniMax-H3" target="_blank"><img src="https://img.shields.io/badge/GitHub-181717?logo=github&logoColor=white" alt="GitHub"></a>
  <a href="https://huggingface.co/MiniMaxAI/MiniMax-H3-Image-PE" target="_blank"><img src="https://img.shields.io/badge/Hugging%20Face-FFD21E?logo=huggingface&logoColor=black" alt="Hugging Face"></a>
  <br>
  <a href="https://modelscope.cn/organization/minimax" target="_blank" rel="noopener noreferrer"><img alt="ModelScope MiniMax AI" src="https://img.shields.io/badge/ModelScope-MiniMax%20AI-white?labelColor=%23EF3D5D"></a>
  <a href="https://platform.minimaxi.com/docs/faq/contact-us" target="_blank"><img src="https://img.shields.io/badge/WeChat-07C160?logo=wechat&logoColor=white" alt="WeChat"></a>
  <a href="https://discord.com/invite/dbMxutw7tP" target="_blank"><img src="https://img.shields.io/badge/Discord-5865F2?logo=discord&logoColor=white" alt="Discord"></a>
  <a href="https://huggingface.co/MiniMaxAI/MiniMax-H3-Image/blob/main/LICENSE"><img src="https://img.shields.io/badge/LICENSE-4CAF50?logo=creativecommons&logoColor=white" alt="LICENSE"></a>
</p>

# MiniMax-H3-Image-PE

## Online API

Use MiniMax-H3-Image directly via API.

- Global: [platform.minimax.io](https://platform.minimax.io/docs/guides/image-generation) | CN: [platform.minimax.cn](https://platform.minimax.cn/docs/guides/image-generation)

API docs:
- Text-to-image: [EN-docs](https://platform.minimax.io/docs/api-reference/image-generation-h3-generations), [CN-docs](https://platform.minimax.cn/docs/api-reference/image-generation-h3-generations)
- Image editing: [EN-docs](https://platform.minimax.io/docs/api-reference/image-generation-h3-edits), [CN-docs](https://platform.minimax.cn/docs/api-reference/image-generation-h3-edits)
- Prompt expansion: [EN-docs](https://platform.minimax.io/docs/api-reference/image-generation-h3-context-ir), [CN-docs](https://platform.minimax.cn/docs/api-reference/image-generation-h3-context-ir)

## Introduction

MiniMax-H3-Image-PE provides prompt expansion (PE) for
[MiniMax-H3-Image](https://huggingface.co/MiniMaxAI/MiniMax-H3-Image).
It turns a short request into a detailed description of the intended image,
together with an aspect-ratio recommendation for image generation.

This repository covers two workflows:

| Workflow | Input | Released assets |
| --- | --- | --- |
| **Text-to-image (T2I) PE** | A text instruction | MiniMax-H3-Image-PE weights (fine-tuned from [Qwen3.8-27B](https://huggingface.co/Qwen/Qwen3.8-27B), FP4), task and system prompts, and a client example |
| **Image editing PE** | An editing instruction and reference images | A task prompt and message-assembly example for a vision-language model of your choice. **Image editing PE is still under development; this release provides its prompt only.** |

The examples below explain how to use MiniMax-H3-Image-PE and the image editing task prompt.

## How to use T2I PE

Run the examples from a local copy of this repository so the relative prompt and
script paths resolve correctly.

### Serve MiniMax-H3-Image-PE

We recommend SGLang with `sglang>=0.5.23` and `xgrammar>=0.2.7`.

```bash
sglang serve \
  --model-path MiniMaxAI/MiniMax-H3-Image-PE \
  --served-model-name MiniMax-H3-Image-PE \
  --model-type llm \
  --reasoning-parser qwen3 \
  --grammar-backend xgrammar \
  --constrained-json-disable-any-whitespace \
  --host 0.0.0.0 \
  --port 30000
```

SGLang reads the FP4 configuration from the checkpoint. XGrammar constrains the
answer to the JSON schema, and the reasoning parser separates reasoning from the
final answer.

### Expand a prompt

Load the task prompt and insert your instruction with `.format(user_query)`:

```python
from pathlib import Path

task_prompt = Path("prompt/t2i/task_prompt.txt").read_text(encoding="utf-8")
user_query = "An orange tabby cat sleeping on a sunlit windowsill."
user_prompt = task_prompt.format(user_query)
```

Send it with the system prompt and request parameters:

```python
import json
from urllib.request import Request, urlopen

system_prompt = Path("prompt/t2i/system_prompt.txt").read_text(encoding="utf-8").strip()
params = json.loads(Path("prompt/t2i/request_params.json").read_text(encoding="utf-8"))
payload = {
    **params,
    "model": "MiniMax-H3-Image-PE",
    "messages": [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ],
    "stream": False,
}
request = Request(
    "http://0.0.0.0:30000/v1/chat/completions",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
)
with urlopen(request, timeout=1200) as response:
    result = json.load(response)
pe_result = json.loads(result["choices"][0]["message"]["content"])
print(pe_result)
```

The included client performs the same request and checks the response:

```bash
python3 scripts/expand_prompt.py \
  --url http://0.0.0.0:30000 \
  --model MiniMax-H3-Image-PE \
  "An orange tabby cat sleeping on a sunlit windowsill."
```

### Request parameters

The examples load the defaults from
[`prompt/t2i/request_params.json`](prompt/t2i/request_params.json):

| Parameter | Value |
| --- | --- |
| `temperature` / `top_p` / `top_k` | 1.0 / 0.95 / 20 |
| `min_p` | 0.0 |
| `presence_penalty` / `repetition_penalty` | 0.0 / 1.0 |
| `max_tokens` | 4096, including thinking and the final answer |
| `reasoning_effort` | `xhigh` |
| `enable_thinking` / `preserve_thinking` | `true` / `true` |
| `response_format` | JSON schema for `expanded_caption` and `aspect_ratio` |

### Output

With `--reasoning-parser qwen3`, `message.content` contains the JSON answer.
Reasoning is returned separately in `message.reasoning_content`. Example output:

```json
{
  "expanded_caption": "A warm photograph shows an orange tabby cat sleeping on a sunlit windowsill, with soft afternoon light falling across its fur.",
  "aspect_ratio": "3:2"
}
```

When your aspect-ratio selection is `auto`, use the `aspect_ratio` returned by the
model for image generation. If you select an explicit ratio, use your selected
ratio instead of the model's recommendation at the image-generation stage.

## How to use Image editing PE

Use the task prompt with a vision-language model that supports interleaved text
and images. The example below describes message assembly without selecting a
model or making an API call.

### Inputs

Provide the following inputs:

| Input | Description |
| --- | --- |
| `user_query` | The editing instruction. Refer to images in their supplied order. |
| `references` | At least one prepared image, in order, with its original display aspect ratio as a reduced `W:H` string. Use `None` when the source ratio is unknown. |
| `aspect_ratio` | The target ratio: `adaptive` to let the model choose, or an explicit positive-integer `W:H` string. |

### Assemble the message

Load [`prompt/edit/task_prompt.txt`](prompt/edit/task_prompt.txt) unchanged as the
first content part. Follow it with the image count, each image's label and source
ratio immediately before that image, and your editing instruction and target ratio
in the final text part. This produces one user message.

The fixed task prompt forms a shared prefix across requests, allowing reuse by
services that support prefix caching. Cache behavior depends on the provider.

In the pseudocode below, `source_image` and `reference_image` are already prepared
image inputs. The text and image parts are conceptual; adapt their representation
to your model's interface.

```python
import json
from pathlib import Path

task_prompt = Path("prompt/edit/task_prompt.txt").read_text(encoding="utf-8")
user_query = "Replace the bag in the first image with the bag in the second image."
aspect_ratio = "adaptive"  # Or an explicit ratio, such as "16:9".
references = [
    {"image": source_image, "aspect_ratio": "3:2"},
    {"image": reference_image, "aspect_ratio": "1:1"},
]

count = len(references)
content = [
    {"type": "text", "text": task_prompt},
    {"type": "text", "text": (
        f"Reference Image Count:\n"
        f"{count} input image(s), labeled <Picture 1> through <Picture {count}>."
    )},
]
for index, reference in enumerate(references, start=1):
    metadata = "aspect_ratio unavailable"
    if reference["aspect_ratio"] is not None:
        metadata = f"aspect_ratio {reference['aspect_ratio']}"
    content.extend([
        {"type": "text", "text": f"Reference Media:\n- <Picture {index}> [{metadata}]"},
        {"type": "image", "image": reference["image"]},
    ])

user_input = (
    "\nUser Editing Instruction (JSON string):\n"
    f"{json.dumps(user_query, ensure_ascii=False)}\n\n"
    f"User Aspect Ratio Selection:\n{aspect_ratio}\n\n"
    "Apply the instructions above to the supplied inputs and reference images. "
    "Output only the required two-field JSON object."
)
content.append({"type": "text", "text": user_input})
messages = [{"role": "user", "content": content}]
```

### Output

```json
{
  "expanded_caption": "<one paragraph describing the intended edit>",
  "target_aspect_ratio": "3:2"
}
```

The description identifies source subjects, states what is preserved or changed,
and describes new content. Descriptive prose is English; literal text retains the
language you request. `target_aspect_ratio` is a positive-integer `W:H` string.
If you select an explicit ratio, the model preserves it exactly. If you select
`adaptive`, the model determines a numeric ratio for the intended edited image.

## Use with Diffusers

MiniMax-H3-Image-PE can also run locally in Transformers through the
[`diffusers/minimax-h3-image-pe-blocks`](https://huggingface.co/diffusers/minimax-h3-image-pe-blocks)
Modular Diffusers blocks. The blocks use the released prompts and request
parameters for T2I PE and Image editing PE, and XGrammar constrains the answer
to the JSON schema.

### Load MiniMax-H3-Image-PE

```bash
pip install -U diffusers transformers xgrammar bitsandbytes kernels flash-linear-attention
```

```python
import torch
from diffusers import ModularPipeline

pe = ModularPipeline.from_pretrained("diffusers/minimax-h3-image-pe-blocks", trust_remote_code=True)
pe.load_components(dtype=torch.bfloat16, device_map="cuda")
```

The FP4 weights stay in 4-bit and use about 19 GiB of GPU memory. GPUs with
native FP4 support run the NVFP4 weights directly; other GPUs use bitsandbytes
FP4.

### Expand a prompt

Pass a request to run T2I PE:

```python
state = pe(prompt="An orange tabby cat sleeping on a sunlit windowsill.")
print(state.get("prompt"), state.get("aspect_ratio"))
```

Pass reference images to run Image editing PE. Refer to the images in their
supplied order:

```python
state = pe(
    prompt="Replace the bag in the first image with the bag in the second image.",
    image=["source.png", "bag.png"],
    aspect_ratio="adaptive",
)
print(state.get("prompt"), state.get("aspect_ratio"))
```

### Inputs and outputs

| Name | Description |
| --- | --- |
| `prompt` | Input: the request or editing instruction. Output: the expanded caption. |
| `image` | One or more reference images (PIL images, paths or URLs). Selects Image editing PE. |
| `aspect_ratio` | Input, Image editing PE only: `adaptive` or an explicit `W:H` ratio. Output: the target ratio. |
| `enable_thinking` | Reasoning before the answer, `True` by default as in the released request. |
| `max_new_tokens` | Token budget, including thinking and the final answer. |
| `seed` | Seed for a reproducible expansion. |
| `reasoning` | Output: the model's reasoning. |

Activations run in bf16, so outputs are not identical to the SGLang deployment
above.

## License

- MiniMax-H3-Image-PE is part of MiniMax-H3-Image and is released under the [MiniMax-H3-Image Community License Agreement](https://huggingface.co/MiniMaxAI/MiniMax-H3-Image/blob/main/LICENSE).
- MiniMax-H3-Image-PE is derived from [Qwen3.8-27B](https://huggingface.co/Qwen/Qwen3.8-27B), which is licensed under the Apache 2.0 License.
- The separate written authorization described in Section IV of the license is requested through [platform.minimax.io/license](https://platform.minimax.io/license).

## Contact Us

Contact us at [model@minimax.io](mailto:model@minimax.io).