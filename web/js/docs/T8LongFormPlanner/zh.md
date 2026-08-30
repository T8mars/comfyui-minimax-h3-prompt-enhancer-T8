# T8 Long-form Planner（长视频分段导演）

按总时长和目标单段时长建立无缝时间表，分别输出 H3、Seedance 2.0 分段 JSON、全片连续性总纲和交接表。只做规划，不生成、拼接或剪辑视频。

可连接 `T8 Film Project Router`。连接后每段额外返回 `world_rule_checks`、`knowledge_state` 与 `downstream_status`，明确世界规则/代价、人物知情差和已失效下游；缺失事实保持未知，不会静默修复上游。

路由器中的连续性锚点会作为 `required_literal_anchors` 逐字保留。若上游返回了 JSON 但改名 `segments` 等关键字段，报告会设为 `structured_response=false` 并列出实际顶层键，不再把错误结构误报为成功。

运行后节点底部会直接显示结构协议状态：绿色表示分段合同通过，红色表示响应缺字段、段数/时序不符或锚点缺失。状态卡会跟随 ComfyUI 的中英文界面，并按诊断内容自动增高，避免长错误信息被遮挡。

`协议失败处理` 默认使用“警告并保留输出（兼容）”，因此旧工作流行为不变；选择“严格阻止下游（推荐）”后，红色合同会通过 ComfyUI 原生阻断器停止下游，同时保留状态卡和 JSON 诊断。两种模式都不会额外调用 LLM。
