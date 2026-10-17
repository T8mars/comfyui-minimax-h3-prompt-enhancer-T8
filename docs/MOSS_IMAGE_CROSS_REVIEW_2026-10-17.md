# MOSS Image：20 轮交叉审查与本机布局复现

后续用户 1256×1672 反馈已加入 [8 倍数兼容修复](MOSS_IMAGE_8PX_COMPATIBILITY_2026-10-17.md)。
本页保留此前各轮原始范围和结果，不把后续新增兼容当作早先已覆盖的测试。

范围：尚未发布的 `MOSSImagePromptEnhancerT8`。主审与独立只读子 Agent
`moss_twenty_round_audit` 完成 20 次实际往返，按反例修复，不把检查主题列表
冒充 20 轮。本次不推送、不递增发布版本、不追加付费模型采样。
原 30 节点源码、接口、旧工作流和共享 provider 模块保持不变。

## 用户截图的原因

这是新节点的前端布局兼容问题，不是“提示词/宽高没有传进去”。
独立 CPU Comfy 页面按外接 STRING 提示词、两路 INT 宽高复现：修复前节点
保留 1136 高度，提示词输入框分到 554 高度，连接后隐藏仍占大块空白。

两个原生宿主模型需要分别处理：

- 旧转换式宿主：保留 `origType`、`origComputeSize`、原生序列化；不能在刷新时
  将已转换输入强行恢复为可显示控件。首次见到已转换控件，也要保存真正的原类型。
- 新共存式宿主：widget socket 存在不等于已连接。已连接控件仍需紧凑的原生
  suppressed row；直接 extension-hidden 会让 widget 的 y 坐标停止更新，端口
  重叠。多行 DOM 控件没有原生 canvas 标签绘制器，由 MOSS 自己画固定双语标签。

最终实际 Chrome 中，初始高度 644，外接后、50 次模式切换后、保存重载后、
断开重连后均为 614；提示词行只有 24 高，显示“创作需求 / Brief（已连接）”，
宽高端口各占独立一行。保存依然只有 27 个稳定字段，未删除 `input.widget`。
实际 API 图保持外接提示词；原生 Primitive 宽高会被宿主折叠成整数，不能误判
其不是数组连线就代表丢值。普通状态刷新保留手动高度；新建、重载、接线变化
主动整理该新节点的布局。

本机打开 ComfyUI 不等于选择 GGUF：截图中的增强渠道仍是平价小屋 API。
离线增强须明确选择“本地 GGUF”；不需要云端 Key。

## 20 轮实际往返

