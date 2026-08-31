# MiniMax Music 3 提示词与歌词增强器（T8）

这是文字节点，不生成或试听音频。它把歌词与 Music 3 官方结构化 Caption 分成独立输出。

- `lyrics`：生成、严格保留、局部润色或纯器乐模式下的最终歌词。
- `music_caption`：官方 Skill 规定的 `Global Metadata / Vocal Details / Arrangement`，默认英文。
- `music3_payload_json`：包含 Music 3 所需的 `input` 与 `instructions`。
- `enhancement_report_json`：脱敏阶段与质量报告，不含 API Key、歌词全文或模板正文。

“官方完整”模式按官方渐进披露流程选择最多两个流派索引和三个职责不同的模板。歌词创作/润色是 T8 非官方能力，不冒充官方 Skill。

本地模式可使用 `ComfyUI/models/LLM` 及任意子目录中的 llama.cpp 兼容文字 GGUF；Music 3 不加载 mmproj。节点会优先使用固定 llama-server，也可复用当前 ComfyUI Python 已安装的 llama-cpp-python。

“恢复上次云端结果（不重新生成）”会一次恢复同一成功运行的四个完整输出，只读当前进程内存，不会重新发起任何歌词或 Caption 请求。

Caption 的语言选项在云端与本地都作为最终约束；只有完整 Caption 明显跑错语种时才追加一次只纠正语言的请求。网络状态未知时不会重投，歌词语言仍由独立的歌词语言选项控制。
