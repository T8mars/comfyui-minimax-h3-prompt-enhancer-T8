# H3 空间标记增强（实验）

点击本节点底部 **📖 空间标记：示例与接线**：查看青框人物→黄框门口的示意图，
下载配套参考图 PNG 和 Ref2VA / Hybrid 工作流 JSON。先保存当前工作流，再导入JSON、
上传PNG，配置增强渠道，并将本节点从Off切On即可试用。教程不会自动替换当前画布。

配套示例已填 markers_json：`walker`是红衣人物，`door`是门口目标；
`xyxy`是原图0..1坐标，`relations`表示人物走向、穿过门口后继续前进。换图时按真实图改框。
需安装现有 `comfyui-minimax-h3-audio-T8`，以提供 `H3 Marker · Prepare`。

仅连接 MiniMax H3。现有 Prepare.marker_plan → 本节点 → H3.visual_marker_config；
同一 Prepare.marked_image 同时接 H3 原参考图口。普通 Ref2VA / Hybrid 额外参考图，默认关闭。

0 自动唯一匹配；正整数选择增强器实际 Picture，仍核对像素，不等于 Bind.marker_position。
Hybrid 首尾帧先编号。不自动插图或调整图片，不增加时长限制或独立 LLM 请求。

Off 不跳过独立 IMAGE 分支、不擦框；恢复只取旧稿并跳过新增配置依赖，不保证跳过旧媒体依赖。
云端收到图片及标记文字。核对附件不等于下游绑定、人物语义、硬轨迹或去框成功。

下游使用现有 Prompt.base_prompt 的 manual_original，再把 recipe 交 Bind；
避免 generated 重复添加动作，确保上下游图片顺序一致。On＋Relay 首期未支持。
同色/共享目标/手绘缺坐标可以用；具体原始对白、经过/停止、次序和终态仍遵守用户要求。
