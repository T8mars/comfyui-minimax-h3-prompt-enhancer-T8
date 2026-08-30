<p align="right">
  <strong>简体中文</strong> | <a href="./README_EN.md">English</a>
</p>

## 入口导航

| 入口 | 适合用户 | 说明 | 打开 |
| --- | --- | --- | --- |
| 贞贞的平价AI小铺（国内版） | 国内用户、国内模型优先 | 主要调用国内模型，适合国内模型工作流。 | <a href="https://api.seedance.nz/sign-up?aff=5f4w"><kbd>进入国内版平价AI小铺</kbd></a> |
| 贞贞的AI工坊（海外版） | 海外用户、海外模型优先 | 主要调用海外模型，也包含部分国内模型。 | <a href="https://ai.t8star.org/register?aff=dP7j"><kbd>进入海外版AI工坊</kbd></a> |
| RunningHub APIKEY（国内版） | 需要适配更多 AI 应用的国内用户 | 适配更多 AI 应用，并可体验最新模型。 | <a href="https://www.runninghub.cn/user-center/1819214514410942465/webapp?inviteCode=rh-v1121"><kbd>获取国内版 APIKEY</kbd></a> |
| RunningHub APIKEY（海外版） | 海外模型、更宽松审核场景 | 审核更宽松，支持海外模型。 | <a href="https://www.runninghub.ai/user-center/1907375370302308353/webapp?inviteCode=rh-v1121"><kbd>获取海外版 APIKEY</kbd></a> |

# ComfyUI MiniMax-H3 / Seedance 2.0 / Music 3 Prompt Enhancer T8

一组面向 MiniMax-H3、Seedance 2.0 视频生成和 MiniMax Music 3 音乐生成的 ComfyUI 提示词增强节点。H3 与 Seedance 2.0 节点支持文字与真实 `IMAGE` / `VIDEO` 素材；Music 3 节点只处理文字，并把歌词、官方 Structured Caption 和可直接交给下游的 JSON 分开输出。三个节点均可选择贞贞平价小屋、贞贞的 AI 工坊、用户自己的 OpenAI 兼容接口，或本地 llama.cpp 兼容 GGUF。

三个节点共享已经验证的 API、密钥和错误处理，但提示词协议完全隔离：MiniMax-H3 使用其官方字段、任务类型和时间码；Seedance 2.0 使用任务意图、`镜头N` 事件顺序和官方多模态引用语法；Music 3 严格执行官方 `music-caption-rewriter` 的三段描述合同。Music 3 是独立音乐模型，不是 H3 视频模型。

## 社区与资源链接

