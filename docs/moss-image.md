# MOSS Image Prompt Enhancer T8

独立的 AI 绘画提示词编写节点，不生成图片，不替换原 H3 / Qwen 节点。
官方 Skill 和编译器固定在 OpenMOSS/MOSS-Image 的
`c1355e6b1986dfe8fba3c0455783a05899212342`，保留 Apache-2.0 许可。
[原文](https://github.com/OpenMOSS/MOSS-Image/tree/c1355e6b1986dfe8fba3c0455783a05899212342/skills/moss-image-prompt-enhancer)。

## 最简单的用法

1. 添加 **MOSS Image Prompt Enhancer T8**，填写画面需求，设定最终宽高。
2. 保持“生成 / Generate”和“AUTO”，选择增强语言模型渠道；云端接入 API Key
   或使用已有凭据/环境变量，本地无需。示例的 Key 输入预留为空，不要分享填过密钥的工作流。
3. 将第一个输出 `positive_prompt` 接入 MOSS 工作流的正向文本编码。
   宽、高两个 INT 输出接对应画布；本节点不改采样器、负向、alpha 或模型。
4. 使用 Layout 时可以查看底部“排版结构示意”。这只是框和文字的示意，
   不是生成图片，不证明文字排版美观、渲染保真或语义质量。

普通照片/插画通常用 Caption；明确左右位置、多主体遮挡、海报文字或分栏
可用 Layout。AUTO 只在这两种原生格式中选择，不强迫所有需求变成海报。

## 输入与高级项

- 默认画布 1024×1024，支持 **8 的倍数，范围 16–16384**，例如 1256×1672。
  输入、草稿和输出宽高保持一致，不自动改成 16 倍数。官方快照以 16 倍数为
  基线；T8 的运行时兼容层扩展到 8 倍数，未改动官方原文件。Layout 仍按真实
  像素画布校验边界和居中，不能借临时校验区域接受越界框。
  比例快捷项写入真实像素宽高；需求中明确的画布与 UI 冲突时先报错。
  下游生成节点可能自行对齐尺寸：例如原生 Empty Flux 2 Latent 使用宽高整除
  16，1256×1672 对应 latent 的像素等效尺寸是 1248×1664。提示词节点不替用户
  改动下游采样/裁切逻辑；精确 Layout 应以最终实际画布为准。
- 描述语言可选自动（需求未明确时英文）、English、中文。画面可见文案不随
  描述语言翻译。需严格保留时使用“锁定画面文案”：一整块文字，或 JSON
  字符串数组，例如 `["春日来信", "今天，慢一点。"]`。换行、标点和重复次数
  都必须一致。单个文案块不会被悄悄拆成多个 text item。
- 最大描述字数 0 为自动。Layout 只计 summary/item 的描述，不计坐标、键名和
  锁定文案。它是软约束：不会截 JSON 或删掉必须内容来强行达标。
- 可选参考图片按槽号排序，批次展开后合计最多 10 张（T8 的输入预算，并非
  MOSS 官方编辑能力声明）。参考图只交给增强语言模型观察；并未传给 MOSS
  执行原生图像编辑。视觉容量不足时明确失败，不静默丢图。
- 云端 Token 默认 16384，包含模型思考，与 MOSS 编码器的 4096 不同。
  本地 GGUF 的上下文/输出预算单独设置，纯文字不需要视觉投影器。
- 创作种子不是 MOSS 出图的采样器种子。它参与工作流重新执行及本地语言模型
  采样；不承诺不同云渠道的确定性复现，成图种子仍在原 MOSS 采样器设置。

## 仅校验编译：零模型请求

选择“仅校验编译 / Compile only”，将原始 JSON 填入“原始草稿”。
无需 API Key、GGUF、Strata 或参考图，创作需求可留空。

Caption 草稿为 `{"caption":"A single ivory cup on a plain table."}`。
Layout 是官方原始平面结构：width/height、`bbox_coord_space="abs"`、
`bbox_format="xyxy"`、summary 和 items，坐标是画布内的像素值。
本地编译器转为 `abs_centralized` / `yxyx` 的单行 JSON，去掉画布字段。
不要把已经编译的居中坐标重新当原始草稿输入。

Layout 编译以草稿内画布为准；Caption 使用 UI 宽高作为外部工作流元数据。
生成模式的语言/锁文案/软字数/渠道设置在仅编译模式不参与改写。
重复键、未知字段、NaN/Infinity、越界/反向框、截断 JSON 等均拒绝。

## 渠道与费用

沿用平价小屋、AI 工坊、OpenAI 兼容、本地 GGUF、已启动 Strata 五种路由。
平价默认增强模型 `qwen/qwen3.8-flash-next`，可在高级项改模型 ID；工坊使用
工坊选择器。共享 **T8 LLM Provider Config** 优先于节点上的同类参数。
本地/GGUF 和 Strata 不要求云端密钥；不会替用户启停、切换或下载模型。

“在本机打开 ComfyUI”不等于已选择本地模型：请看“增强渠道 / Provider”，
默认仍是平价小屋 API。要离线增强，请改为“本地 GGUF”，再在高级设置选择模型。
外接提示词、宽高时会显示紧凑的已连接行，保留原始输入和连线；新建、重载或
改变接线时会自动整理 MOSS 节点高度，普通状态刷新不会清除手动拉高的高度。

一次生成首发一次，默认最多额外纠正一次，所有格式、坐标、文案与字数问题
共用这一预算。可以将纠正设为 0。网络失败不自动重新提交付费请求。
后台已完成但本机未收到完整结果，不等于可以凭空从渠道取回正文。

硬校验失败：停止下游，防止无效字符串进入 MOSS；可点“查看失败草稿”复制
并手动编译修正。只有软约束未达标，或可选纠正失败而首稿硬校验通过：保留
完整合法首稿并警告。不会以空字符串假装成功。
但 Strata 服务身份/模型变化、协议、安全配置或整个任务超时仍会停止本次任务，
不会用首稿掩盖这些硬错误。失败不会覆盖之前的成功缓存。

## 六个输出与恢复

| 输出 | 类型 | 用途 |
| --- | --- | --- |
| positive_prompt | STRING | 原生 Caption 文本或编译后 Layout 单行 JSON |
| width / height | INT / INT | 最终画布，恢复时仍为 INT |
| resolved_format | STRING | caption 或 layout |
| draft_json | STRING | 可编辑、可再次校验的原始草稿 |
| report_json | STRING | 请求次数、来源、警告和结构检查，不含密钥 |

“恢复上次成功结果”只取当前 Comfy 进程内的缓存，不新生成、不执行无关模型
依赖。失败/取消不会覆盖上次成功；较早并发任务不会覆盖同槽较新的任务。
缓存有容量/时效限制，重启不保证保留。恢复显示旧结果，不套用当前新设置。
失败草稿是独立、只读、显式查看的内存副本，不自动写入日志或隐藏提示词。
共享 Comfy 实例的管理员可能访问历史、缓存和只读接口；不要输入敏感资料。
云端模式会将需求、锁文案和参考图发送给所选渠道，参考图可能经过其上传接口。

## Token 与质量边界

MOSS 官方编码器对包装后的提示词最多保留 4096 Token。本节点不强制下载目标
Tokenizer，也未在每次编写时测量目标 Token，报告始终标记 `unverified`。
字符数不是 Token 数；超长稿须在实际 MOSS 工作流核验，不承诺不会截断。
JSON、坐标和锁文案通过只证明结构可用，不证明人物、字体、构图或生成质量。
小参数本地模型可能输出不合规 JSON，可换更强模型或 API，并保留实际失败记录。

## 可直接加载的示例

- [Caption 自然图像](../example_workflows/moss_caption_example.json)
- [中文海报 Layout](../example_workflows/moss_layout_example.json)
- [双主体空间关系](../example_workflows/moss_spatial_example.json)
- [离线编译](../example_workflows/moss_compile_only_example.json)
- [故意越界的失败示例](../example_workflows/moss_compile_error_example.json)：预期报错，
  用来确认坏草稿不会输出到下游，不是可直接成功出图的案例。

## English quick guide

Use Generate + AUTO for normal authoring, or choose Caption/Layout explicitly.
Send `positive_prompt` to your MOSS positive text encoder and connect the two INT
canvas outputs to the image workflow. Optional references inform the enhancement
LLM only: this node does not generate or edit images natively.

Compile-only accepts the original native draft offline; Layout uses its own
pixel canvas and the pinned official compiler. Caption preserves prose. One
total optional correction is allowed; invalid drafts stop downstream execution,
while a complete hard-valid first draft survives a failed soft correction.
Last-good recovery performs no inference and restores typed dimensions.

The target 4096-token budget remains unmeasured. Structural validation and the
geometry preview are not rendered-image quality or typography certification.
Keys are not serialized by this node; upstream credential nodes, cloud uploads
and Comfy history retain their own privacy boundaries. No existing node schema
or workflow is modified by the MOSS addition.
