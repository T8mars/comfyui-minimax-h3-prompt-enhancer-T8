# MOSS 整册／逐图创作

生成时必须连接 **T8 LLM Provider Config → provider_config**，填写需求和实际宽高。
本节点只编写提示词，不生图；与 H3/Seedance 分镜配置无关。

## 选择模式

- **Comic / 漫画卡通**：页数 1–16，0 自动；先整体规划，再逐页英文源稿、中文描述映射。
  参考图是整册上下文，不是每图一本。英中共用画布、可见原文、框、标签和顺序。
- **Fisher / 通用长版**：默认 `independent`，每张参考各一份独立稿；无图一稿。
  只有显式 `fusion` 才把全部参考融合成一张图。只生成所选一种描述语言，自动默认中文。
  自动中文无短版/长度约束时，约 1500–2500 汉字是软目标，不强行补足。

参考按槽号、批次展开排序，合计最多 10 张。云端会收到需求、上下文和参考图，
可能经过渠道上传；本机 Comfy 不等于本地模型，请在共享配置中明确选渠道。

## 接线与费用

输出 0 `bundle_json` → **MOSS Authoring Page T8**；Page 选页码和 `en/zh`。
**只用 Page 输出 0 接正向，1/2 接 INT 宽/高。** 整册、阅读稿、源稿、报告都不是正向。

无纠正时 Comic N 页为 `1 + 2N` 次，Fisher N 稿为 N 次；融合一稿为一次。
每阶段最多追加 1 次纠正（可设 0），不是网络失败自动重试。字数上限按每页每语言
的描述 Unicode 码点统计，不含 Layout 可见文字/JSON/坐标，不是 Tokens；不截断合法稿。

## 修订、恢复与失败

连续性事实写入 `continuity_context`。修订用 `layout_context_json` 的严格类型包装：
`schema_version="t8-moss-authoring-context/v1"`、`mode="full_layout"` 或 `"panels_only"`、
`bundle` 为完整原 bundle 对象、`edit_unit_ids` 为其中实际单元 ID 数组，不是页码。
可解析的完整 JSON 示例见仓库 `docs/moss-image.md` 的“指定页修订与固定布局”。

`preserve_layout=true` 时 full_layout 固定非描述结构，panels_only 固定漫画框/读序/画布。
关闭后也不改已有可见原文。重新接回同内容、同顺序的原参考；未选单元不重写。
外层 `edit_unit_ids=[]` 是零编辑复制，零模型调用，不需 provider 或图片。

“恢复完整集合”只取本进程旧成功，零生成；最多 50 槽、至多 1 小时，重启/淘汰可能丢失。
失败不覆盖成功，不延长旧成功期限。恢复只跳过无关 lazy 依赖，不绕过宿主静态校验。
“只读查看失败稿”不排队：`inspection_only=true`、`complete=false`，不能交给 Page。
同源只读不是多用户隐私隔离；共享实例不要输入敏感资料或密钥。

双语几何一致不等于翻译语义准确或成图验收；4096 目标 Token 未自动测量，
没有真实 LLM 美学收益证明。先人工审稿，再验收实际 MOSS 输出。