| 资源 | 链接 |
| --- | --- |
| B站 | [T8 的哔哩哔哩空间](https://space.bilibili.com/385085361) |
| YouTube | [T8star-Aix](https://www.youtube.com/@T8star-Aix/) |
| API | [获取贞贞 API Key](https://api.seedance.nz/sign-up?aff=5f4w) |
| 在线 AI 应用 | [RunningHub 在线应用与作品](https://www.runninghub.ai/zh-cn/user-center/1907375370302308353/userPost?inviteCode=rh-v1121) |
| ComfyUI 整合包 | [夸克网盘下载](https://pan.quark.cn/s/264edb7e36bd) |
| 模型网盘 | [夸克网盘下载](https://pan.quark.cn/s/c9c267081fbf) |
| Hugging Face | [t8star](https://huggingface.co/t8star) |

## 三个独立节点

| 节点 | 用途 | 主要任务 |
| --- | --- | --- |
| `MiniMax H3 Prompt Enhancer (Cloud / Local GGUF)` | 生成 MiniMax-H3 提示词 | T2VA / I2VA / FL2VA / L2VA / Ref2VA |
| `Seedance 2.0 Prompt Enhancer (Cloud / Local GGUF)` | 生成 Seedance 2.0 提示词 | T2V、首帧、首尾帧、多模态参考、编辑、延长、轨道补齐和组合任务 |
| `MiniMax Music 3 Prompt & Lyrics Enhancer (T8)` | 生成 Music 3 歌词与音乐描述 | AUTO、生成歌词、严格保留、局部润色、纯器乐 |

本项目目前不包含 Seedance 2.5 提示词节点，也不调用视频或音乐生成、轮询、试听或下载接口。

## 功能特点

- 平价小屋固定视觉模型 `bytedance/doubao-seed-evolving`；AI 工坊默认 `gemini-3.5-flash` 并支持 Custom；OpenAI 兼容模式支持填写供应商自己的视觉模型 ID。
- 云端视觉渠道分析文字、图片和完整视频；本地 GGUF 明确使用真实时间戳抽样帧与有序联系表，只推断可见时序，不读取音轨，也不冒充完整视频字节理解。
- 支持首帧、尾帧、首尾帧以及多图、多视频参考。
- 集成 MiniMax-H3 官方核心 Skill，规则冻结于经审阅的官方提交 `d21241f0a4b3acbb34c97dae47fa417b7065e438`，并固定全部 4 个文件及归一化内容树哈希。
- 支持现有中英文兼容协议，以及官方所有说明字段强制英文的严格协议。
- 官方共 9 个 Skill：1 个 H3 核心写作 Skill 始终启用，另有 `无 / AUTO` 和全部 8 个可选场景写作 Skill；其中“音乐 MV 动态字幕（官方）”已同步 MiniMax `music-video-subtitle-generator` v0.6.6。选择具体场景 Skill 后，节点内会显示用途、适用范围、推荐输入、结构锚点、可安全填入的示例、MiniMax 官方 GIF 与来源链接。8 个场景 Skill 的完整原生流程依赖 MiniMax Hub agent/canvas/hub 工具；本节点只适配其中可落入单条 H3 提示词的写作约束，不运行或声称移植资产生成、审批、剪辑、画布或外部工作流。
- 两个节点共享独立的 `非官方模板（案例 / 社区 Skill）` 列表：375 条已发布案例事实归并为 213 个稳定案例 selector（含 162 个同机制证据变体），另有 2 个独立用户贡献社区 Skill，共 215 个非官方下拉项；全部提供中文名称、用途、简约推荐输入、2–5 个结构锚点和随 GitHub 直接分发的轻量 GIF 预览。
- 支持中文 / English 输出。
- 支持 `strict / balanced / creative` 三档改写。
- 支持 `AUTO` 或固定 1–20 个镜头的下拉控制。
- 支持用户参考模板融合，主提示词与可观察媒体事实优先。
- 提供随机种子以及 `fixed / randomize / increment / decrement` 状态。
- 提供节点内 API Key 输入、遮罩显示、保存、清空和注册链接。
- 支持贞贞平价小屋、贞贞的 AI 工坊、显式配置的 OpenAI 兼容接口，以及免 API Key 的本地 llama.cpp GGUF；Qwen3.8 两个固定型号继续实测支持，同时开放其他 llama.cpp 兼容文字模型与带匹配 mmproj 的视觉模型。
- H3/Seedance 输出单一提示词 `STRING`；Music 3 分别输出歌词、Structured Caption、payload JSON 和安全增强报告四个 `STRING`。
- 新增独立 Seedance 2.0 节点：简单/复杂双路径、AUTO/固定 1–20 镜头、官方/Seedance.nz 引用语法、字幕与稳定性策略。
- 新增独立 Music 3 节点：完整内置官方 `music-caption-rewriter`、18 个流派索引和 1000 个模板，并严格按 router → 最多 2 个索引 → 最多 3 个模板逐级披露，绝不会把全库塞进一次 LLM 请求。
- Music 3 的官方 Caption 与歌词完全分离；生成/润色歌词属于清楚标注的 T8 非官方扩展，严格保留模式不会改动用户歌词。
- T8 案例支持独立浏览器：按分类筛选、搜索、收藏、最近使用和单 GIF 懒加载预览；原有下拉值与工作流 selector 保持兼容。
- 三个节点提供 ComfyUI 原生进度和仅驻留内存的脱敏执行诊断；诊断不保存 API Key、URL、提示词、歌词、模板正文、媒体或模型推理。
- 三个节点新增“渠道能力预检”和“查看/复制脱敏诊断”入口；OpenAI 兼容未知渠道不会被标记为已验证视觉模型。
- 可选 `T8 LLM Provider Config` 辅助节点可统一渠道、模型、Base URL、本地 Qwen 设置、`temperature` 策略和白名单参数；断开后立即恢复三个原节点自己的值。
- 可选本地凭据别名让工作流只保存别名、真实 Key 留在 ComfyUI 用户目录；原有 API Key `STRING` 接线和工作流保存方式继续可用并具有更高优先级。
- 可选 `T8 Prompt Inspector` 只在本地检查 H3、Seedance 2.0 与 Music 3 的可复算结构，原文逐字直出、只给非阻塞警告，不调用 LLM 或判断创意质量。
- T8 模板浏览器支持确定性的本地 Top-3 推荐与 2–3 项并排对比；推荐不会自动改动当前模板，也不会把用户输入或 GIF 发到外部服务。

## 可选的 P0/P1 辅助节点

`T8 LLM Provider Config`、`T8 Prompt Inspector`、`T8 Prompt Text` 和 `T8 Show Text` 是仓库自带的辅助节点，不替代三个核心 enhancer，也不改变它们的既有输出。`T8 Prompt Text` 可替代第三方多行文本输入节点，`T8 Show Text` 可在节点内只读显示并原样透传 `STRING`。三个核心节点末尾只追加一个无 widget 的可选 `provider_config` socket，因此旧工作流的 31/35/38 个序列化 widget、API Key `STRING` 接线、默认渠道和输出顺序保持不变。

### “共享 LLM 渠道配置”怎么连接

绿色的“共享 LLM 渠道配置（可选）”不是 `STRING`，不能连接普通文本或 API Key 节点。请搜索并添加 `T8 LLM 共享渠道配置`，把它右侧的“渠道配置”输出接到 H3、Seedance 2.0 或 Music 3 节点同名输入：

1. “共享渠道”选择 `Local Qwen`、平价小屋、AI 工坊或 OpenAI Compatible。
2. 本地模式从 `ComfyUI/models/LLM` 递归发现主模型；H3/Seedance 分析图片或视频采样帧时把视觉投影器设为 `AUTO（自动匹配）` 或显式选择对应 mmproj，Music 3 会忽略视觉投影器。
3. 本地模式不填 API Key；云端可继续把普通 `STRING` Key 直接接到原节点，或在共享配置中使用本地凭据别名。
4. 连接共享配置后，以共享节点中的渠道、模型和本地参数为准；断开连接会立即恢复原节点自身设置。
5. 不想使用共享节点时，也可以直接在任一核心节点的 API 模式中选择“本地 GGUF（llama.cpp / Qwen，离线）”。旧工作流保存的“本地 Qwen3.8-27B”值仍会正常执行。

共享配置的凭据优先级为：原节点执行时收到的 `api_key`（包括外部 STRING 接线或已保存值）→ 本地凭据别名 → 原节点既有环境变量后备。凭据管理器可列出、保存、更新、删除和显式测试云端连接；测试连接会先提示并只发送一次最小请求，界面不显示 Key、URL 或上游正文。

OpenAI 兼容默认继续发送 `temperature`，保持 1.2.0 行为。只有已知 Kimi Coding Plan 地址的 `AUTO` 策略会省略该字段，也可在共享配置中显式选择发送或省略。附加参数只接受白名单，不能覆盖模型、消息、鉴权、媒体或流式控制等核心字段。

## T8 创作导演套件（独立辅助节点）

创作导演套件扩展的是“策划、探索、修改和交付”链路，不替代三个核心 enhancer。三个核心 Node ID、既有 widget 顺序、默认值和输出保持不变；不使用这些新节点的旧工作流不需要迁移。

| 节点 | 是否调用 LLM | 用途 |
| --- | --- | --- |
| `T8 Creative Director` | 否 | 建立人物、世界、视觉、动作、声音等统一创作总纲，维度支持 `LOCK / EVOLVE / AUTO` |
| `T8 Creative Context Assembler` | 否 | 把总纲、素材角色、DNA 和个人预设组装成可接现有核心节点的 `STRING` |
| `T8 Directed Revision` | 1 次 | 只修改点名范围，输出修订结果、报告与本地 diff |
| `T8 Long-form Planner` | 1 次 | 任意正整数总时长拆段，分别输出 H3、Seedance 2.0 和段间交接 JSON |
| `T8 Reference Role Mapper` | 1 次 | 分析用户实际连接的图片/视频，分配身份、服装、场景、动作、镜头、风格和禁止借用角色 |
| `T8 Creative Candidate Lab` | 1 次 | 一次生成 2–4 个创作机制不同的候选及软比较 |
| `T8 Candidate Selector` | 否 | 从候选 JSON 本地选择一个方向 |
| `T8 Storyboard Pack` | 1 次 | 输出全局提示词、分镜、关键帧图像提示词、转场/声音与素材绑定 |
| `T8 Creative DNA Mixer` | 否 | 最多融合三个 T8 非官方案例的结构、镜头和高潮/收尾机制，不发送案例媒体 |
| `T8 Personal Creative Preset` | 否 | 在工作流内保存用户自己的文字型创作规则，不修改内置库或写外部文件 |
| `T8 Music Creative Lab` | 1 次 | 歌词/Caption 候选、定向歌词修改、歌曲标题和中日韩文字层软 QA |
| `T8 Creative Version Stack` | 否 | 保存、选择和回退最多 8 个提示词、歌词或 Caption 版本 |
| `T8 Music-to-Video Beat Sheet` | 1 次 | 根据歌词、Caption 和用户已知 BPM/时间点生成 H3/Seedance 视频节拍表 |

需要 LLM 的节点默认使用 Seedance NZ；推荐连接 `T8 LLM Provider Config`，统一选择平价小屋、AI 工坊、OpenAI Compatible 或本地 GGUF。每次执行只有一次逻辑生成请求；Seedance NZ 遇到已确认安全重试的 500/502/503/504/520–530 网关状态时最多进行 6 次有界传输尝试，401/402/429 和可能已完成计费的读超时不会盲目重复。上游返回非空但没有命中 JSON 时，节点保留原文并在报告中标记 `structured_response=false`，不会因为创意评分或格式偏差丢弃内容。

候选的七维软分数由节点对最终文本做确定性的本地启发式计算，不要求模型额外“自评分”，不冒充客观艺术质量，也不阻塞非空候选。分镜包只让模型返回一次逐镜合同，关键帧表与转场/声音表在本地从逐镜字段派生，避免付费响应重复同一内容。2026-08-28 使用真实 `bytedance/doubao-seed-evolving` 完成 7 类脱敏验收：候选、定向修改、长片分段、4 镜头分镜、多模态角色映射、中文歌词候选和 5 镜头音乐节拍表均通过二值合同检查；该验收分数不等于主观艺术评分。

素材边界：Reference Role Mapper 只会读取用户直接连接到该节点的媒体。官方/T8 案例 GIF、来源视频和人类预览永远不会作为模型参考素材。本地 GGUF 的视频理解仍只基于带真实时间戳的采样画面，不分析音轨；Music-to-Video Beat Sheet 没有 AUDIO 输入，不会声称听歌、检测 BPM 或转写歌词。

推荐连接方式：

1. `T8 Creative Director` → `T8 Creative Candidate Lab` / `T8 Long-form Planner` / `T8 Storyboard Pack`。
2. 有素材时先运行 `T8 Reference Role Mapper`，把 `reference_context_for_enhancer` 接到现有 H3 的“参考素材补充”，或把角色表接到 `T8 Creative Context Assembler`。
3. `Candidate Lab` → `Candidate Selector` → 现有 H3/Seedance 的主提示词，或继续进入 `Storyboard Pack`。
4. `Music Creative Lab` 的候选可进入 `Creative Version Stack`；选定歌词与 Music Caption 再进入 `Music-to-Video Beat Sheet`。

## 1.1.0 更新

- 新增免 API Key 的本地 Qwen3.8-27B GGUF 渠道，并支持官方与第三方 Uncensored Q4_K_M 变体、视觉投影器、显存释放、执行后卸载策略和真实时间戳视频联系表。
- MiniMax H3 核心 Skill 更新为固定官方快照；维护工具可核验内容树，并由每周工作流只读检查 H3 核心、8 个官方创意 Skill 和 Music 3 官方 Skill 的上游路径是否发生变化。
- 385 个官方/T8 GIF 全部保留；GitHub 完整克隆继续内置全部预览，Registry 包仅内置 8 个官方 GIF，377 个 T8 GIF 改由独立版本化资源通道按需获取，避免案例增长再次触发 Registry 体积限制。
- 提供 13 个 ComfyUI 原生 `example_workflows` 与同名缩略图：原有 9 个基础/本地工作流保持不变，另增 4 个创作导演套件组合案例；全部示例不依赖 Comfyroll、EasyUse 等第三方节点。
- 三种云端渠道统一使用一个经过测试的传输层，同时保留各自既有付费重试、HTTP 分类和错误文案；不记录请求或响应正文。
- 新增版本门禁、密钥/大文件/JSON/GIF 预算检查、Changelog、License、Registry 元数据与发布前 CI。
- 旧工作流迁移规则和稳定接口见 [`COMPATIBILITY.md`](./COMPATIBILITY.md)。

## 安装

> **更新建议：优先从 GitHub 更新。** 当 Registry 的新版本处于审核、`Pending` 或 `Flagged` 状态时，ComfyUI-Manager 可能自动回退安装较旧的 `Active` 版本；界面虽然会显示“安装/重装成功”，但新节点、新功能和紧急修复仍然不可用。更新后必须完整重启 ComfyUI，并对浏览器执行一次 `Ctrl+F5`。不要在 `custom_nodes` 中保留本插件的多个副本。

### GitHub 安装 / 更新（推荐）

首次安装时，在 ComfyUI 的 `custom_nodes` 目录执行：

```bash
git clone https://github.com/T8mars/comfyui-minimax-h3-prompt-enhancer-T8.git
```

已经通过 Git clone 安装时，在插件目录执行：

```bash
git pull --ff-only
```

如果原来通过 Manager 或 ZIP 安装，更新前请先关闭 ComfyUI，把旧插件目录移出 `custom_nodes`，再克隆到唯一的标准目录；不要让旧目录与新目录同时存在。目录结构应为：

```text
ComfyUI/
└─ custom_nodes/
   └─ comfyui-minimax-h3-prompt-enhancer-T8/
```

### ComfyUI-Manager / Registry

在 ComfyUI-Manager 的节点管理器中搜索：

```text
MiniMax H3 / Seedance 2.0 / Music 3 Prompt Enhancer (T8)
```

也可以使用 Comfy CLI：

```bash
comfy node install minimax-h3-seedance-music3-prompt-enhancer-t8
```

Registry 发布包会包含节点运行代码、官方 Skill、非官方案例库、8 个官方 GIF 和一份轻量资源通道清单；377 个 T8 GIF 不再塞入 Registry ZIP。用户查看某个 T8 案例时，节点默认只下载该案例所在的小分片并缓存到 `ComfyUI/user/t8_prompt_enhancer/preview_assets`。发布包仍不包含测试、来源批次、API Key、独立 `llama-server` 运行时、安装/下载脚本或 GGUF 模型。Manager 安装的本地 GGUF 模式使用当前 ComfyUI Python 中的 `llama-cpp-python`；如果需要固定 `llama-server`、PATH 自动回退、环境变量默认值或显式连接探测，请按上面的推荐方式从 GitHub 完整安装。

云端模式不增加额外 Python 依赖，使用 ComfyUI 已安装的 `requests`、NumPy、Pillow 和原生媒体类型；本地视频抽样复用 ComfyUI 自带的 PyAV。安装后重启 ComfyUI；如果节点或前端界面没有更新，请对浏览器执行一次 `Ctrl+F5`。

在节点菜单中搜索任一节点：

```text
MiniMax H3 Prompt Enhancer (Cloud / Local GGUF)
Seedance 2.0 Prompt Enhancer (Cloud / Local GGUF)
MiniMax Music 3 Prompt & Lyrics Enhancer (T8)
```

## 快速使用

1. 添加 `MiniMax H3 Prompt Enhancer (Cloud / Local GGUF)`。
2. 在“视频创意 / 提示词”中输入基础意图。
3. 选择生成类型、时长、镜头数量、改写模式、输出语言、官方 Skill 协议和 MiniMax 官方创意预设；需要时再选择一个非官方案例或社区 Skill 模板。
4. I2VA / FL2VA / L2VA / Ref2VA 按任务要求连接图片或视频。
5. 云端渠道填写 API Key；本地 Qwen 渠道不需要 Key。
6. 点击节点底部的“运行提示词优化”。
7. 从 `enhanced_prompt` 获取最终字符串。

可以直接把 [`example_workflows/minimax_h3_prompt_enhancer_example.json`](./example_workflows/minimax_h3_prompt_enhancer_example.json) 拖入 ComfyUI。示例工作流不包含 API Key；同目录 JPG 是 ComfyUI 模板缩略图。

## MiniMax Music 3 快速使用

1. 添加 `MiniMax Music 3 Prompt & Lyrics Enhancer (T8)`。
2. 在“音乐创意”中写明风格、主题、情绪、用途和希望的编曲发展。
3. 选择歌词模式：`AUTO / 生成新歌词 / 严格保留歌词 / 按要求润色 / 纯器乐`。已有歌词可以通过普通 `STRING` 接入。
4. “官方完整（2–4 次请求）”会按官方逐级披露选择参考；“快速核心（1–2 次请求）”只执行官方核心合同。调用次数取决于是否还要生成或润色歌词，不会同时调用三个供应商。
5. 云端渠道填写当前 API Key；本地 Qwen 不需要 Key。点击“运行 Music 3 提示词与歌词优化”。
6. 将 `lyrics` 接到 Music 3 的 `input`，将 `music_caption` 接到 `instructions`；也可以直接解析 `music3_payload_json`。
7. `enhancement_report_json` 只记录阶段、付费请求数、缓存命中、官方快照哈希、Token 预算估算与警告代码，不包含歌词、用户创意、API Key、供应商 URL、模板 ID 或模板正文。

可以直接导入 [`example_workflows/music3_prompt_lyrics_enhancer_example.json`](./example_workflows/music3_prompt_lyrics_enhancer_example.json)。示例不包含 API Key、音频或官方模板正文。

## Seedance 2.0 快速使用

1. 添加 `Seedance 2.0 Prompt Enhancer (Cloud / Local GGUF)`。
2. 填写“视频创意 / 提示词”。任务意图、组织方式、时长和镜头数都可先保持 `AUTO`。
3. 按任务连接首帧、尾帧、参考图片或完整参考视频。
4. 选择官方中文 `@图片N/@视频N` 或 Seedance.nz 英文 `@Image N/@Video N` 引用格式。
5. 可选一个 `非官方模板（案例 / 社区 Skill）`，用于迁移因果结构、节奏和镜头语法。
6. 云端渠道填写“提示词增强 LLM API Key”；本地 Qwen 不需要 Key。然后点击节点底部运行按钮。
7. 把 `enhanced_prompt` 连接到下游 Seedance 2.0 视频节点的提示词输入。

可以直接导入 [`example_workflows/seedance20_prompt_enhancer_example.json`](./example_workflows/seedance20_prompt_enhancer_example.json)。示例不包含 API Key。

## 示例工作流

| 示例 | 用途 |
| --- | --- |
| [`minimax_h3_prompt_enhancer_example.json`](./example_workflows/minimax_h3_prompt_enhancer_example.json) | H3 云端基础示例 |
| [`seedance20_prompt_enhancer_example.json`](./example_workflows/seedance20_prompt_enhancer_example.json) | Seedance 2.0 云端基础示例 |
| [`music3_prompt_lyrics_enhancer_example.json`](./example_workflows/music3_prompt_lyrics_enhancer_example.json) | Music 3 云端基础示例 |
| [`basic_workflow_multi_task_connections.json`](./example_workflows/basic_workflow_multi_task_connections.json) | 一个共享配置同时连接 H3、Seedance 2.0 与 Music 3；只使用本仓库节点 |
| [`minimax_h3_local_qwen_example.json`](./example_workflows/minimax_h3_local_qwen_example.json) | H3 + 共享配置 + 本地 Qwen3.8-27B |
| [`seedance20_local_qwen_example.json`](./example_workflows/seedance20_local_qwen_example.json) | Seedance 2.0 + 共享配置 + 本地 Qwen3.8-27B |
| [`music3_local_qwen_example.json`](./example_workflows/music3_local_qwen_example.json) | Music 3 + 共享配置 + 本地 Qwen3.8-27B，不加载 mmproj |
| [`prompt_inspector_local_qwen_example.json`](./example_workflows/prompt_inspector_local_qwen_example.json) | H3 本地增强后接 T8 Prompt Inspector 本地结构检查 |
| [`text_utilities_example.json`](./example_workflows/text_utilities_example.json) | 仓库自带 T8 Prompt Text → T8 Show Text，演示标准 STRING 输入、显示与透传 |
| [`creative_direction_revision_example.json`](./example_workflows/creative_direction_revision_example.json) | 创作总控 → 多方案实验室 → 候选选择 → 定向修改 |
| [`creative_longform_storyboard_example.json`](./example_workflows/creative_longform_storyboard_example.json) | 共享创作总纲驱动长视频分段与分镜创作包 |
| [`creative_music_video_suite_example.json`](./example_workflows/creative_music_video_suite_example.json) | 音乐候选、版本选择与 H3/Seedance 2.0 音乐视频节拍导演 |
| [`creative_reference_dna_preset_example.json`](./example_workflows/creative_reference_dna_preset_example.json) | 素材角色、T8 Creative DNA、个人预设组装为旧增强节点可接收的 STRING 上下文 |

所有内置工作流均不包含 API Key。涉及三个原有核心节点的工作流继续保存完整的 31/35/38 项控件数组；旧版 21/22、25/26、31 项工作流会在下拉值校验前自动补齐本地 Qwen 默认值，避免把 `randomize` 错读为 GGUF 模型。

### Seedance 2.0 任务意图

| 选项 | 用途 | 素材规则 |
| --- | --- | --- |
| `AUTO` | 按意图和已连接素材判断 | 无歧义时自动选择 |
| `T2V` | 文生视频 | 不连接素材 |
| `I2V` | 首帧图生视频 | 只连接 `first_frame` |
| `FL-I2V` | 首尾帧过渡 | 连接 `first_frame` 与 `last_frame` |
| `多模态参考生成` | 借用图片或视频中的主体、动作、运镜、风格等 | 至少连接一个参考素材 |
| `视频编辑` | 对已有视频增删改 | 至少一个参考视频，提示词直接写 `@视频N` |
| `视频延长` | 向前或向后延长 | 恰好一个参考视频 |
| `轨道补齐` | 在视频间生成衔接 | 2–3 个参考视频 |
| `组合任务` | 参考一个素材并编辑另一个视频 | 被编辑视频加至少一个其他素材 |

视频编辑与组合任务默认把 `@视频1` / `@Video 1` 作为被编辑目标；其他连接素材是支持参考。需要不同角色时，在高级“素材用途”中明确指定。

### Seedance 2.0 提示词组织

- 官方八要素按需补齐：主体、动作、场景、光影色调、单一主运镜、风格、画质和约束。
- 简单任务使用一个紧凑自然段；复杂任务才使用 `镜头1 / 镜头2 / 镜头3`。
- 镜头数支持 `AUTO` 或固定 1–20。固定镜头是传给 LLM 的软生成约束；时长较短却使用较高镜头数时，上游可能合并或省略镜头，节点不会因此判错。
- 目标时长支持 `AUTO` 或手动输入任意正整数秒数，节点不设上限；它只控制提示词整体内容密度，不生成毫秒级时间码，也不默认写逐镜头绝对秒数。下游视频模型或工作流自身的时长限制仍然有效。
- 编辑、延长和组合任务直接指代 `@视频N`，不写成“参考 @视频N”。
- “素材用途”可补充 `@图片1=人物外观；@视频1=动作和运镜`，但不能替代真实素材分析。
- “参考模板融合”只迁移结构、节奏、运镜、转场、风格和声音设计，不复制模板中的人物、道具和剧情事实。

### Seedance 2.0 音频边界

Seedance 2.0 目标视频模型能够处理音频，不代表提示词增强渠道能分析音频文件。2026-08-05 的真实能力探测中，平价小屋/兼容模式使用的 `bytedance/doubao-seed-evolving` 明确拒绝 OpenAI 兼容 `input_audio`，返回“audio input is not supported by this model”。新增 AI 工坊渠道不会改变本节点的输入合同：两个节点都没有 `AUDIO` 输入，也不会声称听过上传音频。

用户仍可在文字里描述对白、环境声、动作声、音乐和音色，或保留文字形式的 `@音频N/@Audio N` 意图；这些内容只作为文字理解。探测结论的脱敏记录位于 [`tests/fixtures/seedance20_audio_probe_2026-08-05.txt`](./tests/fixtures/seedance20_audio_probe_2026-08-05.txt)。

## MiniMax Music 3 官方 Skill 与歌词边界

Music 3 节点内置的是 MiniMax 官方 `music-caption-rewriter` 完整快照，固定于提交 `91410fb657c007ae57c60df8240f5ece5be089c7`：18 个 family index、1000 个完整模板、共 1022 个文件。来源、数量与归一化内容树哈希记录在 [`official_skills/SOURCE.json`](./official_skills/SOURCE.json)，测试会现场重算并阻止残缺发布。

节点里的“歌词模式”不是官方 Skill 选择器：生成新歌词和按要求润色属于 T8 非官方扩展，严格保留属于本地保护，AUTO/纯器乐属于工作流控制。官方 Skill 的正式能力是生成 `Global Metadata / Vocal Details / Arrangement` 三段 `music_caption`；“官方 Skill 质量模式”选择“官方完整”时，才会在三段合同之外继续执行流派路由、最多两个索引和最多三个官方模板的逐级披露。

官方 Caption 固定按以下顺序输出，默认使用英文并以约 250–450 词作为软目标：

```text
### Global Metadata
### Vocal Details
### Arrangement
```

- 歌词文本只用于 Music 3 的 `input`；Caption 只用于 `instructions`。节点不会在 Caption 中引用、改写、概括或复述歌词正文，只会传递方括号 section tags 和整体音乐意图。
- `生成新歌词` 与 `按要求润色` 是 T8 非官方扩展，不冒充官方 Skill；`严格保留歌词` 在本地逐字直通，不产生歌词 LLM 请求。
- “歌词语言”只约束 `lyrics` 输出，与官方 Caption 的描述语言完全分离。AUTO 会从音乐创意和已有歌词文字推断中/英/日/韩；生成阶段若上游仍返回错误语言，节点只追加一次歌词语言纠正请求，保持标签与结构，并且不修改 `music_caption`。生成新歌词模式会隐藏不参与请求的“已有歌词”输入框，避免把语言名称误填到歌词正文。
- 节点先把用户要求整理为带来源标记的私有 `Music Brief`，再把同一份 BPM、调式、拍号、器乐/人声状态、乐器、排除项和结构约束传给 router、参考选择器与 Caption 编译器。否定句、融合风格或官方歧义词不会被本地关键词强行路由，而是交给官方 router 规则判断。
- 方括号时间线同时保留 section tags 与安全 control tags，例如 `[Verse 2: breathy vocal]`、`[drums drop out]`；纯器乐的自定义结构也会完整进入 Music Brief。URL、工具调用、系统提示、密钥等疑似注入内容不会作为编曲指令进入官方 Caption 阶段。
- “按要求润色”可限定全部歌词、指定段落或第 N 次出现；未命中的目标会在付费前报错，目标以外段落由本地逐字合并保护。`严格保留歌词` 永远逐字直通。
- 歌词语义默认“隐私隔离”：Caption 不读取歌词正文。用户可手填宽泛语义摘要，或明确选择额外一次 LLM 分析；LLM 只返回情绪、叙事强度、能量弧线和人声密度四个枚举，不向 Caption 阶段传递歌词原句。
- 官方资源、固定核心 Skill 哈希和 18/1000 索引模板完整性会在创建供应商会话和任何付费请求之前检查；残缺或被意外修改时直接本地失败。
- “阶段缓存”是当前 Python 进程内、10 分钟、仅成功结果的短缓存，用于后段失败后续跑；缓存键只保存加盐哈希并隔离不同凭据，不落盘保存歌词。画布上的请求估算会提示预计阶段和缓存可能减少的调用数。
- `纯器乐` 输出 `[Instrumental]`，并要求 Caption 不引入歌手。歌词/Caption 目标长度、歌曲时长、BPM、结构和押韵均是软约束，上游返回非空可用内容就不会因偏差报错。
- 该节点没有 `IMAGE`、`VIDEO` 或 `AUDIO` 输入，不分析参考音乐，也不调用 Music 3 音频生成 API。它只准备文字。

## 生成类型

| 选项 | 含义 | 素材要求 |
| --- | --- | --- |
| `T2VA（文生音视频）` | 文本生成音视频提示词 | 不连接媒体 |
| `I2VA（首帧图生音视频）` | 从首帧向后发展 | 必须连接 `first_frame` |
| `FL2VA（首尾帧生音视频）` | 在首尾帧之间设计运动 | 必须连接 `first_frame` 和 `last_frame` |
| `L2VA（尾帧图生音视频）` | 从合理前态收束到尾帧 | 必须连接 `last_frame` |
| `Ref2VA（参考图/视频生音视频）` | 完整参考生成或编辑 | 至少一张参考图或一个参考视频 |

## 提示词模式

### 官方增强

根据用户意图、真实媒体和 MiniMax-H3 规则直接生成提示词。一般只需要填写主提示词，LLM 会自行补充镜头、动作、声音和节奏。

### 参考模板融合

在官方规则之外，允许提供一段参考模板。模板用于迁移镜头组织、节奏、运镜、转场、视觉风格和声音设计，不会默认照搬模板里的角色、道具、剧情、对白或固定镜头数量。

优先级为：

```text
硬性要求 > 用户主提示词与媒体事实 > MiniMax-H3 核心规则 > MiniMax 官方创意预设 > 更具体的用户手动参考模板 > T8 非官方案例 / 社区 Skill 模板
```

## H3 核心写作 Skill（始终启用）

MiniMax 官方 9 个 Skill 的组成是“1 个核心写作 Skill + 8 个场景 Skill”。核心 `h3-prompt-writing` 负责所有任务共用的 H3 字段、时间线、素材标签与声音合同，因此不是一种可选视频风格；节点界面的协议选项只控制它采用兼容输出还是严格英文输出。

| 选项 | 行为 |
| --- | --- |
| `现有兼容（保留中英文）` | 默认值；保留现有中文 / English 正文体验，同时使用新版结构、说话人、声音和 Ref2VA 素材角色规则 |
| `官方 Skill 严格（全英文协议）` | 所有说明字段和描述正文强制使用英文；仅用户原始对白、歌词、品牌/UI 文案和画面可见文字保留原语言 |

严格档位优先于“输出语言”选择。例如同时选择“中文”和“官方 Skill 严格”，实际说明正文仍为英文。这样不会静默改变旧工作流，新节点也继续默认中文兼容模式。Ref2VA 生成类任务在严格档位下默认以约 350–500 English words 作为软目标；未达到目标字数仍不是节点错误。

新版核心规则还包括：按目标视频首次真实发声顺序分配 `(S1)`，多人同声使用 `(S1,S2)`，跨切镜对白在两侧使用 `<scenetrans>`，只在片尾截断时使用 `<cutoff>`；Ref2VA 严格区分 Subject、Picture、Video 的实际角色，普通视频内声音不会被伪装成独立 Audio 素材。

## MiniMax 官方场景 Skill（8 个可选）

| 预设 | 主要强化内容 |
| --- | --- |
| `无（仅核心规则）` | 不附加场景风格规则 |
| `AUTO（根据意图判断）` | 意图明确时最多选择一个匹配预设，否则只用核心规则 |
| `极简产品广告` | 产品身份、材质、负空间、单节拍主动作、稳定闭幕和品牌事实安全 |
| `3D 动画短片` | 角色/场景连续性、可读轮廓、动作预备与跟随、单镜重要角色控制 |
| `品牌宣传短片` | 可核验品牌事实、精确文案、安全空间和具体功能证明 |
| `音乐 MV 动态字幕（官方）` | MiniMax 官方 `music-video-subtitle-generator` v0.6.6：锁定歌词、条件式口型/表演、空间文字、文本已知节拍和人物/场景/文字参考隔离；明确授权时可创作适配当前时长的短篇原创歌词，但不假装分析音频附件 |
| `双人合作游戏开场` | 双人身份与左右位置、玩家名、UI 文案、按钮层级和颜色控制 |
| `纸拼贴讲解` | 半调纸片、视觉隐喻、停格组装动作和触感音效 |
| `立体纸艺停格讲解` | 分层纸景、折叠/弹起/翻页/纸偶动作、材料与景深连续性 |
| `手绘实拍融合` | 实拍接触、同一实体连续变形、慢半拍追拍、粗糙发光笔触和非恐怖基调 |

这些选项只把官方场景 Skill 中适合“单次 H3 提示词改写”的规则传给 LLM。节点不会安装远程 Skill、生成角色卡或锚点图、研究官网、分析音频文件、调用 H3 视频生成、拼接片段或执行交付流程。

如果同时选择了一个 `非官方模板（案例 / 社区 Skill）`，则 **T8 非官方模板优先**：本次请求不会再应用或 AUTO 推断这 8 个可选官方场景 Skill。界面会把官方场景 Skill 标为“当前停用”并隐藏其详情卡；取消 T8 模板后，工作流中原先保存的官方场景 Skill 会自动恢复。该优先级不影响始终启用的 H3 核心写作 Skill，也不会改变旧工作流的节点 ID、输入或保存值。

## 非官方模板（案例 / 社区 Skill）

该列表与节点已有的 MiniMax 官方 9 个 Skill 完全分开，绝不修改或重复导入官方模板。下拉框显示中文名称，工作流内部保存稳定模板 ID；旧名称会自动迁移。MiniMax H3 会把机制写进 H3 原生字段、`[Shot N]` 时间线和声音合同；Seedance 2.0 只使用它自己的任务意图、自然段或连续 `镜头N` 语法，不会混入 H3 字段或逐镜头绝对时间码。

| 模板 | 可复用机制 |
| --- | --- |
| `产品广告｜功能证据递进` | 先给结果，再用至少三个可见证明状态逐层回答产品问题，最后收束到行动 |
| `固定机位｜从线稿生成成品` | 锁定构图，让同一对象经过至少四个不可逆制作阶段并轻微活化 |
| `形态奇观｜平面升级到现实` | 同一载体从平面、空间、体积升级到环境峰值，再回到初始锚点 |
| `人物旅程｜从困境走向目标` | 明确起点困境与目标，经过连续物理过渡并在抵达后完成目标动作 |
| `二维角色｜真人接触三级反应` | 一次跨媒介接触触发三级反应，由平面媒介自身完成结尾 |
| `一对多反转｜单一证据胜出` | 多数方案先制造冲突，克制的单一信号通过物理结果完成反转 |
| `风险揭晓｜证据交给人物反应` | 干预制造冲突，可视证据证明风险，再以有物理动机的镜头交接落到反应 |
| `未来证据｜异常闯入现实` | 同一证据载体连续更新，异常先出现在证据内，延迟后跨入稳定现实 |
| `第一视角探险｜穿越后巡检` | 清楚穿越阈值后保持空间连续，只检查一个局部线索且不虚构诊断 |
| `复古手持｜日常送别回眸` | 观察者媒介记录日常动作，外部信号改变目标，以一次回应和有动机失误收尾 |
| `反差喜剧｜越从容越失控` | 附着主体的负担触发至少两次因果连锁，主体始终沉着 |
| `人物档案｜能力逐层点亮` | 固定档案框中按身份、诊断、能力、工具和待命状态逐层激活 |
| `画中物成真｜小光点变奇观` | 被创作标记先自主活动，再越过实体边界、扩张并改变环境 |
| `工艺过程｜材料覆盖当进度` | 同一工艺物由一个只增不减的材料变量经过至少四个阶段完成 |
| `角色登场｜细节到全身揭晓` | 从可识别细节逐步扩大到面部、一次代表动作和全身身份定格 |
| `机械同行｜启动后稳定伴行` | 可见启动达到阈值后负载才移动，并由连续镜头证明稳定伴行 |
| `平面重组｜几何节奏品牌片` | 单一几何母题反复拆解重组，高密阶段后留短暂停顿并用既有图形收束 |
| `景别收紧｜从世界到眼神` | 景别从宏大环境持续收紧，证据由环境转到局部、装置和近景反应 |
| `角色卡验真｜四类证据锁定角色` | 固定角色卡反复校验姿态、操作、步态和面部四类不同证据 |
| `双系统碰撞｜同时证明两种规则` | 两套不同规则先独立成立，只汇聚一次并形成同时保留双方证据的第三状态 |
| `单目标逃生｜前后灾害交替逼近` | 单一终点持续可读，前后危险交替，完整恢复后用近失结果证明能力 |
| `对决节奏｜静止密战一击定局` | 安静建立、连续密集交换、一次决定性干预、假稳定和延迟结果 |
| `路线坍塌｜安全空间逐段消失` | 方向与终点固定，后方路线只减不增，主体完全过阈值后最后连接才失效 |
| `程序错位｜扫描到实物双确认` | 超尺度主体经历不同程序失配，扫描先揭晓，随后由同一实物完成第二次确认 |
| `技能展示｜基础动作串联升级` | 每项递增技能都从基础循环出发并返回，每个机位只承担一个证明任务 |
| `微缩介入｜外部物只进入一次` | 静态标准物先校准尺度，微缩日常稳定后由另一个外部执行物单次介入 |
| `第一视角查岗｜遮挡失效到摆烂收口` | 第一人称持续推进，每次遮挡失败都暴露更深证据，最终主动停止遮挡 |
| `雨夜追逐｜街巷近战到机车脱身` | 建立追逐方向，以一次近身阻断改变节奏，再交接到更快载具完成脱身 |
| `单人表演弧｜坐起前倾再释放` | 固定直视镜头中用姿态、手势和释放动作完成完整单人表演弧 |
| `多功能救援线｜跨裂隙送补给再撤离` | 同一绳线承担多种路线职责，接触被救者后由一人带领共同离开 |
| `微缩逃亡｜巨物追赶到资源补给` | 巨物校准微缩尺度，跨材质改变动作动词，最终取得并使用资源 |
| `气闸异境｜物理异常后空间崩坏` | 密闭空间先完成普通操作，再积累异常并开向不可能外部，由遗留物证明连续 |
| `异质航行｜维修出发到巨尺度揭示` | 出发前先证明载具与成员就绪，再交替展示局部操控和广域速度，最终用巨尺度揭示重构旅程大小 |
| `角色登场｜失误后借身体特征破局` | 先建立角色生活与移动方式，技术任务发生可恢复失误后，以身份特征作为工具完成解决 |
| `双角色职责｜独立建立后共同完成` | 两个角色先各自完成可见职责，再在共享接口形成缺一不可的共同成果 |
| `冲击后揭示｜从私密困境到城市尺度真因` | 狭小空间先建立私密困境，巨大外力制造局部后果，最后用城市广角解释真因 |
| `分层接力｜小物体穿越多区域完成传递` | 同一小物体沿相连区域改道传递，见证者持续追踪，最终由全景闭合完整接力 |
| `尺度奇观阶梯｜每镜重置参照再逼近` | 每段先重置熟悉尺度参照，再让不可能形态逐级逼近到近距离遭遇 |
| `背景异常｜先被观众发现再由记录设备证实` | 异常先在背景出现，记录设备把它隔离成证据，人物最后才产生延迟反应 |
| `非对称突破｜密集阻力到空间制度改变` | 单一非对称力量突破密集阻力，局部与广角共同证明推进，并改变空间规则 |
| `表面生长｜沿既有几何扩散并回收到手作载体` | 彩色线条沿真实几何生长并连接多个载体，最终回收到可物理关闭的纪念物 |
| `步速到抵达｜目的地延迟出现并由环境庆祝` | 旅人从步行加速到奔跑，目的地延迟揭示，并由环境在接近时触发庆祝 |
| `动作成字｜方向笔画驱动角色切换与终态标记` | 第一位角色生成方向笔画，第二位角色沿同一图形轴接力并完成终态标记 |
| `连续推进｜重复地标计时并抵达更深通道` | 受限通道持续推进，以重复地标和视差计时，仅在末段跨入更深次级通道 |
| `双人递进｜共享接触从地面升到空中峰值` | 两个主体先建立距离差，再让同一次共享接触由低位递进到唯一空中峰值，最后落地保持关系终态 |
| `数据折叠｜总量下钻到当前值` | 超大总量先建立尺度，展开分类明细作为证据，再折回聚合结果并切换到当前状态值 |
| `手势对齐｜前景动作触发后景状态` | 固定前后景先给基准状态，前景动作完成清楚对齐并只触发一次后景状态变化，最后确认结果持续 |
| `轮廓接力｜闪光换形后完成攻势闭环` | 先建立清楚动作轮廓和落地姿态，用一次闪光完成换形交接，再以效果动作、位移和落地终态证明新形态 |
| `多人攻势接力｜独立入场后同步收束` | 多名角色沿独立路线依次完成职责证明，待角色关系清楚后再同步投入并收束 |
| `微表情问候｜侧身发现到笑容回稳` | 在近乎锁定的人像镜头中，用侧身、直视、垂眼、闭眼笑容和回稳完成微表情弧线 |
| `地貌变形揭示｜局部异常到巨体逼近` | 先让局部异常仍像地貌，再逐步揭示身份、完整几何和尺度影响，最终回到低位完成逼近 |
| `表演让位于环境｜近脸到全景的连续退镜` | 表演不中断，单次连续退镜把视觉主导权从面部交给身体，再交给响应中的环境 |
| `连续跟随｜步态与弯曲地标共同计时` | 在弯曲受限通道中持续后方跟随，以稳定步态、重复地标和消失点变化证明前进深度 |
| `分组对话覆盖｜两边接力后全桌合流` | 第一组与第二组依次完成可见对话轮次，最后通过共享桌面锚点和宽构图重新合流 |
| `群演聚焦接力｜全场到主位再回合奏` | 从完整群体建立空间，隔离主位完成证明段，再重新引入共同主位并以群体同步收束 |
| `载具启程｜微观检查累积到离场证明` | 先建立载具与操作者，以多个局部检查逐项证明准备状态，再通过明确激活和远景离场完成系统兑现 |
| `巨体攻防｜共享空间中的连续闪避` | 巨体用慢重动作占据空间，小体型主体连续穿过负空间，始终保持双方地理关系与未决对峙 |
| `表情校准｜固定身份下的动作单元序列` | 锁定身份、光线和视角，让局部面部动作单元分段变化并复位，最后收紧景别校验稳定性 |
| `踏面异变｜重复触点到基底破裂` | 重复触点先建立局部表面反应规则，一次更强接触使基底破裂并进入新的下层介质状态 |
| `移动兑现｜载具跃迁到生活结果` | 把载具身份、出发、性能跃迁和地理抵达串成因果链，最终用具体生活结果兑现技术奇观 |
| `类型预告｜同一主角跨场景升级到片名` | 同一主角和少数关系锚点贯穿多场景升级，从私人压力走向公共危险与大尺度奇观，片名卡封口 |
| `静态伏击｜从被动锚点升级到异能出口` | 长停留先固定主角与地点，威胁逐次压缩空间，最后只用一次超常出口改变冲突状态 |
| `环境前沿｜局部点燃到全域占据` | 同一地理中的可追踪前沿从局部起点连续扩张、跨越地标，最终由广角证明全场改变 |
| `尺度球局｜共享球体串联反差挑战` | 一个持续可见球体串联尺度反差对手、固定目标与动作阶段，以双方可见反应结束而不臆测得分 |
| `连续变线｜逐层防守到垂直终结` | 固定球场、球与篮筐关系，连续穿过多层可见防守门并逐次改变路线，最后只用一次垂直篮筐动作收束 |
| `技艺递进｜原料变形到成品特写` | 从单一原料开始，以功能不同且难度递增的手部操作改变形态，经一次不可逆热处理后用成品微距证明结果 |
| `材质引路｜空间生长到版式定格` | 同一连续材质从微小锚点引导运镜、生成实体并扩展成环境，最后一次升高压成保留历史关系的平面版式 |
| `世界悬停｜持续靠近到末端复流` | 复杂环境整体冻结而观察者连续穿行，以多个冻结地标持续证明悬停，片尾只恢复一次全局运动 |
| `动态承载｜平衡升级到失败落点` | 先建立稳定穿越能力，再进入动态承载面并持续证明平衡，最后用一次转移失败、落点与本人反应收束 |
| `屏中蒙太奇｜外层连续内屏切换` | 实体显示设备与外部现场保持同一连续镜头，内屏累积至少三种状态，结尾让内屏结果、设备载体和外部语境同时可读 |
| `逐物改写｜局部对象到整片环境` | 从一个局部对象开始逐项传播可见变化，保持改写规则连续，最终把局部机制扩展为整片环境的新状态 |
| `尺度展开｜微小材质扩张后原样回收` | 从微小材质锚点连续扩张到大尺度空间结果，再沿同一材质关系精确回收至原始尺度与状态 |
| `图形复位｜身份卡与动作证明交替` | 先完成紧凑身份激活，让固定图形身份卡与短促动作证明交替出现，后段提高动作难度并把峰值动作轮廓收回完整主体锁定图 |
| `计划对照｜固定分镜条见证执行升级` | 让持续可读的计划板与独立执行区同框，以按计划累积的现场变化证明执行推进，并让终态与计划末项闭合 |
| `日程闭环｜重复锚点串联整日任务` | 用稳定身份与随身物锚点串联准备、通勤、目的地任务和返回休息，在高密度切换中保持整日因果顺序 |
| `镜头交接｜观察者跟随转主体自拍` | 外部观察镜头先完成跟随、地点交互和环境证明，再经有动机的连续桥只交接一次拍摄权给主体 |
| `感官封闭｜人群静止点到异地恢复` | 用稳定主体与独立流动环境建立压力，在一次完整感官封闭后只发生一次全画幅换境，并以同身份恢复动作证明新空间持续 |
| `双支座弹性偶｜控制器驱动形变复位` | 两个可见支座分别绑定图形角色，依次验证共享响应、独立响应和第三种关系测试，最后稳定复位为可辨双角色 |
| `光学搜索｜远景线索递进到细节确认` | 在同一受限光学界面内从远景地点线索逐层收紧到中景主体、近景身份与极近景局部证据 |
| `画内涂鸦｜现实互动逐步绘出隐藏世界` | 让现实互动逐次生成锚定在表面的同族线稿，从局部符号、路线与新图形升级到环境范围的连通绘制世界 |
| `造型轮播｜身份锁定跨风格世界` | 固定主体身份与镜头关系，让背景、材质、配色和配件成套切换并逐步增密，最后回到可读身份终态 |

375 条来源案例中有 213 个案例 selector 和 162 个 evidence variant，当前没有 pending case；证据变体只增加同一机制的 GIF 与证据，不重复增加下拉。`batch-2026-08-17-01` 新增 `身份机体跃迁`、`独演成敌`、`样本倍增` 3 个稳定 selector，并为 `固定机位｜从线稿生成成品` 增加 2 个 evidence variant、为 `造型轮播｜身份锁定跨风格世界` 增加 1 个 evidence variant；`batch-2026-08-17-02` 新增 `规则闯关｜吸收能力后从平面赛道升维`；`batch-2026-08-20-01` 新增 `单次决策兑现｜准备—执行—后果—回归`、`延迟载体释放｜进入—静置—开启—扩散`、`画外定位悬念｜反应递进但不揭示来源`；`batch-2026-08-21-01` 新增 `关系重排｜群体建立—双人收紧—前后站位`、`见证释放｜封闭近景—外部尺度—双视图证明`、`信息接力｜稳定载体穿越多种实体媒介`；`batch-2026-08-22-01` 新增 `价值阶梯｜原料—转化—装配—使用回报`、`能力见证｜装备特写—连贯表演—人群反应—挑战交接`、`公共兑现｜席间期待—揭晓—群体释放—登台锁定`；`errata-2026-08-24-01` 以一份累计快照补齐 8 月 23 日已批准成果：新增 66 个稳定 selector，并为 8 个既有 selector 补充 10 个 evidence variant；`errata-2026-08-24-02` 新增作者明确授权分发的 `指尖控制｜四向同拍全身响应` selector；`batch-2026-08-25-01` 新增 `时尚密度复位｜身份锁定、拼贴回顾与英雄主标`；`batch-2026-08-25-02` 新增 `手势边界换媒｜局部窗口、多形态验真与回归`；`batch-2026-08-25-03` 为该模板补充 1 个同机制 evidence variant，不新增 selector；`batch-2026-08-25-04` 新增 14 个稳定 selector，并把 6 个同机制证据变体归并到既有/同批模板，不创建重复下拉；`batch-2026-08-26-01` 新增 10 个稳定 selector，并把 10 个同机制证据变体归并到既有/同批模板；`batch-2026-08-26-02` 新增 1 个稳定 selector，不新增 evidence variant；`batch-2026-08-27-01` 为 9 个既有模板补充 15 个同机制 evidence variant，不增加重复下拉；`batch-2026-08-28-01` 再为 16 个既有模板补充 20 个 evidence variant；`batch-2026-08-28-02` 又为 19 个既有模板补充 20 个 evidence variant；`batch-2026-08-29-01` 再为 19 个既有模板补充 20 个 evidence variant；`batch-2026-08-30-01` 累计快照再补齐 40 个同机制 evidence variant，其中 20 个为本批明确增量，均不增加重复下拉。旧工作流中的 `声画错位递进` / `t8-case-audio-cause-lead-ladder-v1` 会迁移到证据支持的 `景别收紧｜从世界到眼神`。

另外两个独立的用户贡献社区 Skill 不合并进案例 registry，也不冒充官方 Skill：

| 社区 Skill | 可复用机制 |
| --- | --- |
| `自然街拍互动｜边走边聊到清楚落点` | 连续路线跟拍中用距离、步态、视线、手势、视差与现场声推进到可读互动结果 |
| `突遇惊吓到和解｜贴近反转与求和手势` | 平静基线、一次非致命惊慌、距离反转和被看见的求和手势组成关系反转 |

打开 `MiniMax 官方场景 Skill（8 个可选）` 或 `非官方模板（案例 / 社区 Skill）` 下拉时，鼠标悬停任一具体选项会在菜单右侧即时显示对应 GIF、用途和简约推荐输入；菜单靠近窗口右边时预览会自动移到左侧。键盘上下选择和搜索过滤也会同步预览。选择任一具体官方场景 Skill 或非官方模板后，节点内都会显示用途、适用/推荐输入格式、必须实现的结构锚点、推荐示例、GIF 和来源链接。`填入推荐示例` 只有在主提示词为空时才写入；已有输入会显示“已有输入，未覆盖”。推荐示例只是可编辑的实例意图，不是最终提示词。即使只输入“美丽的女人”，节点也会保留这个主体，并要求 LLM 原创建立模板需要的场景、触发、事件链和可见结果，不能退化成普通人像运镜。

GIF 只供浏览器中的人类界面预览，绝不会连接到首帧、尾帧、参考图片、参考视频，也不会发送给 LLM。8 个官方预设 GIF 和 377 个 T8 案例/社区 Skill 轻量 GIF 均随 GitHub 完整仓库直接分发；Registry/Manager 安装则默认在用户实际查看某个案例时，从独立的 [`comfyui-minimax-h3-prompt-enhancer-T8-assets`](https://github.com/T8mars/comfyui-minimax-h3-prompt-enhancer-T8-assets) Release 下载对应分片。节点会校验安装目录对应的案例全集、来源 SHA-256、分片 SHA-256、每个 GIF 的大小/哈希/文件头和安全解包路径；不兼容或损坏的资源不会显示，也不会影响提示词增强。

H3 与 Seedance 2.0 节点都提供非序列化按钮 `管理 / 更新 T8 动态预览`：可选择“智能按需（推荐）”“自动补齐全部”或“仅手动下载”，并可检查更新、下载缺失、校验修复或清空缓存。这些设置保存在 ComfyUI 用户目录，不写入工作流，所以旧工作流结构、节点输入输出和 API Key 均不会改变。离线时已缓存/内置 GIF 继续显示；未缓存 GIF 只显示提示，提示词生成仍正常运行。

维护者仍可选用本地原始案例清单，以显示来源链接或在开发环境优先检查原始预览；普通用户不需要此配置：

```powershell
Copy-Item .t8-case-library.example.json .t8-case-library.local.json
```

`.t8-case-library.local.json` 已加入 `.gitignore`。也可以分别用环境变量 `T8_UNOFFICIAL_CASE_LIBRARY_V2`、`T8_STANDALONE_COMMUNITY_SKILLS_V1` 指定两个 manifest；若社区 manifest 与案例 manifest 位于同一目录，后端会自动发现它。本地清单缺失、路径失效或校验失败时，节点会自动回退到仓库内置 GIF。

默认 `无（不使用 T8 案例）`，因此旧工作流请求保持不变。案例独立于“官方增强 / 官方优化”和“参考模板融合”，用户提示词、媒体事实、硬性要求、时长与固定镜头数始终优先。节点把所有结构锚点作为一次请求内的硬写作合同传入上游，并要求静默检查；按此前的上游兼容策略，非空响应仍直接放行，不会因本地语义猜测误杀有效输出。

### 维护者：标准化每日导入

日常批次先由 curator 生成并独立复审 `unofficial-case-library-v2.json`，再用 [`tools/import_unofficial_case_library_v2.py`](./tools/import_unofficial_case_library_v2.py) 同步人类名称、推荐输入、结构锚点、证据变体和双模型 Creative DNA：

```powershell
python tools/import_unofficial_case_library_v2.py `
  --library <handoff-dir>\unofficial-case-library-v2.json `
  --community-skills <handoff-dir>\standalone-community-skills-v1.json `
  --existing-catalog case_templates\catalog.json `
  --source-batch-dir case_templates\source_batches `
  --output case_templates/catalog.json
```

每次案例目录发生变化，都必须同步生成并提交完整的 GitHub 内置预览包，不能只提交 selector 元数据；同时必须用资产仓库工具生成新的、不可变的 Release 分片和匹配的 `channel.json`，再把该通道快照带入节点版本。Registry 只分发通道清单，不分发 T8 GIF。原生成器要求输出目录不存在或为空；建议先生成到待审目录，核对后再整体替换正式目录：

```powershell
python tools/bundle_t8_case_previews.py `
  --library <handoff-dir>\unofficial-case-library-v2.json `
  --community-skills <handoff-dir>\standalone-community-skills-v1.json `
  --catalog case_templates\catalog.json `
  --output-dir web\js\assets\t8-case-previews-next `
  --ffmpeg <ffmpeg-dir>\bin\ffmpeg.exe
```

导入器按每次累计库声明的库存做严格闭合校验；本次为 375 条案例记录、213 个 selector、162 个 evidence variant、0 个 pending case，并另验 2 个独立社区 Skill，最终生成 215 个非官方下拉项。已发布案例必须 `released/approved`；H3 与 Seedance 2.0 适配器必须同为可执行的无媒体 recipe，或同为已验证的 disconnected direct-final 交接，两种格式都必须通过哈希、`media_connections=[]` 与 secret 边界检查。可执行 recipe 的 provider/secret 字段必须为空、不得含旧 `openai_upload_url`，双模型 Creative DNA 必须一致；direct-final 的成品提示词只用于验证，节点目录仅从已校验的 `creative-dna.json` 提取可复用机制、结构锚点、可替换槽位和失败修复，不导入成品提示词。若以后再次出现 pending case，必须保持未发布、未复审、有明确 blocker、无 adapter，并且不能进入下拉或预览分发。社区 Skill 必须保持非官方/用户贡献、不得合并进案例 registry，并现场重算 Skill、摘要、双模型 guidance 与 GIF 哈希。提示词目录不会写入本地路径、来源 URL、来源视频或成品提示词；分发包只保存作者授权的轻量 GIF、不可逆哈希与编码参数。Markdown 报告只是说明，不能代替机器 JSON、实时 recipe、内置预览覆盖率与哈希核验。

### 音乐 MV 动态字幕（官方）填写方式

选择 `音乐 MV 动态字幕（官方）` 后，主提示词会显示一份动态填写提示；它只是界面占位文字，不会写入工作流或自动成为提示词。旧工作流中保存的 `MV / 歌词贴字` 会自动迁移到这个正式名称。可以直接按下面的结构填写，未涉及的项目留空：

```text
MV类型/音乐类型/视觉风格：暗色抒情 MV，低饱和蓝黑色，空间歌词排版
歌词原文（逐字锁定，可空）：夜色落在我肩上，别回头。
无歌词时：器乐 / 允许生成原创歌词
演唱者或离屏人声：画内女歌手演唱
已知 BPM、歌词时间点或节拍事件（可空，节点不分析音频）：00:04.200 鼓点进入，00:09.000 drop
目标平台/画幅（可空）：抖音竖屏，9:16
字体包装与禁止项：文字在中景展开，不遮挡眼睛和关键口型
```

MV 规则按以下方式工作：

- 用户提供的歌词逐字锁定，保持原语言、标点、顺序和重复，不翻译、不润色、不补写；只有未提供歌词且明确写出“允许生成原创歌词”时，才会创作一段能放进当前目标时长的原创歌词，并将同一文本用于演唱与可见文字。否则不会自动创建歌词、歌手或口型。
- 只有提示词或可见参考素材明确存在画内演唱者时，才补充嘴唇、下颌、呼吸、表情和手势；器乐、纯 Typography 与离屏人声 MV 不强制出现歌手。
- 歌词文字作为前景、中景或背景的空间图形层，同一时刻保持一个主阅读焦点；可轻微穿插遮挡，但不会遮挡眼睛、主要表情和关键口型。
- 只有文本明确给出 BPM、时间码、drop、snare、808、歌词重音或音乐段落时，才进行精确卡点。节点没有 AUDIO 输入，也不会声称听过歌曲或参考视频声音。
- Trap / Dark-pop / Cyber-grunge 才会条件化使用硬切、glitch、扫描错位、颗粒和 zine 拼贴；抒情、氛围或原声 MV 不会被统一套用硬切风格。
- `strict / balanced / creative` 控制扩写幅度；`官方 Skill 协议`控制正文语言和格式。即使选择全英文严格协议，用户原始歌词仍保留原语言。

多张参考图建议在高级选项的 `reference_context` 中做角色隔离：

```text
<Picture 1>=人物外观；
<Picture 2>=场景与灯光；
<Picture 3>=字体包装，只参考字体、版式和动效，不参考人物与场景。
```

字体参考图中的示例文字、人物和场景不会自动复制。参考视频只提供可见表演、运镜、剪辑节奏和画面结构，不会被当作独立音频、BPM 或歌词时间轴。

使用“参考模板融合”时，模板只贡献镜头组织、节奏、运镜、转场和视觉语法；模板中的人物、歌词、BPM、标题、剧情和镜头数不能覆盖基础提示词、真实媒体、硬性要求或固定镜头数量。


## 改写模式

| 模式 | 温度 | 行为 |
| --- | ---: | --- |
| `strict` | `0.2` | 尽量保持用户原意和媒体事实，只补必要格式与连续性 |
| `balanced` | `0.7` | 在保真基础上补充合理镜头、灯光、动作、环境声和节奏 |
| `creative` | `1.2` | 加强视觉风格、镜头设计、动作连接、声音层次和配乐 |

温度映射是本节点的产品设置，不代表供应商官方推荐值。

## 主要输入

| 输入 | 说明 |
| --- | --- |
| `prompt` | 用户基础视频意图，不能为空 |
| `task_type` | T2VA / I2VA / FL2VA / L2VA / Ref2VA |
| `duration_seconds` | 目标时长，任意正整数秒数，节点不设上限；下游模型限制仍然有效 |
| `shot_count` | `AUTO` 由模型按内容、素材、时长和节奏判断；也可固定为 1–20 个镜头 |
| `rewrite_mode` | `strict / balanced / creative` |
| `description_word_target` | `0` 为自动；非零为 80–1000，中文按约数汉字、英文按单词理解 |
| `output_language` | `中文 / English`，默认中文 |
| `prompt_mode` | `官方增强 / 参考模板融合` |
| `official_skill_profile` | 界面显示为“H3 核心写作 Skill（始终启用）”；`现有兼容 / 官方 Skill 严格`，默认兼容，严格档位强制英文说明正文 |
| `creative_preset` | 界面显示为“MiniMax 官方场景 Skill（8 个可选）”；`无 / AUTO / 8 个官方场景写作预设`，选择具体项后显示详情卡和官方 GIF；与 T8 非官方模板同时选择时暂不生效 |
| `case_template` | `无 / 215 个非官方模板`：213 个 T8 案例 selector + 2 个独立社区 Skill；显示中文名称，工作流保存稳定 ID，H3 与 Seedance 2.0 使用独立原生适配规则；H3 中与官方场景 Skill 同选时优先生效 |
| `reference_template` | 仅参考模板融合使用 |
| `first_frame` | I2VA / FL2VA 首帧 |
| `last_frame` | FL2VA / L2VA 尾帧 |
| `reference_images` | Ref2VA 参考图，Autogrow，最多 9 张 |
| `reference_videos` | Ref2VA 参考视频，Autogrow，最多 3 个 |
| `reference_context` | 高级可选；补充画面无法判断的身份或关系 |
| `constraints` | 高级可选；必须保留或禁止改变的内容 |
| `seed` | 随机种子，配合运行后状态控制缓存和变体 |

`reference_context` 和 `constraints` 默认折叠。正常使用不需要填写，避免把简单任务变成大量表单输入。

## 镜头数量

- `AUTO（系统自动判断）`：结合基础提示词、参考素材、目标时长、动作密度和节奏决定镜头数；没有必要切镜时优先使用单镜头内运镜。
- `1–20`：要求 LLM 在时间线中使用恰好对应数量的 `[Shot N]`，连续编号，并让后续镜头的时间码严格递增且小于目标时长。
- 固定数量优先于基础提示词或参考模板中的模糊镜头数量范围。选择 `AUTO` 时，基础提示词中的镜头要求仍会参与模型判断。

镜头数量是传给上游模型的明确生成约束，不是本地响应验收条件；只要上游返回非空内容，节点仍按“输出与错误行为”中的规则放行。

## 随机种子

种子使用 ComfyUI 原生运行后控制：

- `randomize`：每次运行前随机更换种子。
- `fixed`：保持当前种子，输入相同时允许使用 ComfyUI 缓存。
- `increment`：每次运行递增。
- `decrement`：每次运行递减。

Seedance 没有为本节点调用的 Chat Completions 公开确定性 `seed` 请求参数，因此节点不会发送未声明的 API 字段。种子会作为提示词变体标识并参与 ComfyUI 缓存，但不保证强制重跑后逐字复现。

## API Key 与接口模式

三个节点中的 Key 都用于当前所选云端 LLM 渠道的提示词增强请求，不是下游 Seedance 2.0 视频生成或 Music 3 音频生成 API Key；本地 Qwen 渠道完全不需要 Key。

### 贞贞平价小屋（推荐）

聊天与素材上传地址固定为：

```text
https://api.seedance.nz
```

可以把任意 `STRING` 输出连接到节点的 API Key 接口，也可以在节点底部填写 Key，或点击[获取贞贞 API Key](https://api.seedance.nz/sign-up?aff=5f4w)。接线值优先；没有接线且节点中的 Key 留空时读取环境变量 `SEEDANCE_API_KEY`。

PowerShell：

```powershell
$env:SEEDANCE_API_KEY="你的 API Key"
```

Linux / macOS：

```bash
export SEEDANCE_API_KEY="你的 API Key"
```

### 贞贞的 AI 工坊（图片/视频）

聊天地址固定为：

```text
https://ai.t8star.org/v1/chat/completions
```

默认模型是 `gemini-3.5-flash`。选择 `Custom（自定义）` 后会显示“自定义模型 ID”，可填写 AI 工坊模型列表中的完整 ID。H3/Seedance 自定义模型必须自行确认具备图片与视频理解能力；Music 3 节点是纯文本请求，只要求所选模型支持 Chat Completions 文本输入。

可以点击节点底部的[获取 AI 工坊 API Key](https://ai.t8star.org/register?aff=dP7j)。节点中的 Key 留空时读取环境变量 `T8STAR_API_KEY`：

```powershell
$env:T8STAR_API_KEY="你的 API Key"
```

AI 工坊模式不需要上传 URL。图片和完整视频以 Base64 Data URL 放进同一次 Chat Completions 请求。2026-08-06 的真实协议探测确认：该网关对 `gemini-3.5-flash` 的视频 Data URL 必须使用 OpenAI 多模态 `image_url` 部件（Data URL 自身仍是 `video/mp4`）；`video_url` 虽会返回 200，但会丢失或误读视频事实。因此本节点使用实测通过的表示法，而不是照搬旧参考节点。

### OpenAI 兼容接口（备用）

备用模式只需一个 API Base URL 和模型 ID。Base URL 支持服务根地址、以 `/vN` 版本段结尾的地址（例如 `/v1` 或火山方舟的 `/api/v3`），或完整 `/chat/completions` 地址。节点 Key 留空时读取 `OPENAI_API_KEY`，Base URL 留空时读取 `OPENAI_BASE_URL`；H3/Seedance 需要供应商实际支持的视觉模型，Music 3 只需要文本模型。

三个核心节点会自动把 `OpenAI Base URL` 和 `OpenAI 模型 ID` 保存到当前工作流：输入时即时同步，点击节点运行按钮时还会在提交前再次读取尚未失焦的输入框；重新打开工作流或切换 API 模式后会自动恢复，无需每次重填。该兼容状态不包含 API Key，Key 仍按下方安全规则单独处理。旧工作流无需重连，首次保存后会补充这份兼容状态。

#### 修复后的节点配置

MiniMax H3 与 Seedance 2.0 两个节点使用相同的 OpenAI 兼容配置：

| 节点字段 | 是否必填 | 用法 |
| --- | --- | --- |
| `API Key` | 是 | 可连接任意 `STRING`，也可在节点内填写；节点留空时读取 `OPENAI_API_KEY` |
| `OpenAI 模型 ID` | 是 | 填写兼容服务商提供的完整视觉模型 ID，不再固定为 `bytedance/doubao-seed-evolving` |
| `OpenAI Base URL` | 是 | 只填写一个聊天接口地址；服务根地址补全为 `/v1/chat/completions`，已有 `/vN` 版本段则直接追加 `/chat/completions` |
| `视频素材 URL` | 否 | 仅用于视频，每行一个，按已连接 `VIDEO` 的顺序对应；未填写的已连接视频自动使用 Base64 |

不再需要、也不要填写单独的“兼容素材上传 URL”。图片没有素材 URL 字段，始终由节点编码成 Base64 并随聊天请求直接发送。

该模式不再使用第二个素材上传端点：

- 图片统一编码为 PNG，通过 `image_url.url` 中的 `data:image/png;base64,...` 内联到同一次 Chat Completions 请求。
- 视频默认通过 `video_url.url` 中的 `data:video/...;base64,...` 内联完整视频字节。
- “视频素材 URL”可选，每行一个，按已连接 VIDEO 的顺序替代对应视频的 Base64；未覆盖的视频继续使用 Base64。
- 视频 URL 数量不能超过已连接 VIDEO 数量，且必须是 HTTP(S) 地址。

OpenAI 官方 Chat Completions 明确定义了 Base64 图片输入，但通用 `video_url` 并不是所有兼容供应商都支持的统一能力。这里的视频格式面向声明支持视频理解的兼容网关；用户填写的模型和网关必须同时支持视频内容部件，节点不会降级到纯文字或抽帧请求。

### 本地 GGUF（llama.cpp / Qwen，离线推理）

本地渠道是三个现有节点的第 4 个互斥 provider，不会新增或替换节点，也不会改变 H3、Seedance 2.0、Music 3 各自的提示词合同。运行时不需要 API Key、Base URL 或云端模型 ID。节点不再把可用范围锁死为两个文件名：会递归扫描 `ComfyUI/models/LLM`，读取轻量 GGUF 元数据，区分主模型与 mmproj，并为视觉模型推荐同名/同目录投影器。

GitHub 完整安装采用自动回退顺序：本节点固定安装器生成的 `llama-server` → 系统 `PATH` 中的 `llama-server` → 当前 ComfyUI Python 环境已经安装的 `llama-cpp-python`。Manager/Registry 安装为通过 Registry 自动安全审查，仅使用进程内 `llama-cpp-python`，不随包分发外部进程启动器。两种安装都会递归扫描同一个 `models/LLM`，状态窗口会显示实际命中的后端、来源和版本。

如果当前 ComfyUI Python 没有可用的 `llama-cpp-python`，三个核心节点都提供“获取 llama-cpp-python 预编译 Wheel”按钮，跳转到 [JamePeng 预编译 Releases](https://github.com/JamePeng/llama-cpp-python/releases)。必须选择与 **ComfyUI 实际 Python 版本、操作系统和 CUDA 版本**匹配的 Wheel，并用 ComfyUI 自己的 Python 安装，而不是系统 Python：

```powershell
& "你的 ComfyUI Python 路径\python.exe" -m pip install "下载到本地的 llama_cpp_python-....whl"
```

这是可选的第三方预编译来源，本节点不会静默下载或自动安装 Wheel。安装后请完整重启 ComfyUI，再点击“检查本地 Qwen 安装 / 扫描 GGUF”确认实际运行时；如果 Wheel 与 Python/CUDA 不匹配，状态窗口会明确显示导入或原生库加载错误。GitHub 完整安装还可以直接运行本仓库的 `install_local_qwen.py --runtime` 安装固定 `llama-server`，无需 Python Wheel；Manager 包不包含该下载/启动脚本。

模型和运行时体积很大，不会随 Git 仓库分发，也不会在执行节点时静默下载。请在节点目录显式运行：

```powershell
& "你的 ComfyUI Python 路径\python.exe" install_local_qwen.py
```

只看安装计划：

```powershell
& "你的 ComfyUI Python 路径\python.exe" install_local_qwen.py --dry-run
```

只安装或核验其中一部分：

```powershell
& "你的 ComfyUI Python 路径\python.exe" install_local_qwen.py --runtime
& "你的 ComfyUI Python 路径\python.exe" install_local_qwen.py --model --model-variant official
& "你的 ComfyUI Python 路径\python.exe" install_local_qwen.py --model --model-variant uncensored
& "你的 ComfyUI Python 路径\python.exe" install_local_qwen.py --model --model-variant heretic-9b
& "你的 ComfyUI Python 路径\python.exe" install_local_qwen.py --model --model-variant all
& "你的 ComfyUI Python 路径\python.exe" install_local_qwen.py --offline
```

`official` 是默认模型；`uncensored` 是用户可选的第三方 27B FP8 衍生 Q4_K_M 量化；`heretic-9b` 是体积更小的第三方 9B i1-Q6_K 量化；`all` 安装三种文字模型及默认 27B 视觉投影器。9B 上游仓库没有发布匹配的 mmproj，因此固定安装器只安装其文字模型；纯文字 H3/Seedance、Music 3 可直接使用，图片/视频必须由用户另行提供兼容的 9B mmproj，交给 AUTO 匹配或手动选择。安装后重启 ComfyUI，或点击节点的“检查本地 Qwen 安装 / 扫描 GGUF”，下拉会重新列出 `models/LLM` 及任意子目录内的 GGUF。第三方模型不会替换现有 27B 默认值，也不会破坏旧工作流或绕过本项目的提示词合同、输入验证与输出保护。

安装器固定并核验以下资产，支持 `.part` 断点续传、磁盘空间预检和原子改名：

| 资产 | 固定版本 | 体积 |
| --- | --- | --- |
| 默认 Qwen 模型 | `Qwen3.8-27B-Q4_K_M.gguf`，固定 HF revision 与 SHA-256 | 约 15.93 GiB |
| 可选第三方模型 | `qwen3.8-27b-uncensored-fp8-q4_k_m.gguf`，固定 `theresa00l/...` revision 与 SHA-256 | 约 15.66 GiB |
| 可选轻量第三方模型 | `Qwen3.8-9B-heretic-uncensored.i1-Q6_K.gguf`，固定 `mradermacher/...` revision 与 SHA-256 | 约 6.85 GiB |
| 视觉投影器 | `mmproj-F16.gguf`，固定 SHA-256 | 约 0.86 GiB |
| 推理运行时 | llama.cpp `b10436`，固定安装器提交与 SHA-256 | 依平台/后端而定 |

GGUF 与 mmproj 统一放入 ComfyUI 的 `models/LLM/` 或任意子目录；历史目录 `models/LLM/Qwen3.8/` 和只保存文件名的旧工作流继续兼容。固定安装器的 llama.cpp 仍放在本节点已忽略的 `runtime/local_qwen/`，但也会复用当前 ComfyUI 已安装的 `llama-cpp-python`。默认模型来自 `unsloth/Qwen3.8-27B-GGUF`；27B 可选模型来自 `theresa00l/Qwen3.8-27B-Uncensored-FP8-Q4_K_M-GGUF`；轻量 9B 可选模型来自 `mradermacher/Qwen3.8-9B-heretic-uncensored-i1-GGUF`。9B 量化仓库标注其来源为 `rohit267/Qwen3.8-9B-heretic-uncensored`、语言为英语，但没有声明许可证；本项目只提供固定下载入口，不分发或重新授权模型文件。参考安装器、参考插件和 llama.cpp 为 MIT。具体固定提交、哈希及归属见 [`THIRD_PARTY_NOTICES.md`](./THIRD_PARTY_NOTICES.md)。

任意被扫描到的文字 GGUF 都可交给当前 llama.cpp 运行时加载；“被发现”不等于“本项目已验收”。H3/Seedance 有图片或视频输入时必须有匹配 mmproj；AUTO 优先按 `general.name`、架构、同目录和文件名相似度匹配。当前 `llama-cpp-python` 回退路径会自动选择 Qwen2.5-VL、Qwen3-VL、Qwen3.5、Gemma 3/4 或 MTMD 处理器（取决于已安装版本实际提供的类）；不具备对应处理器的视觉架构会明确报兼容性错误，文字模式不受影响。

可选模型已用本项目固定的 `mmproj-F16.gguf` 和 llama.cpp 本地运行时完成真实兼容验收：文字精确 token、图片 OCR/颜色/形状、视频采样帧的双阶段 OCR、早晚运动方向与时间顺序共 12/12 项通过。它支持节点现有的“图片 + 按时间戳采样视频画面”路径；这仍不等于读取完整视频字节或分析音轨。脱敏证据见 [`tests/fixtures/local_qwen_uncensored_compatibility_2026-08-20.json`](./tests/fixtures/local_qwen_uncensored_compatibility_2026-08-20.json)。

轻量 9B Q6_K 模型也完成了真实 llama.cpp 兼容验收：文字精确 token、图片 OCR/颜色/形状、视频早晚代码、运动方向、时间顺序、单图单视频计数和“不分析音轨”共 12/12 项通过，耗时 22.078 秒。视觉测试使用用户另行放置的 `mmproj-Qwen3.5-9B-Uncensored-HauhauCS-Aggressive-BF16.gguf`；该投影器不由本安装器下载或分发。脱敏证据见 [`tests/fixtures/local_qwen_heretic_9b_compatibility_2026-08-25.json`](./tests/fixtures/local_qwen_heretic_9b_compatibility_2026-08-25.json)。

2026-08-21 又对可选第三方模型执行了完整发布质量验收，确定性总分 `100/100`、`passed=true`，5 个用例全部通过：同 seed 三次逐字一致、H3 T2VA、Music 3 中文歌词与官方完整 Skill、H3 图像+视频证据、Seedance 2.0 图像+视频证据。视频用例同时核验早晚阶段代码、运动方向、硬切和首次出现顺序；全套耗时 476.938 秒，峰值显存 15971 MiB，卸载后回到 2007 MiB（基线 1613 MiB）。脱敏报告见 [`tests/fixtures/local_qwen_uncensored_quality_2026-08-21.json`](./tests/fixtures/local_qwen_uncensored_quality_2026-08-21.json)，仅保存分数、布尔检查、哈希、字符数和资源采样，不保存提示词、歌词、媒体、API Key 或临时令牌。

建议 24GB 以上显存获得较好的交互体验；16GB 显存会由独立 `llama-server` 的 `--fit` 自动部分卸载到系统内存，建议至少 32GB RAM，速度会明显下降。CPU-only 功能上可运行，但本项目不承诺交互速度。首次使用前可点击三个节点中的“检查本地 Qwen 安装 / 扫描 GGUF”查看模型数量、mmproj 配对、运行时后端和实际模型目录；旁边的路径按钮可直接复制 `ComfyUI/models/LLM` 绝对路径。

本地选项说明：

- H3/Seedance 的图片编码为 Base64 JPEG；原生 `VIDEO` 按真实时间戳采样，默认 2 fps，每 6–9 帧组成一个有时间标签的联系表，并按上下文预算最多发送 16 个视觉部件。
- 本地视频只分析可见画面顺序，不读取、转写或声称理解原声音轨。云端完整视频行为不变。
- Music 3 只发送文字，整个多阶段任务复用同一模型进程，并且绝不加载 `mmproj`。
- 三个节点共享互斥运行锁，避免同时抢占显存；独立 `llama-server` 等待与请求期间支持 ComfyUI 取消。`llama-cpp-python` 是兼容回退路径，其底层同步推理的中途取消能力取决于已安装绑定版本。
- 默认关闭思考以降低延迟；可在高级选项开启思考、选择推理强度、上下文、最大输出、视频采样率、显存释放及执行后卸载/驻留/10 分钟 TTL。
- 运行时只监听 `127.0.0.1` 随机端口，使用随机临时令牌并关闭 Web UI；成功、异常、取消和 ComfyUI 退出都会执行相应清理。
- 本地模型会在完整官方 Skill 与案例之后收到最终语言锁，确保“输出语言”对 H3、Seedance 2.0 和 Music 3 Structured Caption 的说明正文生效。若返回内容明显整体跑到另一种语言，节点只在同一次本地模型驻留期间追加一次低温语言纠正；已经符合语言要求时不增加调用。协议字段、时间码、参考标签以及用户原始对白、歌词、品牌/UI 文案和画面文字保持原样。H3 的“官方 Skill 严格（全英文协议）”仍按设计优先于中文选项。
- 本地输出继续遵守既有 content-first 规则：H3 仅在完整命中字段时重排，Seedance 非空放行，Music 3 保留歌词保护和官方 Caption 阶段合同。

## API Key 安全

三个节点都提供标准 `STRING` API Key 接口，并保留底部的遮罩、显示、保存和清空按钮。外部接线值优先。遮罩只能避免画布上直接显示明文：点击“保存到工作流”后，Key 会进入工作流 JSON。

- 分享工作流前务必点击“清空”。
- 更安全的方式是把节点 Key 留空并使用环境变量。
- 节点不会把 Key、请求正文、素材 URL 或响应正文写入日志。
- 仓库示例和测试不包含真实 API Key。

执行期间，三个节点会向 ComfyUI 进度条报告本地准备、模型请求和结果整理阶段。最近 50 次执行的脱敏阶段信息可从本机 ComfyUI 的 `/t8-prompt-enhancer/diagnostics` 查看；记录仅含节点类别、渠道名称、结果、阶段耗时、可用时的尝试次数、素材数量、缓存命中与错误类别，进程重启后自动消失。该接口不会返回 API Key、供应商 URL、请求/响应正文、提示词、歌词、模板、媒体或模型推理。

## 图片与视频处理

- 云端图片编码为 PNG；平价小屋模式上传，AI 工坊与 OpenAI 兼容模式内联为 Base64 Data URL。本地 Qwen 图片编码为限边 JPEG Data URL。
- 云端视频使用 ComfyUI 原生 `VIDEO` 的完整流；AI 工坊与 OpenAI 兼容模式默认内联完整视频字节。本地 Qwen 是单独的、明确标注的视觉采样路径：读取真实帧率/PTS 与活动裁剪窗口，生成带时间戳的有序联系表，不读取音轨。
- 支持 MP4、AVI、MOV、MKV，单文件不超过 50 MB。
- Ref2VA 单个视频时长 2–15 秒，多个视频总时长不超过 15 秒。
- Ref2VA 最多 9 张图片、3 个视频，总素材数最多 12。
- 云端渠道仍拒绝带活动裁剪窗口的原生 `VIDEO`，因为上传底层流可能仍指向未裁剪原文件；本地 Qwen 不上传原视频，会按活动裁剪窗口和 PTS 采样，因此允许直接使用裁剪窗口。
- 平价小屋返回的素材上传 URL 是临时链接，应只用于当前模型请求；AI 工坊与 OpenAI 兼容模式没有中间上传步骤。

## 输出与错误行为

H3 与 Seedance 2.0 输出：

```text
enhanced_prompt: STRING
```

只要 Chat Completions 返回非空正文，节点就会输出，不会因为字段缺失、Markdown、镜头编号、时间码、目标长度或 `finish_reason=length` 报错。

MiniMax-H3 节点唯一的本地整理规则：

1. 当前任务的全部预期字段均以精确字段名命中；
2. 每个字段只出现一次；
3. 字段顺序确实错误。

三个条件同时成立时按官方顺序重排；任何字段未命中、缺失、重复，或者本来就是正确顺序时，保持上游原文。

Seedance 2.0 没有 H3 固定字段，因此不做字段重排和格式验收；非空上游正文直接输出。两个节点都不会因目标字数或镜头数量偏差报错，也不会为修复格式自动发起第二次付费请求。

Music 3 输出四个 `STRING`：

```text
lyrics
music_caption
music3_payload_json = {"input": lyrics, "instructions": music_caption}
enhancement_report_json
```

Music 3 只在三个官方标题都被唯一命中但顺序错误时进行本地重排；标题缺失或上游使用其他可用格式时直接放行非空正文，同时在增强报告中给出警告代码。目标字数、歌词长度或结构没有精确命中不属于节点错误。报告还会做歌词原句泄漏、所选官方参考短语重叠、纯器乐误加人声、段落时间线遗漏和官方 5000 Token 预算的软检查；这些检查不把已有非空结果变成节点错误。

以下情况仍会报错：

- API Key 无效或余额不足；
- 网络、超时、限流或供应商 5xx；
- 素材编码、上传或多模态请求失败；
- 响应不是合法 JSON；
- 响应缺少正文或正文全空白。
- 本地渠道缺少/损坏 GGUF、mmproj 或 llama.cpp 运行时，视觉/上下文预算越界，或本地推理进程异常退出。

平价小屋的 `https://api.seedance.nz/v1/chat/completions` 遇到 SSL/建连故障，或 HTTP 500/502/503/504 与 Cloudflare 520–526/530 网关故障时会快速重试：共 3 次尝试，按“环境代理 → 显式直连 → 环境代理”切换网络路径，间隔 0.5 秒和 1 秒；任意一次取得成功响应都会继续正常输出。401、余额不足、429、读取超时和用户自定义 OpenAI 兼容接口不会自动重试。读取超时时服务端可能已经完成生成，节点会保留错误而不盲目重复付费。Seedance 素材上传同样会在安全的连接/网关故障下切换路径；上传遇到 429 时仍按服务端提示等待后重试。

Music 3 的 `official_reference_selection` 是“官方完整”模式必经阶段：必须成功选中至少 1 个官方模板才能继续编译 Caption。在 `api.seedance.nz` 遇到临时网关故障时最多尝试 6 次，按 0.5、1、2、4、8 秒有界退避；不会静默降级为无模板生成。

## 测试

在 ComfyUI 根目录的上一级运行：

```powershell
.\python\python.exe -m unittest discover -s ComfyUI\custom_nodes\comfyui-minimax-h3-prompt-enhancer-T8\tests -v
```

单元测试使用 mock API、本地媒体夹具和官方 Skill 静态资源，不联网、不上传素材、不产生费用。`tests/test_music3.py` 还会核验全部 18 个索引、1000 个模板、固定内容树哈希、逐级披露上限、歌词隔离、局部润色边界、安全 control tags、阶段缓存、诊断脱敏和云端 provider 重试合同；`tests/test_local_qwen.py` 核验第四渠道免 Key、模型路径安全、seed 映射、图片 Base64、真实时间戳视频抽样、按首次出现顺序描述视频阶段、无音轨声明、三节点接线以及 Music 不加载视觉能力。`tests/test_platform_11.py` 独立验证共享传输重试、诊断字段白名单与 URL/Key/错误正文脱敏，以及三节点旧工作流迁移矩阵。

维护者发布前还应运行确定性仓库门禁；它会检查禁入文件、疑似密钥、全部已跟踪 JSON、官方 Skill 快照、Python/JavaScript 语法、`.comfyignore` 实际发布面、Registry YARA 触发模式和 90 MiB GIF 总预算。该上限专门为 Comfy Registry 的 100 MB ZIP 扫描保留余量，避免 Action 发布成功但版本随后被标记为 `Flagged`：

```powershell
.\python\python.exe ComfyUI\custom_nodes\comfyui-minimax-h3-prompt-enhancer-T8\tools\verify_repository.py
.\python\python.exe ComfyUI\custom_nodes\comfyui-minimax-h3-prompt-enhancer-T8\tools\release.py --check-prepush
```

本地 Qwen 发布验收不调用云端 API，但会真实加载约 18GB 权重并长时间占用本机 GPU/CPU。只有明确接受本地算力消耗时运行：

```powershell
.\python\python.exe ComfyUI\custom_nodes\comfyui-minimax-h3-prompt-enhancer-T8\local_qwen_live_smoke.py --confirm-local-large-model
.\python\python.exe ComfyUI\custom_nodes\comfyui-minimax-h3-prompt-enhancer-T8\local_qwen_live_smoke.py --confirm-local-large-model --model qwen3.8-27b-uncensored-fp8-q4_k_m.gguf --output ComfyUI\custom_nodes\comfyui-minimax-h3-prompt-enhancer-T8\tests\fixtures\local_qwen_uncensored_quality_2026-08-21.json
```

2026-08-19 在 RTX 4060 Ti 16GB / llama.cpp CUDA 12 上的固定验收结果为 `100/100`、`passed=true`：同 seed 三次逐字一致、H3 T2VA、Music 3 中文新歌词与官方完整 Skill、H3 图像+视频、Seedance 2.0 图像+视频五项全部通过。Music 约束逐项核验 92 BPM、D major、4/4、女主唱、钢琴、原声吉他与排除 rap；视觉夹具逐项核验图片代码、视频早晚代码、运动方向、硬切和时序。全套耗时约 964 秒，峰值显存 15091 MiB，卸载后回到 2246 MiB（基线 2223 MiB）。脱敏报告见 `tests/fixtures/local_qwen_quality_2026-08-19.json`；不包含提示词正文、歌词、Base64、API Key 或本地临时令牌。

`live_smoke.py` 用于平价小屋的 MiniMax-H3；`seedance20_live_smoke.py` 用于平价小屋的 Seedance 2.0。`workshop_live_smoke.py` 会让两个节点各走一次 AI 工坊：H3 使用默认模型，Seedance 2.0 使用 Custom 路径但填写同一个 `gemini-3.5-flash`。测试会生成带独有文字、颜色、形状和两阶段运动的本地图片与完整 4 秒 MP4，并核验两个节点是否真的识别图片和视频时间顺序。真实测试会产生 Token 费用，只有明确接受费用时才运行：

```powershell
.\python\python.exe ComfyUI\custom_nodes\comfyui-minimax-h3-prompt-enhancer-T8\live_smoke.py --confirm-paid
.\python\python.exe ComfyUI\custom_nodes\comfyui-minimax-h3-prompt-enhancer-T8\seedance20_live_smoke.py --confirm-paid
$env:T8STAR_API_KEY="你的 AI 工坊 API Key"
.\python\python.exe ComfyUI\custom_nodes\comfyui-minimax-h3-prompt-enhancer-T8\workshop_live_smoke.py --confirm-paid
```

前两个脚本运行前设置 `SEEDANCE_API_KEY`；AI 工坊脚本设置 `T8STAR_API_KEY`。不要把真实 Key 写进命令参数、脚本或工作流后上传到公开仓库。

Music 3 发布质量验收使用 4 个真实工作流：中文新歌词、原歌词逐字保留、纯器乐融合、只改第二段主歌；另用一次批量结构化评审。确定性合同分占 70%，LLM 内容质量评审占 30%，每案总分必须至少 85、内容评审至少 80，且没有标题合同、payload、歌词隔离、器乐或编辑边界硬失败。结果写入脱敏 JSON，不包含 API Key。若个别案例或最终评审失败，脚本会以原子 checkpoint 续跑而不重复已完成案例；通过后自动删除 checkpoint：

```powershell
$env:SEEDANCE_API_KEY="你的平价小屋 API Key"
.\python\python.exe ComfyUI\custom_nodes\comfyui-minimax-h3-prompt-enhancer-T8\music3_live_smoke.py --confirm-paid
```

官方 Skill 不会在用户运行节点时联网更新。维护者拿到经过审阅的 MiniMax-Music3 本地 checkout 后，可先只读核验，再显式更新固定快照；工具会检查 18 个索引、1000 个模板、1022 个文件和归一化哈希，并同步 `SOURCE.json` 与运行时常量：

```powershell
.\python\python.exe ComfyUI\custom_nodes\comfyui-minimax-h3-prompt-enhancer-T8\tools\update_music3_official_skill.py --check-current
.\python\python.exe ComfyUI\custom_nodes\comfyui-minimax-h3-prompt-enhancer-T8\tools\update_music3_official_skill.py --source-dir D:\MiniMax-Music3 --commit 40位提交SHA --apply
```

H3 核心 Skill 同样使用审阅后显式更新，不会在用户运行时联网拉取：

```powershell
.\python\python.exe ComfyUI\custom_nodes\comfyui-minimax-h3-prompt-enhancer-T8\tools\update_h3_official_skill.py --check-current
.\python\python.exe ComfyUI\custom_nodes\comfyui-minimax-h3-prompt-enhancer-T8\tools\update_h3_official_skill.py --source-dir D:\MiniMax-H3 --commit 40位提交SHA --apply
.\python\python.exe ComfyUI\custom_nodes\comfyui-minimax-h3-prompt-enhancer-T8\tools\check_upstream_skills.py
```

## 参考资料

- [MiniMax-H3 基础提示词指南](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_base_en.md)
- [MiniMax-H3 完整参考模式指南](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_ref_en.md)
- [MiniMax-H3 官方创意 Skills 快照](https://github.com/MiniMax-AI/MiniMax-H3/tree/743d51e83329cbae6c7694f1c7b89576e7c25e07/skills)
- [MiniMax-H3 官方核心 Prompt Writing Skill（固定提交）](https://github.com/MiniMax-AI/MiniMax-H3/blob/d21241f0a4b3acbb34c97dae47fa417b7065e438/skills/h3-prompt-writing/SKILL.md)
- [MiniMax-H3 官方 Music Video Subtitle Generator Skill v0.6.6](https://github.com/MiniMax-AI/MiniMax-H3/blob/743d51e83329cbae6c7694f1c7b89576e7c25e07/skills/music-video-subtitle-generator/SKILL.cn.md)
- [Seedance API 文档](https://api.seedance.nz/docs/llms.txt)
- [Seedance 模型页面](https://api.seedance.nz/pricing/bytedance%2Fdoubao-seed-evolving)
- [Seedance 2.0 官方模型页](https://seed.bytedance.com/en/seedance2_0)
- [Seedance 2.0 官方 Prompt Optimizer Skill](https://arkdocs.tos-cn-beijing.volces.com/files/video-generation/SKILL.md)
- [MiniMax Music 3 官方仓库](https://github.com/MiniMax-AI/MiniMax-Music3)
- [MiniMax Music 3 官方 `music-caption-rewriter` Skill（固定提交）](https://github.com/MiniMax-AI/MiniMax-Music3/tree/91410fb657c007ae57c60df8240f5ece5be089c7/skills/music-caption-rewriter)
- [Qwen3.8-27B GGUF（固定 revision 下载来源）](https://huggingface.co/unsloth/Qwen3.8-27B-GGUF)
- [本地 GGUF 参考项目 ComfyUI_Qwen_H3_Prompt](https://github.com/chflame163/ComfyUI_Qwen_H3_Prompt)
- [llama.cpp](https://github.com/ggml-org/llama.cpp)

## 说明

本项目是第三方 ComfyUI 自定义节点，不隶属于 MiniMax、ByteDance、Seedance 或 ComfyUI 官方。API 能力、价格和可用性以服务商最新说明为准。使用真人参考素材时，用户仍需自行确认身份授权和下游平台规则。

## 本地 Skill 与整合包

三个核心节点底部均提供“MiniMax & Seedance本地Skill和整合包”入口，点击会在新标签页打开 [T8 本地 Skill 与整合包](https://github.com/T8mars/minimax-h3-prompt-skill-T8)。该入口仅用于访问资源，不会写入工作流，也不会参与或改变任何 LLM 请求。
