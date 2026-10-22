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

### 主节点强化模式与字数

主界面新增可见的“最大描述字数”和“强化模式”。字数沿用旧字段
`max_output_chars`，没有新增第二个数字位：统计描述正文的 Unicode 码点，
含标点/空白，不含 Layout 的 `text` 可见文案和 JSON/坐标；它是软上限，
不是汉字数、Token 数或 MOSS 4096 Token 的防截断保证。无法同时满足时
保留完整合法稿并显示警告，不截句、不截 JSON。`0` 表示自动。

- `Classic / 原版` 是默认值，保持原消息和单次纠正逻辑；旧工作流自动使用它。
- `Fisher / 通用长版` 按原意充分展开，参考图只写可见证据，局部改图保留
  未指定部分。自动语言默认中文（原语言选项的历史“默认英文”标签仅对
  Classic 有效）；明确选择 English 或明确英文描述要求优先。
  自动中文且无明确短版/长度要求时，约 1500–2500 汉字是创作软目标，
  不是必须凑够的最低字数。设置字符上限后以上限优先。最多一次纠正可将
  过短提纲扩成长稿，但不会为了字数编造参考图中不可见的事实。
- `Comic / 漫画卡通` 根据情绪强度组织故事瞬间、画格、人物演出和文字。
  主节点仍只输出一张图的一种描述语言，支持 Caption 或原生 Layout；
  画框以原生 `object` 加 `comic_panel` tag 表示，不能冒充完整漫画源协议。

两种模式都保留原六输出，只有 `positive_prompt` 接正向。当前主 Fisher
入口不将多个参考图擅自融合：批次展开后若超过一张，会在调用模型前拒绝。
逐图/融合、漫画多页与逐页英中双语使用下面的独立 Director / Page 入口。
两份用户提供 Skill 经过独立规则适配，不是官方 MOSS
格式/审美认证；不会执行 Skill 中的安装、脚本、文件导出或生图指令。

旧 27 个保存字段的位置、六输出和旧五份示例文件不变。新保存仅在末尾
追加第 28 个 `authoring_profile`，并写入版本标记；历史按钮尾值不能开启
新模式。Compile-only 与恢复功能忽略当前强化模式和字数设置，恢复的
历史计数也不会被今天的 UI 参数重算。

- 默认画布 1024×1024，支持 **8 的倍数，范围 16–16384**，例如 1256×1672。
  输入、草稿和输出宽高保持一致，不自动改成 16 倍数。官方快照以 16 倍数为
  基线；T8 的运行时兼容层扩展到 8 倍数，未改动官方原文件。Layout 仍按真实
  像素画布校验边界和居中，不能借临时校验区域接受越界框。
  比例快捷项写入真实像素宽高；需求中明确的画布与 UI 冲突时先报错。
  下游生成节点可能自行对齐尺寸：例如原生 Empty Flux 2 Latent 使用宽高整除
  16，1256×1672 对应 latent 的像素等效尺寸是 1248×1664。提示词节点不替用户
  改动下游采样/裁切逻辑；精确 Layout 应以最终实际画布为准。
- 描述语言可选自动（Classic/单图 Comic 默认英文，Fisher 默认中文）、English、中文。画面可见文案不随
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

## 整册与多参考图：Director / Page

这两个新节点属于 `T8/MOSS Image`，不改 H3/Seedance 的分镜配置，不生成图片。

1. 添加 **MOSS Authoring Director T8**（`MOSSAuthoringDirectorT8`），填写需求，
   选择 Comic 或 Fisher、实际宽高，**生成时必须连接 T8 LLM Provider Config**。
   不接共享配置不会悄悄使用默认云渠道。云端配置会发送需求、上下文和参考图，
   可能经渠道上传接口；离线请显式选择已配置的本地 GGUF。
2. 按需连接 `reference_image_0…9`，批次先展开，合计最多 10 张；顺序按槽号、
   再按批次序号。参考图仍只交给语言模型，不是 MOSS 原生编辑输入。
3. Director 的输出 0 `bundle_json` 接 **MOSS Authoring Page T8**
   （`MOSSAuthoringPageT8`）的同名输入。选择从 1 开始的 `page_index` 和
   `language=en/zh`。每个 Page 节点选一个单元，可并列放多个 Page。
4. **Page 输出 0 `positive_prompt` 接正向编码，输出 1/2 是 INT 宽/高**。
   Director 的整册 JSON、阅读稿，以及 Page 的 source、native draft、report
   都不是正向提示词。不要把这些文本拼接后交给 MOSS。