| 轮 | 核查与证据 | 结论 / 修复 |
| --- | --- | --- |
| 1 | 固定官方源码与格式类型反例 | `[]`/对象格式不再抛未受控 TypeError。 |
| 2 | JSON 深度、体积、未知字段与有限坐标 | 未发现可到输出的绕过；保留硬门。 |
| 3 | 引号文案、参考水印、否定尺寸 | 修复被误识别成最终画布冲突；真正明确冲突仍拒绝。 |
| 4 | Caption 锁文案包含关系、重复、`[VIP]` | 按原始字符区间匹配，不拼接残片；普通方括号文案不误当坏 JSON 数组。 |
| 5 | 三云路由首发/纠正与本地消息 | 描述语言确实传入；未加猜测式语言硬判。 |
| 6 | 软字数与一次总纠正预算矩阵 | 保留合法超限首稿时同时报告超限警告。 |
| 7 | 原生转换后再次刷新 | 确认并修复已转换控件被复活/占空白。 |
| 8 | 401/限流/5xx/Proxy/SSE/取消 | 不重投付费请求；Strata POST 按真实提交增量计，不计预检。 |
| 9 | 真 loopback HTTP，第 4 次身份 GET 改模型 | 可选纠正也不能吞 identity/protocol/config/deadline 硬错误；旧成功缓存保持。 |
| 10 | 纯文字长上下文与 10 图容量 | 完整本地 messages 在加载模型之前预检；推理时仍二次检查。 |
| 11 | 一槽 batch10、10 槽、flat/nested 别名 | 四种布局都发送 10 图；超量/冲突拒绝，不静默丢图。 |
| 12 | 损坏 typed cache / 跨组件 slot | 类型、画布、稿/正向、来源和次数不符不能恢复为成功。 |
| 13 | TTL、并发、非 STRING 失败稿 | 修复异常处理中二次 TypeError、状态卡 running、无草稿却宣称保留。 |
| 14 | 路由导入、Origin、只读草稿、缓存头 | MOSS 本地拒绝畸形 Origin，所有拒绝也 no-store；不修改旧路由。 |
| 15 | 108 种保存布局组合 fuzz | null/omitted prompt+draft、Key、seed control、action tail 和坏 named map 不错位。 |
| 16 | 首见已转换后原生转回 widget | 还原真正原类型/尺寸，不再缓存 converted 状态作为基线。 |
| 17 | 实际共享配置 callback / reroute observer | MOSS 观察所有已连配置字段；保留原回调、返回值，断开不再误标 stale。 |
| 18 | 原生排版/端口位置/DOM renderer | 保留原生紧凑行及 widget 关联；只补 DOM 行双语标签，不修改全局 factory。 |
| 19 | 源 SHA、许可、示例、旧节点和包边界 | 官方快照不变；五新示例无密钥；旧源码/示例无修改。 |
| 20 | 独立重跑专项与反例收口 | 子 Agent Python 52/52、前端 17/17；最终 DOM 标签由主审实际 Chrome 复核。 |

## 验证边界与证据

- 20 轮后主审追加真实 `GetImageSize → width/height` 队列，确证非 Primitive
  上游 INT 在图校验是 `None`，原 validator 会误拒绝。现仅在图校验容忍未解析值，
  执行前仍检查真实尺寸；不是放宽 16 倍数等运行门。前一失败日志完整保留。
- 主审最终全量 1026 项 Python：1024 通过、2 原有 opt-in 跳过（188.932 秒）；
  MOSS 专项 53/53、前端 91/91、Chrome 合约通过。当前及最低 Comfy 0.33
  候选包均 CRC 通过、隔离加载 31 节点，8 官方 GIF / 0 T8 GIF，无 live-repo
  fallback。所有先失败的复现记录保留，不用修复后日志覆盖历史失败。
- Chrome 合约测试执行实际扩展 hooks；独立 Comfy 页面另外测量真实原生节点，
  不是仅用 Node stub 宣称 UI 正确。实际截图已人工检查。
- 实际 CPU 队列检查 lazy 外接草稿、跳过无关依赖、INT 输出接原生 latent、
  坏稿阻断、上次成功恢复、缺缓存与双图传输。loopback HTTP 是故障/接线夹具，
  不是 Strata 模型真实推理或付费 API 质量测试。
- 原 12 份真实模型捕获稿重新零网络回放，编译结果逐字一致；没有追加模型调用，
  不把旧采样重新标成“本次最终代码真实推理”。
- 官方 4096 Token 仍未实测，不宣称结构检查能证明成图、语义、字体或长度安全。
  RunningHub、所有前端版本、Linux/AMD 与全模型矩阵不在本次实测声明内。

本机证据前缀 `G:/CodexHome/.codex/tmp/moss-cross-`：
`native-ui-before2-20261017`（原高占位）、`native-ui-final1-20261017`（最终可见标签）、
`queue-final-20261017`、`replay-20261017.json`、`full-python-20261017.log`、
`repo-20261017.log`、`chrome-20261017.log`。自有服务/临时浏览器均在 finally 退出，
未启停用户 Comfy、Strata 或模型。

追加的真实 INT 前后反例为 `int-boundary-before-20261017` /
`int-boundary-after-20261017`（最终七场景，含两次预期错误），最终全量日志为
`full-python-final-20261017.log`；这些证据均沿用上述 `moss-cross-` 前缀。
