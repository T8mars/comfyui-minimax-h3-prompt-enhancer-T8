# MOSS 8 倍数画布兼容修复 · 2026-10-17

用户错误历史中的实际输入是 **1256×1672**，来自原生 ResolutionSelector：
`3:4 (Portrait Standard)`、2.0 MP、multiple=8。旧 T8 合同照搬官方快照的
16 倍数门，导致增强节点在模型/API 调用之前停止。该限制不能直接当作所有
Comfy 出图运行端的能力边界。

## 修复

- T8 接受范围 16–16384 内的 8 倍数，不改默认 1024，不自动取整或缩放。
- 同步 Python 校验、宽高步长、前端 named/positional 恢复、模型消息规则、
  Caption/Layout 编译和 typed cache；节点 ID、27 字段及六输出类型不变。
- 官方 `moss_vendor` 文件、来源 SHA 和 Apache 许可不变。16 对齐 Layout
  仍直接走原编译器；8 对齐扩展用临时 16 对齐 envelope 验证完整 schema，
  再调用官方 `centered_box` 在真实画布重新校验并计算坐标。临时 padding
  不是有效画布，进入 padding 的框仍报错。原始草稿不变，不执行模型代码。
- 8 对齐消息去除互相冲突的“必须 16 倍数”指令，重复真实宽高；原来 16
  对齐的消息/编译路径不变。旧十二份真实模型捕获稿零网络回放仍逐字相同。
- 报告提示核对下游画布。原生 EmptyFlux2LatentImage 对宽高整除 16，接受
  1256×1672 时 latent 实测为 `[1,128,104,78]`，像素等效 1248×1664；这是
  下游自身行为，不能因为“能出图”就宣称请求尺寸完全未变化。T8 不替用户
  改动采样器、裁切或 VAE，也不自动把 Layout 的中心移到另一个画布。

## 已实际检查

- 新回归修复前失败，修复后 MOSS Python 57/57、前端总计 92/92 和 Chrome
  合约通过。包括不同轴的 8/16 混合、完整边界、分数像素、越界 padding、
  锁文案、原稿不变和成功恢复。
- 独立 CPU Comfy 真队列 11 场景通过，含三项预期错误。复用真实
  ResolutionSelector 3:4/2 MP/multiple8 → 增强节点，输出仍是 1256×1672；
  Layout 全画布框精确居中为 `[-836,-628,836,628]`；接原生 latent、保存和
  typed 恢复均成功；1257 的越界框仍阻断下游。
- 实际 Chrome 中外接 1256/1672，50 次切换、保存重载、断开重连均保留数值，
  高度维持 614、提示词和宽高端口各行正常，已查看截图。
- 真实 HTTP 是自有 loopback 故障/传参夹具，不是新增真实模型或付费 API
  推理；本轮未加载 GPU 模型，未启停用户 8189/Strata 服务。

本机证据前缀 `G:/CodexHome/.codex/tmp/moss-eight-pixel-`：before 日志保留旧门
失败；queue-20261017、native-ui-20261017、chrome-20261017.log、repo-20261017.log、
old-replay-20261017.json 与 full-20261017.log。自有队列/浏览器在 finally 释放。
本轮未 stage、commit、push 或发布 Registry。
