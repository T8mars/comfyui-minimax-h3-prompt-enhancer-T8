# YuE2 音乐提示词与歌词创作 / Music prompt & lyrics creation

[1.15.0 真实 API / 本地验收记录](yue2_acceptance.md)

此节点生成文字，不生成音频；不需要安装 YuE2、SheetSage2 或下载音乐权重。
This node creates text, not audio. No YuE2/SheetSage2 music weights are needed.

## 快速开始 / Quick start

1. 从模板导入 `yue2_cloud_creation_example`，在左侧 T8 文本节点填写自己的 LLM API Key。
2. 在创作要求里写主题、情绪和用途。默认中文歌词、英文风格描述，两者互不改变。
3. 点击创作，或运行工作流。将 `style` 和 `lyrics` 分别接到下游对应输入。
4. 若使用官方 YuE2 Python/CLI，可直接使用 `yue2_request_json`。本节点不会代替下游生成音乐。

Import the cloud example, enter your own key, describe the song, and run. Connect
`style` and `lyrics` separately. `yue2_request_json` follows the official request
contract; generating actual audio is a separate downstream step.

## 歌词模式 / Lyrics modes

- AUTO：有原词则逐字保留；没有则创作。不会根据一句模糊要求自动覆盖原词。
- 生成新歌词：按当前要求创作原创歌词；此模式不保护原词。
- 严格保留：原词包括换行原样输出，只生成配套风格描述。换风格也用此模式。
- 定向改词：在高级选项填写段名、出现次数、改词要求。例如 `Chorus`、`2`、`更有希望，保持两行`。段落必须有独立的 `[Chorus]` 标签；只有指定段落正文被替换。
- 纯器乐：歌词输出为空，只生成器乐风格要求。最终是否没有人声仍需试听验证。

AUTO preserves existing lyrics, otherwise writes new lyrics. Preserve mode keeps
the exact text and line endings. Edit mode replaces only the selected occurrence
of a tagged section; other sections are reconstructed from the untouched original.
Instrumental mode emits empty lyrics and requests no vocals, without claiming an
audio guarantee.

## 官方谱面模式 / Official score modes

| 模式 | 作用 / Behavior |
| --- | --- |
| full | 默认；YuE2 规划旋律和和声 / melody and harmony planning |
| melody | 无和弦标记的旋律规划 / chord-free melody planning |
| off | 跳过乐谱阶段 / no symbolic score stage |

这些模式不等于 LLM 的思考强度或创作质量。ABC 为空时，节点不会伪造一份曲谱。
外部 ABC 会绕过 YuE2 自己的谱面规划；使用者应提供完整、检查过的谱面。

With external ABC, `off` is invalid. `melody` does not strip chords automatically:
select the explicit strip-chords action, or use `full` to retain harmony. The
official lightweight helper checks only its bounded native two-voice dialect,
not the complete ABC standard. Chord removal compares sounding notes, onsets,
durations and bar grids in **both Vocal and Ins voices**. It does not prove audio
adherence or preserve a source singer's identity.

The ABC example is deliberately a **one-bar interface demonstration**, not a
complete song. Replace it with your own complete score and matching lyrics.
If BPM/meter/key conflict with a supplied score, the report warns and style
uses the preserved score's metadata. This version does not transpose or
reharmonize the score. Preserve mode also warns about a possible language
mismatch without rewriting or rejecting the user's lyrics.

## 渠道与费用 / Providers and cost

- 贞贞平价小屋、AI 工坊、OpenAI 兼容接口、本地 llama.cpp GGUF。
- 连接共享 LLM 渠道配置时，其渠道和模型设置优先；断开后使用本节点高级设置。
- OpenAI 的 Base URL 和模型 ID 随工作流保存。可通过共享配置的凭据管理保存本地密钥别名；公开分享前移除文本节点中的密钥。
- 本地是纯文本模式，不加载视觉投影器；采用现有 GGUF 模型目录和卸载策略。
- 标准新歌／局部改词通常 2 次 LLM 请求；保留原词／纯器乐通常 1 次。
- 创作审校增加 1 次评分，必要时最多 1 次定向修订；歌词语言纠正可能再增加 1 次。HTTP 重试另计。报告记录实际请求次数。
- 云端与本地生成上限分别可设，默认 16384 Token。思考与正文共用上限；本地还受上下文剩余容量影响。截断不能当作完整结果。

The shared config overrides provider/model settings, but a connected API key
remains authoritative. Local mode needs no API key or vision projector. Calls
are sequential. Output limits include reasoning; provider capacity still applies.
The recovery button reads the last complete five-output result in the current
ComfyUI process, not a remote task-query API. Restarting ComfyUI clears this cache;
an interrupted creation with no complete result cannot be recovered as a song.

## 输出与评分 / Outputs and evaluation

`style`, `lyrics`, optional `abc`, `yue2_request_json`, `creation_report_json`.
Native JSON contains only `style`, `lyrics`, `cot`, `seed`, `id` and optional
`abc` / `cfg_scale`. There is no invented duration, reference_audio or phonemes
field. Planned duration is advisory. CFG is not a creativity slider.

创作审校按主题叙事、可唱性、副歌记忆点、段落发展、词曲风格协调五项各 20 分评价。
这是 LLM 文本审校，不是官方音乐基准或听感评分。报告保留扣分意见；若发生修订，
分数明确标记为修订前草稿的分数，不冒称最终版本已经重新评分。

Text scores are model judgments, not acoustic measurements. Inspect the actual
lyrics and issue list. Validate real music separately for omitted/repeated words,
pronunciation, melody, arrangement, transitions and ending.

## 四套工作流 / Four bundled workflows

- `yue2_cloud_creation_example`：中文新歌 / cloud creation.
- `yue2_preserve_lyrics_example`：保留原词、换编曲 / preserve and restyle.
- `yue2_local_qwen_example`：共享本地 GGUF 配置 / local GGUF.
- `yue2_abc_melody_example`：乐谱校验、去和弦 / native ABC preparation.

All examples use only nodes bundled by this repository. No third-party text
utility is required. Select an installed model in the local example before running.

## 来源 / Source

Official source: [YuE2 Music Skill](https://github.com/multimodal-art-projection/YuE/tree/92a73cc7652fcc1f937855e4b765e0a0edd7ff2e/skills/yue2-music),
commit `92a73cc7652fcc1f937855e4b765e0a0edd7ff2e`.
Instructions and ABC helper are Apache-2.0. Text composition/review is a T8
extension. Music weights, if separately installed, retain their own licenses.
The bundled source manifest checks normalized UTF-8 hashes; no upstream access
or model download occurs when executing this node.

Registry 安装包不包含官方的音频运行教程 `generation-and-covers.md`；它不参与本节点
运行，原文保留在 GitHub 和上方官方链接中。提示词规则、ABC 参考和许可证仍随包提供并校验。
Registry omits only the upstream audio-runtime tutorial; the unmodified document
remains on GitHub. Prompt rules, ABC references and license remain bundled and checked.
