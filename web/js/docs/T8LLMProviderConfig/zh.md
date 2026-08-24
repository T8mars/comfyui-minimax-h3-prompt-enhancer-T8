# T8 LLM 共享渠道配置

可选的共享配置节点。把 `provider_config` 接到任一 T8 提示词增强节点，即可统一渠道、模型、OpenAI Base URL、本地 Qwen 参数、`temperature` 策略和白名单附加参数。

“共享 LLM 渠道配置（可选）”是专用配置类型，不是 `STRING`。在画布中搜索 `T8 LLM 共享渠道配置`，把其“渠道配置”输出连接到核心节点的绿色同名输入。选择 `Local Qwen` 后不需要 API Key；默认模型为 `Qwen3.8-27B-Q4_K_M.gguf`，H3/Seedance 的视觉分析还使用 `mmproj-F16.gguf`，Music 3 只加载文字模型。

- 不连接时，原节点行为、默认值和旧工作流完全不变。
- 原节点已有的 `api_key` STRING 接线或保存值优先于凭据别名。
- 凭据别名只保存在工作流中；真实 Key 写入 ComfyUI 用户目录，不进入工作流 JSON。
- OpenAI 兼容渠道能力未知时不会假定支持图片或视频，请先用节点的“渠道能力预检”。
- 附加参数不能覆盖 `model`、`messages`、`stream` 或 `temperature` 等核心字段。

断开连接即可恢复原节点字段。