| 模式 | 单元与语言 | 无纠正时的逻辑生成调用 |
| --- | --- | --- |
| Comic | `page_count=1…16`；0 由模型规划 1–16 页。参考图作为整册上下文，不是每图一本。每页英文源稿后接中文描述映射 | 新建 N 页为 `1 + 2N`：1 次规划，每页源稿/翻译各 1 次 |
| Fisher independent（默认） | 每张展开后的参考图各生成一份独立完整稿；不借用别图/前稿。无图生成 1 稿 | N 张参考为 N 次；无图 1 次 |
| Fisher fusion（显式选择） | 全部参考图按需求融合成一张图的一份稿 | 1 次 |

Fisher 只生成所选的一种描述语言，自动默认中文；需英文请明确选择 English。
Comic 固定英中双语，忽略 Fisher 的语言/参考方式选项；Fisher 忽略漫画页数。
Comic 页内保留 `comic_panel` 源标签、读序、元素归属、版式与连续性注记；
编译时只转换一份副本为原生 MOSS 格式，不把规划注记泄漏进正向。
50 种漫画手法按场面选用，没有使用配额或强迫复杂版式。

字数上限按**每页、每种语言**独立统计。中文和英文只是描述字段不同，
可见文案、画布、框、标签和顺序共用同一结构；这证明几何不漂移，**不证明
译文语义准确、文字可读或最终美观**。Fisher 长版也没有真实 LLM 美学收益证明。
需要人工核对阅读稿，再在实际 MOSS 工作流验收成图与目标 Token 长度。

### 阶段预算、失败与整册恢复

`max_corrections` 为 0 或 1，每个规划/源稿/翻译阶段分别最多追加一次纠正。
因此新建 Comic N 页最多 `2 + 4N` 次逻辑生成，Fisher N 稿最多 `2N` 次；
这不是承诺自动多次重试网络错误。报告分别记录逻辑生成、HTTP POST 尝试及纠正。
硬校验失败、取消或安全/服务身份/整个任务超时会停止下游，不把半册当完成。
软字数目标无法达到时可保留完整合法稿，绝不截 JSON 或在坏稿后继续成图。

Director 的“恢复上次成功结果”只恢复本进程同槽的完整集合，零模型调用，
不套用当前参数；仅跳过无关 lazy 依赖，不绕过宿主整图静态校验。
缓存最多 50 个槽，成功结果保留至多 1 小时；失败不刷新旧成功结果的期限，
失败/取消和较早并发任务不能覆盖新成功。重启或容量淘汰后不能保证恢复。

“查看失败草稿”通过同源只读接口显式查看，最多 2 MiB，可能标记 `truncated`。
它可以包含已完成英文源页，但始终是 `inspection_only=true`、`complete=false`，
不是可供 Page 使用的 bundle，不会自动排队或重新调用模型。
同源限制不是多用户隔离；共享 Comfy 管理员/同源访问者仍可能接触缓存内容。
请勿输入敏感内容，也不要把 API Key 放进需求、连续性或 JSON。

### 指定页修订与固定布局

`continuity_context` 是用户明确给出的人物、服装、场景与当前状态事实，
不会伪装成跨会话记忆。需要继承整册时，将**完整成功 bundle 对象**放进
`layout_context_json` 的 `bundle` 字段，不是字符串路径，不是已编译正向，
也不是把整册直接粘在字段顶层。精确格式如下（最小 Fisher 离线源稿示例，
不是模型效果样张；省略字段或加入注释均不合法）：

```json
{
  "schema_version": "t8-moss-authoring-context/v1",
  "mode": "full_layout",
  "bundle": {
    "schema_version": "t8-moss-authoring-bundle/v1",
    "adapter_revision": "t8-moss-authoring/1",
    "complete": true,
    "profile": "Fisher / 通用长版",
    "reference_mode": "independent",
    "units": [{
      "unit_id": "image-1", "index": 1, "width": 1024, "height": 1024,
      "reference_indices": [], "available_languages": ["en"],
      "sources": {"en": {"caption": "A single ivory cup on a plain wooden table, lit softly from the left."}},
      "sidecar": null
    }],
    "reference_map": [], "edited_unit_ids": [], "continuity_context": "",
    "report": {
      "logical_generation_calls": 0, "chat_post_attempts": 0, "correction_calls": 0,
      "stage_records": [], "semantics_verified": false,
      "translation_quality": "unverified", "bilingual_complete": false,
      "image_generation_performed": false
    }
  },
  "edit_unit_ids": ["image-1"]
}
```

