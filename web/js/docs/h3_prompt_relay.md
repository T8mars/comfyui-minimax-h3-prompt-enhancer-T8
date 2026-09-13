# H3 Prompt Relay 编排 / Authoring

在原 **MiniMax H3 提示词增强器** 中把「输出模式」切到 **Prompt Relay 编排**。默认仍是普通增强，旧提示词输出保留在第一个位置；无需更换原节点。多渠道、共享配置、参考素材、本地 GGUF 和原有表演导演继续使用。

## 最简单的用法

[下载文本示例](./workflows/h3_prompt_relay_example.json)不依赖视频执行节点；[下载已接好 Relay Plan 的适配示例](./workflows/h3_prompt_relay_plan.json)另需安装包含 `MiniMaxH3PromptRelayPlanT8Advanced` 的 T8 H3 执行项目。两个链接均由 ComfyUI 本机静态目录提供；适配示例只编译时间线，不加载视频模型、不排队生成视频。

1. 写创意，设目标时长。例：`女生在站台捡起车票，交给乘客，说“你的车票。”，对方点头，她挥手。8秒，一镜到底，无配乐。`
2. 打开 Relay；事件数 `0` 自动安排。事件不是镜头，不会要求每个事件都切镜。
3. 指定时间选填，例如三行 `0-2.5`、`2.5-5`、`5-8`；留空按模型给出的权重分配。不能填 JSON、`2.5s` 或 `00:02.500`。
4. 点运行。读取 `relay_report` 的时间表和提醒，再将以下四个输出连接到执行项目的 Plan。

| 增强节点输出 | Prompt Relay Plan 输入 |
| --- | --- |
| `global_prompt` | `global_prompt` |
| `local_prompts` | `local_prompts` |
| `time_ranges` | `time_ranges` |
| `relay_length` | `length`（转成输入并连接 INT） |

Plan 设置：`timing_mode=seconds`、`allow_gaps=false`、`allow_overlaps=false`。**不要连接 `prompt_relay_events`**，它会覆盖文本事件。再把 Plan 经 Query Route 接到执行节点，并在那里开启 `apply_exp`。只生成提示词不会自动启用 Relay。

Runner 的 `global_prompt` 留空或与 Plan 相同；`segment_prompts_json` 留空。`enhanced_prompt` 是完整普通 H3 提示词，不能拿来替代 Relay 的 global。

## 时间与格式

- 当前执行合同为 24 FPS、每事件至少 5 帧、最多 32 事件；自动模式至少一个事件。单事件不启用多事件竞争路由。
- 普通目标时长仍是原来的整数秒。Relay 精确秒数 `0` 沿用该值；需要 `25.29` 秒时在此单独填写，不改变旧工作流参数类型。
- 交付帧数采用 Python `round(秒数×24)`；计划向上对齐到 `17n+5`。25.29 秒交付 607 帧、计划 617 帧；多出的 10 帧只延续末态，不能放新台词或关键动作。
- 手动时间覆盖**成片交付时间**，不是补齐时间；代码自动延长最后一个范围。六位小数时间范围可往返到整数帧。
- 全局只写跨全片成立的信息。局部每行一个事件，包含当前动作、结果与声音；不会将完整剧情或对白重复塞入全局。
- 每事件内部不能含换行或 ASCII `|`。若逐字原文含这些分隔符，需要先解决文本合同冲突，不能偷偷删改。
- 不建立任何采样器、音频、LoRA、缓存或窗口投影设置。Relay 是注意力引导，不是硬切或口型同步保证。`joint_av_exp` 为实验性音视频路线，多事件时不能与 `lock_source` 组合。
- 下游 Plan 的 length 输入有自己的范围（当前所核对版本为 5..3600）；更长任务需先确认执行节点版本能力，本节点不会擅自截短用户时长。

## 费用、恢复与失败

通常一次当前渠道的创作请求。描述语言不符合要求时可能额外纠正一次；Relay 格式校验失败时最多再纠正一次，不无限重试。失败会明确报出格式或时间问题，不把不可执行的文本冒充有效计划。

「恢复上次云端结果」恢复已完成的本机内存结果，不重新付费生成；模式要与原任务相同。Relay 会同时恢复全部输出，包括整数帧数。未完整收到的响应、重启前的内存记录不能据此恢复。

`relay_report` 只证明静态格式、范围对应与帧计算；人物动作、逐字原文和成片效果仍需检查。本地模型未做本次真实验收；小模型的结构化输出能力会影响是否需要格式纠正。

## English quick start

Select **Prompt Relay 编排** on the existing H3 enhancer. Normal mode remains the default; output slot zero stays `enhanced_prompt`. Enter an idea and duration, leave event count at zero for automatic planning, or provide one decimal-seconds range per line. Event count is not shot count.

Connect `global_prompt`, `local_prompts`, `time_ranges` and integer `relay_length` to the existing execution project's Relay Plan. Set `timing_mode=seconds`, disable gaps/overlaps, leave typed events disconnected, and enable Relay in the downstream runner. Keep runner global empty or identical and its separate segment JSON empty. No generation model or third-party executor is required for the bundled text-only tutorial.

The compiler uses 24 FPS, Python rounding, a five-frame event minimum and the `17n+5` plan grid. Padding holds the completed ending; it does not extend the requested story. One normal authoring call may be followed by one language correction and one format correction. Restoring a completed result never resubmits the paid task. Static validation is not a rendered-video quality guarantee.
