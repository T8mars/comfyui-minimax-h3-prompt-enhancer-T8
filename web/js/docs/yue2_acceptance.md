# YuE2 1.15.0 文本验收 / Text acceptance

日期：2026-09-11。未生成音乐，未给出听感分数。官方协议固定于
`92a73cc7652fcc1f937855e4b765e0a0edd7ff2e`。

## 真实推理 / Live inference

| 场景 | 实际渠道 / 模型 | 请求数 | 总耗时 | 结果 |
| --- | --- | ---: | ---: | --- |
| 中文原创＋审校 | 贞贞平价小屋 / bytedance/doubao-seed-evolving | 3 | 165.03 秒 | 中文歌词、英文 style、原生 JSON 通过；文本审校 91/100 |
| 英文原创 | 同上 | 2 | 48.23 秒 | 英文歌词、英文 style、原生 JSON 通过 |
| 严格保留原词并换风格 | 同上 | 1 | 14.22 秒 | 歌词逐字一致；只生成 style |
| 只改第二次副歌 | 同上 | 2 | 68.06 秒 | 指定正文改变，其他文本保持原样 |
| 本地中文原创 | llama-server / Qwen3.5-4B_Abliterated.f16.gguf | 2 | 25.08 秒 | 两阶段均为有效完整 JSON，中文歌词与英文 style 独立 |
| 本地原创＋审校 | 同上 | 3 | 35.23 秒 | 三阶段通过；文本审校 84/100 |

本地环境：Windows、RTX 4060 Ti 16 GB、上下文 16384、生成上限 8192、关闭思考。
这是已有小模型的验收配置，不会覆盖节点默认的 16384 生成上限；没有下载模型。
上述耗时为单次样本，不是性能承诺。两个文本分数来自各自 LLM 审校，不能当作
跨模型统一基准：云端指出副歌偏长、里程表细节等问题；本地指出 hook、行文与桥段衔接的改进方向。

完整无密钥输入、实际输出与报告见仓库
`tests/fixtures/yue2_acceptance_2026-09-11.json`。
可运行 `yue2_live_smoke.py` 复测云端（交互输入密钥，不保存），或用
`--local-model 已安装的模型.gguf --local-reviewed` 复测本地。云端复测会产生费用。

## 回归与边界 / Regression and limits

- 全仓 378 项 Python 测试通过，含 25 项 YuE2 专项测试。
- 真实浏览器契约通过：反复折叠不累积高度、说明区固定占位、模型 ID/Base URL/歌词保存与重载、重复初始化不增加控件。
- 17 套工作流中新增 4 套 YuE2 示例；原节点 ID、输出和原有工作流保持兼容。
- API 工坊和通用 OpenAI 兼容接口通过请求构造与参数传递测试；没有冒称使用所有供应商密钥实测。
- 本地 llama-server 做了真实推理；两种 llama-cpp-python 包装路径通过模拟运行时的结构化格式与结束原因传递测试，不冒称每个 wheel 都跑过。
- ABC 去和弦通过 Vocal、Ins 双声部音符、时值与小节网格校验；不等于最终音频精确遵谱。

本次发现并修复：小型本地模型即使返回 `finish_reason=stop`，也可能输出未闭合
JSON；通用 `json_object` 在该实测环境不足以约束它。改用带明确字段的 JSON Schema
后，上述本地标准与审校两条流程均通过。没有硬补引号或将截断内容当作成品。

All results above are text/protocol evidence. Actual YuE2 audio rendering,
pronunciation, musicality, lyric coverage and timing still require listening tests.