使用本例时将 Director 设为 Fisher、`independent`、English，在需求中填写
实际修改，例如“仅把杯子改成深蓝色，其余不变”；生成仍须连接共享配置。
真实漫画修订应替换为实际 bundle，并从其 `units[].unit_id` 取页 ID，
例如仅选第二页的真实 ID；不要把 `page_index=2` 当稳定 ID。
`preserve_layout=true` 时，`full_layout` 固定全部非描述结构；`panels_only`
固定画布、画框和读序，允许调整格内人物/物件布局。Fisher 保留原生非描述结构。
关闭 `preserve_layout` 可改布局，但已有可见文案块仍须原样保留；若要改文案，
须先在上下文源稿中有意修改并重新通过结构校验；双语页的共用字段要同步修改。

修订前重新连接原参考图，槽/批次顺序和原内容摘要必须一致；摘要只绑定张量
内容，不证明人物身份。Comic 页数、Fisher 参考方式不得与上下文冲突；修订使用
上下文中各页的原宽高。未选单元逐项保留，不让模型重写。
仅修改 Comic K 页为 `1 + 2K` 次基础调用，不是重跑全部页。
将外层 `edit_unit_ids` 设为 `[]` 是合法的零编辑复制：校验完整集合后零调用，
不需要 provider、brief 或重新加载参考图，也不代表验证过创作质量。

Page 只校验并编译所选源稿，始终零模型调用。缺少所选语言会报错，
不会自动翻译或回退；Fisher 的单语言稿需选实际存在的语言。
也可直接把完整 bundle 粘进 Page 的文本框离线选页；JSON 不做动态提示词展开。

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

先保存当前画布，再导入 JSON。以下新示例只编写/展示文本，不包含 MOSS 生图模型：

- [零模型 CPU 选页（最易入门）](../example_workflows/moss_authoring_cpu_page.json)：内置手工双语教学 bundle，直接运行；切换页码 1/2、en/zh，无 API 或模型。
- [Comic 两页双语](../example_workflows/moss_authoring_comic_two_pages.json)：共享配置 → Director → 两个 Page；默认展示第一页 en/zh，改页码看第二页。
- [Fisher 两图独立](../example_workflows/moss_authoring_fisher_independent.json)：两图对应两个单元，Page 1/2 分别选取。
- [Fisher 显式两图融合](../example_workflows/moss_authoring_fisher_fusion.json)：两图融合为一个单元，只选 Page 1。
- [固定布局修订第二页](../example_workflows/moss_authoring_fixed_layout_revision.json)：内置 typed context，只改 `page-2`，保留 `page-1`；外层编辑列表改 `[]` 可验证零调用复制。
- 主节点：[Fisher 自动长版](../example_workflows/moss_authoring_fisher_long.json) / [Fisher 300 字符短版](../example_workflows/moss_authoring_fisher_short.json) / [单图 Comic](../example_workflows/moss_authoring_comic_single.json)。

两个多参考图示例均需先下载本项目原创教学图
[independent JPG](../example_workflows/moss_authoring_fisher_independent.jpg) 和
[fusion JPG](../example_workflows/moss_authoring_fisher_fusion.jpg)，分别拖入两个 LoadImage
上传（或用自己的两张图）。工作流不会自动把仓库图片写入 `ComfyUI/input`。
除纯 CPU 选页与零编辑复制外，生成示例都须先设置共享 provider；可能产生调用费用。
教学稿/示意图不是实际模型成图或审美收益证明。

原五份 Classic 示例保持不变：

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

For multiple pages/references, use **MOSS Authoring Director T8 → MOSS Authoring
Page T8**. Generation requires shared provider config. Comic uses one plan plus
two stages per edited page and paired English/Chinese caption sources; Fisher
defaults to independent per-reference units, with fusion only by explicit choice.
Select a 1-based page and existing language; wire only Page outputs 0/1/2 to
positive/width/height. Bundles, source drafts and reports are not positive prompts.
Typed revision context preserves unselected units; an empty edit scope and
last-good recovery perform no inference. Failed partials are inspection-only.

The target 4096-token budget remains unmeasured. Structural validation and the
geometry preview are not rendered-image quality or typography certification.
Keys are not serialized by this node; upstream credential nodes, cloud uploads
and Comfy history retain their own privacy boundaries. No existing node schema
or workflow is modified by the MOSS addition.
