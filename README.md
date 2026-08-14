## 入口导航

| 入口 | 适合用户 | 说明 | 打开 |
| --- | --- | --- | --- |
| 贞贞的平价AI小铺（国内版） | 国内用户、国内模型优先 | 主要调用国内模型，适合国内模型工作流。 | <a href="https://api.seedance.nz/sign-up?aff=5f4w"><kbd>进入国内版平价AI小铺</kbd></a> |
| 贞贞的AI工坊（海外版） | 海外用户、海外模型优先 | 主要调用海外模型，也包含部分国内模型。 | <a href="https://ai.t8star.org/register?aff=dP7j"><kbd>进入海外版AI工坊</kbd></a> |
| RunningHub APIKEY（国内版） | 需要适配更多 AI 应用的国内用户 | 适配更多 AI 应用，并可体验最新模型。 | <a href="https://www.runninghub.cn/user-center/1819214514410942465/webapp?inviteCode=rh-v1121"><kbd>获取国内版 APIKEY</kbd></a> |
| RunningHub APIKEY（海外版） | 海外模型、更宽松审核场景 | 审核更宽松，支持海外模型。 | <a href="https://www.runninghub.ai/user-center/1907375370302308353/webapp?inviteCode=rh-v1121"><kbd>获取海外版 APIKEY</kbd></a> |

# ComfyUI MiniMax-H3 / Seedance 2.0 / Music 3 Prompt Enhancer T8

一组面向 MiniMax-H3、Seedance 2.0 视频生成和 MiniMax Music 3 音乐生成的 ComfyUI 提示词增强节点。H3 与 Seedance 2.0 节点能把用户文字与真实 `IMAGE` / `VIDEO` 素材放进同一次多模态请求；Music 3 节点只处理文字，并把歌词、官方 Structured Caption 和可直接交给下游的 JSON 分开输出。三个节点均可选择贞贞平价小屋、贞贞的 AI 工坊或用户自己的 OpenAI 兼容接口。

三个节点共享已经验证的 API、密钥和错误处理，但提示词协议完全隔离：MiniMax-H3 使用其官方字段、任务类型和时间码；Seedance 2.0 使用任务意图、`镜头N` 事件顺序和官方多模态引用语法；Music 3 严格执行官方 `music-caption-rewriter` 的三段描述合同。Music 3 是独立音乐模型，不是 H3 视频模型。

## 三个独立节点

| 节点 | 用途 | 主要任务 |
| --- | --- | --- |
| `MiniMax H3 Prompt Enhancer (Seedance / AI Workshop / OpenAI)` | 生成 MiniMax-H3 提示词 | T2VA / I2VA / FL2VA / L2VA / Ref2VA |
| `Seedance 2.0 Prompt Enhancer (Seedance / AI Workshop / OpenAI)` | 生成 Seedance 2.0 提示词 | T2V、首帧、首尾帧、多模态参考、编辑、延长、轨道补齐和组合任务 |
| `MiniMax Music 3 Prompt & Lyrics Enhancer (T8)` | 生成 Music 3 歌词与音乐描述 | AUTO、生成歌词、严格保留、局部润色、纯器乐 |

本项目目前不包含 Seedance 2.5 提示词节点，也不调用视频或音乐生成、轮询、试听或下载接口。

## 功能特点

- 平价小屋固定视觉模型 `bytedance/doubao-seed-evolving`；AI 工坊默认 `gemini-3.5-flash` 并支持 Custom；OpenAI 兼容模式支持填写供应商自己的视觉模型 ID。
- 同时分析文字、图片和完整视频，不用抽帧冒充视频理解。
- 支持首帧、尾帧、首尾帧以及多图、多视频参考。
- 集成 MiniMax-H3 官方核心 Skill，规则冻结于官方提交 `093f3129a3f7bd27c74928b1cd31a54fbdebe057`。
- 支持现有中英文兼容协议，以及官方所有说明字段强制英文的严格协议。
- 官方共 9 个 Skill：1 个 H3 核心写作 Skill 始终启用，另有 `无 / AUTO` 和全部 8 个可选场景写作 Skill；其中“音乐 MV 动态字幕（官方）”已同步 MiniMax `music-video-subtitle-generator` v0.6.6。选择具体场景 Skill 后，节点内会显示用途、适用范围、推荐输入、结构锚点、可安全填入的示例、MiniMax 官方 GIF 与来源链接。预设只优化提示词，不运行完整制作工作流。
- 两个节点共享独立的 `非官方模板（案例 / 社区 Skill）` 列表：109 条已发布案例事实归并为 94 个稳定案例 selector（含 15 个同机制证据变体），另有 2 个独立用户贡献社区 Skill，共 96 个非官方下拉项；全部提供中文名称、用途、简约推荐输入、2–5 个结构锚点和随 GitHub 直接分发的轻量 GIF 预览。
- 支持中文 / English 输出。
- 支持 `strict / balanced / creative` 三档改写。
- 支持 `AUTO` 或固定 1–20 个镜头的下拉控制。
- 支持用户参考模板融合，主提示词与可观察媒体事实优先。
- 提供随机种子以及 `fixed / randomize / increment / decrement` 状态。
- 提供节点内 API Key 输入、遮罩显示、保存、清空和注册链接。
- 支持贞贞平价小屋、贞贞的 AI 工坊，以及显式配置的 OpenAI 兼容备用接口。
- H3/Seedance 输出单一提示词 `STRING`；Music 3 分别输出歌词、Structured Caption、payload JSON 和安全增强报告四个 `STRING`。
- 新增独立 Seedance 2.0 节点：简单/复杂双路径、AUTO/固定 1–20 镜头、官方/Seedance.nz 引用语法、字幕与稳定性策略。
- 新增独立 Music 3 节点：完整内置官方 `music-caption-rewriter`、18 个流派索引和 1000 个模板，并严格按 router → 最多 2 个索引 → 最多 3 个模板逐级披露，绝不会把全库塞进一次 LLM 请求。
- Music 3 的官方 Caption 与歌词完全分离；生成/润色歌词属于清楚标注的 T8 非官方扩展，严格保留模式不会改动用户歌词。

## 安装

在 ComfyUI 的 `custom_nodes` 目录执行：

```bash
git clone https://github.com/T8mars/comfyui-minimax-h3-prompt-enhancer-T8.git
```

目录结构应为：

```text
ComfyUI/
└─ custom_nodes/
   └─ comfyui-minimax-h3-prompt-enhancer-T8/
```

本节点不增加额外 Python 依赖，使用 ComfyUI 已安装的 `requests`、NumPy、Pillow 和原生媒体类型。安装后重启 ComfyUI；如果节点或前端界面没有更新，请对浏览器执行一次 `Ctrl+F5`。

在节点菜单中搜索任一节点：

```text
MiniMax H3 Prompt Enhancer (Seedance / AI Workshop / OpenAI)
Seedance 2.0 Prompt Enhancer (Seedance / AI Workshop / OpenAI)
MiniMax Music 3 Prompt & Lyrics Enhancer (T8)
```

## 快速使用

1. 添加 `MiniMax H3 Prompt Enhancer (Seedance / AI Workshop / OpenAI)`。
2. 在“视频创意 / 提示词”中输入基础意图。
3. 选择生成类型、时长、镜头数量、改写模式、输出语言、官方 Skill 协议和 MiniMax 官方创意预设；需要时再选择一个非官方案例或社区 Skill 模板。
4. I2VA / FL2VA / L2VA / Ref2VA 按任务要求连接图片或视频。
5. 填写 API Key，点击“保存到工作流”；或者使用环境变量。
6. 点击节点底部的“运行提示词优化”。
7. 从 `enhanced_prompt` 获取最终字符串。

可以直接把 [`example/minimax_h3_prompt_enhancer_example.json`](./example/minimax_h3_prompt_enhancer_example.json) 拖入 ComfyUI。示例工作流不包含 API Key。

## MiniMax Music 3 快速使用

1. 添加 `MiniMax Music 3 Prompt & Lyrics Enhancer (T8)`。
2. 在“音乐创意”中写明风格、主题、情绪、用途和希望的编曲发展。
3. 选择歌词模式：`AUTO / 生成新歌词 / 严格保留歌词 / 按要求润色 / 纯器乐`。已有歌词可以通过普通 `STRING` 接入。
4. “官方完整（2–4 次请求）”会按官方逐级披露选择参考；“快速核心（1–2 次请求）”只执行官方核心合同。调用次数取决于是否还要生成或润色歌词，不会同时调用三个供应商。
5. 填写当前所选 LLM 渠道的 API Key，点击“运行 Music 3 提示词与歌词优化”。
6. 将 `lyrics` 接到 Music 3 的 `input`，将 `music_caption` 接到 `instructions`；也可以直接解析 `music3_payload_json`。
7. `enhancement_report_json` 只记录阶段、付费请求数、缓存命中、官方快照哈希、Token 预算估算与警告代码，不包含歌词、用户创意、API Key、供应商 URL、模板 ID 或模板正文。

可以直接导入 [`example/music3_prompt_lyrics_enhancer_example.json`](./example/music3_prompt_lyrics_enhancer_example.json)。示例不包含 API Key、音频或官方模板正文。

## Seedance 2.0 快速使用

1. 添加 `Seedance 2.0 Prompt Enhancer (Seedance / AI Workshop / OpenAI)`。
2. 填写“视频创意 / 提示词”。任务意图、组织方式、时长和镜头数都可先保持 `AUTO`。
3. 按任务连接首帧、尾帧、参考图片或完整参考视频。
4. 选择官方中文 `@图片N/@视频N` 或 Seedance.nz 英文 `@Image N/@Video N` 引用格式。
5. 可选一个 `非官方模板（案例 / 社区 Skill）`，用于迁移因果结构、节奏和镜头语法。
6. 填写的是“提示词增强 LLM API Key”，保存后点击节点底部运行按钮。
7. 把 `enhanced_prompt` 连接到下游 Seedance 2.0 视频节点的提示词输入。

可以直接导入 [`example/seedance20_prompt_enhancer_example.json`](./example/seedance20_prompt_enhancer_example.json)。示例不包含 API Key。

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
- 镜头数支持 `AUTO` 或固定 1–20。固定镜头是传给 LLM 的软生成约束；在 4–15 秒内使用较高镜头数时，上游可能合并或省略镜头，节点不会因此判错。
- 目标时长支持 `AUTO` 或 4–15 秒，只控制整体内容密度，不生成 H3 的毫秒时间码，也不默认写逐镜头绝对秒数。
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

109 条来源案例中有 94 个案例 selector 和 15 个 evidence variant，当前没有 pending case；证据变体只增加同一机制的 GIF 与证据，不重复增加下拉。`batch-2026-08-14-01` 新增 14 个稳定 selector，并把 5 个第二来源证据合并到 `复古手持｜日常送别回眸`、`角色卡验真｜四类证据锁定角色`、`纪实跟拍｜行进中偶遇再离开`、`平面重组｜几何节奏品牌片` 等既有模板。旧工作流中的 `声画错位递进` / `t8-case-audio-cause-lead-ladder-v1` 会迁移到证据支持的 `景别收紧｜从世界到眼神`。

另外两个独立的用户贡献社区 Skill 不合并进案例 registry，也不冒充官方 Skill：

| 社区 Skill | 可复用机制 |
| --- | --- |
| `自然街拍互动｜边走边聊到清楚落点` | 连续路线跟拍中用距离、步态、视线、手势、视差与现场声推进到可读互动结果 |
| `突遇惊吓到和解｜贴近反转与求和手势` | 平静基线、一次非致命惊慌、距离反转和被看见的求和手势组成关系反转 |

打开 `MiniMax 官方场景 Skill（8 个可选）` 或 `非官方模板（案例 / 社区 Skill）` 下拉时，鼠标悬停任一具体选项会在菜单右侧即时显示对应 GIF、用途和简约推荐输入；菜单靠近窗口右边时预览会自动移到左侧。键盘上下选择和搜索过滤也会同步预览。选择任一具体官方场景 Skill 或非官方模板后，节点内都会显示用途、适用/推荐输入格式、必须实现的结构锚点、推荐示例、GIF 和来源链接。`填入推荐示例` 只有在主提示词为空时才写入；已有输入会显示“已有输入，未覆盖”。推荐示例只是可编辑的实例意图，不是最终提示词。即使只输入“美丽的女人”，节点也会保留这个主体，并要求 LLM 原创建立模板需要的场景、触发、事件链和可见结果，不能退化成普通人像运镜。

GIF 只供浏览器中的人类界面预览，绝不会连接到首帧、尾帧、参考图片、参考视频，也不会发送给 LLM。8 个官方预设 GIF 和 111 个 T8 案例/社区 Skill 轻量 GIF 均随 GitHub 仓库直接分发；全新下载不需要额外清单或本地案例目录。T8 GIF 由内置 manifest 按案例 ID、来源 SHA-256、分发文件 SHA-256 和 GIF 文件头完整校验。

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
  --library G:\minimax-skill-T8\comfyui-handoffs\unofficial-case-library-v2.json `
  --community-skills G:\minimax-skill-T8\comfyui-handoffs\standalone-community-skills-v1.json `
  --existing-catalog case_templates\catalog.json `
  --source-batch-dir case_templates\source_batches `
  --output case_templates/catalog.json
```

每次案例目录发生变化，都必须同步生成并提交完整的内置预览包，不能只提交 selector 元数据。生成器要求输出目录不存在或为空；建议先生成到待审目录，核对后再整体替换正式目录：

```powershell
python tools/bundle_t8_case_previews.py `
  --library G:\minimax-skill-T8\comfyui-handoffs\unofficial-case-library-v2.json `
  --community-skills G:\minimax-skill-T8\comfyui-handoffs\standalone-community-skills-v1.json `
  --catalog case_templates\catalog.json `
  --output-dir web\js\assets\t8-case-previews-next `
  --ffmpeg F:\AI-T8-video-onekey\ffmpeg\bin\ffmpeg.exe
```

导入器要求 109 条案例记录严格组成 94 个 selector + 15 个 evidence variant + 0 个 pending case，并另验 2 个独立社区 Skill，最终生成 96 个非官方下拉项。已发布案例必须 `released/approved`，H3 与 Seedance 2.0 recipe 均通过、`media_connections=[]`、provider/secret 字段为空、无旧 `openai_upload_url`、两份 recipe 的 Creative DNA 一致；若以后再次出现 pending case，必须保持未发布、未复审、有明确 blocker、无 adapter，并且不能进入下拉或预览分发。社区 Skill 必须保持非官方/用户贡献、不得合并进案例 registry，并现场重算 Skill、摘要、双模型 guidance 与 GIF 哈希。提示词目录不会写入本地路径、来源 URL、来源视频或成品提示词；分发包只保存已发布项的轻量 GIF、不可逆哈希与编码参数。Markdown 报告只是说明，不能代替机器 JSON、实时 recipe、内置预览覆盖率与哈希核验。

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

- 用户提供的歌词逐字锁定，保持原语言、标点、顺序和重复，不翻译、不润色、不补写；只有未提供歌词且明确写出“允许生成原创歌词”时，才会创作一段能放进当前 4–15 秒时长的短篇原创歌词，并将同一文本用于演唱与可见文字。否则不会自动创建歌词、歌手或口型。
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
| `duration_seconds` | 目标时长，4–15 秒 |
| `shot_count` | `AUTO` 由模型按内容、素材、时长和节奏判断；也可固定为 1–20 个镜头 |
| `rewrite_mode` | `strict / balanced / creative` |
| `description_word_target` | `0` 为自动；非零为 80–1000，中文按约数汉字、英文按单词理解 |
| `output_language` | `中文 / English`，默认中文 |
| `prompt_mode` | `官方增强 / 参考模板融合` |
| `official_skill_profile` | 界面显示为“H3 核心写作 Skill（始终启用）”；`现有兼容 / 官方 Skill 严格`，默认兼容，严格档位强制英文说明正文 |
| `creative_preset` | 界面显示为“MiniMax 官方场景 Skill（8 个可选）”；`无 / AUTO / 8 个官方场景写作预设`，选择具体项后显示详情卡和官方 GIF |
| `case_template` | `无 / 96 个非官方模板`：94 个 T8 案例 selector + 2 个独立社区 Skill；显示中文名称，工作流保存稳定 ID，H3 与 Seedance 2.0 使用独立原生适配规则 |
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

三个节点中的 Key 都用于当前所选 LLM 渠道的提示词增强请求，不是下游 Seedance 2.0 视频生成或 Music 3 音频生成 API Key。

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

备用模式只需一个 API Base URL 和模型 ID。Base URL 支持服务根地址、以 `/v1` 结尾的地址，或完整 `/chat/completions` 地址。节点 Key 留空时读取 `OPENAI_API_KEY`，Base URL 留空时读取 `OPENAI_BASE_URL`；H3/Seedance 需要供应商实际支持的视觉模型，Music 3 只需要文本模型。

#### 修复后的节点配置

MiniMax H3 与 Seedance 2.0 两个节点使用相同的 OpenAI 兼容配置：

| 节点字段 | 是否必填 | 用法 |
| --- | --- | --- |
| `API Key` | 是 | 可连接任意 `STRING`，也可在节点内填写；节点留空时读取 `OPENAI_API_KEY` |
| `OpenAI 模型 ID` | 是 | 填写兼容服务商提供的完整视觉模型 ID，不再固定为 `bytedance/doubao-seed-evolving` |
| `OpenAI Base URL` | 是 | 只填写一个聊天接口地址；节点会把服务根地址或 `/v1` 地址规范化为 `/v1/chat/completions` |
| `视频素材 URL` | 否 | 仅用于视频，每行一个，按已连接 `VIDEO` 的顺序对应；未填写的已连接视频自动使用 Base64 |

不再需要、也不要填写单独的“兼容素材上传 URL”。图片没有素材 URL 字段，始终由节点编码成 Base64 并随聊天请求直接发送。

该模式不再使用第二个素材上传端点：

- 图片统一编码为 PNG，通过 `image_url.url` 中的 `data:image/png;base64,...` 内联到同一次 Chat Completions 请求。
- 视频默认通过 `video_url.url` 中的 `data:video/...;base64,...` 内联完整视频字节。
- “视频素材 URL”可选，每行一个，按已连接 VIDEO 的顺序替代对应视频的 Base64；未覆盖的视频继续使用 Base64。
- 视频 URL 数量不能超过已连接 VIDEO 数量，且必须是 HTTP(S) 地址。

OpenAI 官方 Chat Completions 明确定义了 Base64 图片输入，但通用 `video_url` 并不是所有兼容供应商都支持的统一能力。这里的视频格式面向声明支持视频理解的兼容网关；用户填写的模型和网关必须同时支持视频内容部件，节点不会降级到纯文字或抽帧请求。

## API Key 安全

三个节点都提供标准 `STRING` API Key 接口，并保留底部的遮罩、显示、保存和清空按钮。外部接线值优先。遮罩只能避免画布上直接显示明文：点击“保存到工作流”后，Key 会进入工作流 JSON。

- 分享工作流前务必点击“清空”。
- 更安全的方式是把节点 Key 留空并使用环境变量。
- 节点不会把 Key、请求正文、素材 URL 或响应正文写入日志。
- 仓库示例和测试不包含真实 API Key。

## 图片与视频处理

- 图片编码为 PNG；平价小屋模式上传，AI 工坊与 OpenAI 兼容模式内联为 Base64 Data URL。
- 视频使用 ComfyUI 原生 `VIDEO` 的完整流，不抽帧、不转成图片列表，也不在本地截取前 5 秒；AI 工坊与 OpenAI 兼容模式默认内联完整视频字节。
- 支持 MP4、AVI、MOV、MKV，单文件不超过 50 MB。
- Ref2VA 单个视频时长 2–15 秒，多个视频总时长不超过 15 秒。
- Ref2VA 最多 9 张图片、3 个视频，总素材数最多 12。
- 带活动裁剪窗口的原生 `VIDEO` 会在上传前被拒绝，因为底层流可能仍指向未裁剪原文件。请先把片段另存为新视频再连接。
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

平价小屋的 `https://api.seedance.nz/v1/chat/completions` 遇到 SSL/建连故障，或 HTTP 500/502/503/504 与 Cloudflare 520–526/530 网关故障时会快速重试：共 3 次尝试，间隔 0.5 秒和 1 秒；任意一次取得成功响应都会继续正常输出。401、余额不足、429、读取超时和用户自定义 OpenAI 兼容接口不会自动重试。读取超时时服务端可能已经完成生成，节点会保留错误而不盲目重复付费。免费素材上传遇到 429 时最多重试一次。

## 测试

在 ComfyUI 根目录的上一级运行：

```powershell
.\python\python.exe -m unittest discover -s ComfyUI\custom_nodes\comfyui-minimax-h3-prompt-enhancer-T8\tests -v
```

单元测试使用 mock API、本地媒体夹具和官方 Skill 静态资源，不联网、不上传素材、不产生费用。`tests/test_music3.py` 还会核验全部 18 个索引、1000 个模板、固定内容树哈希、逐级披露上限、歌词隔离、局部润色边界、安全 control tags、阶段缓存、诊断脱敏、三种 provider 与重试合同。

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

## 参考资料

- [MiniMax-H3 基础提示词指南](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_base_en.md)
- [MiniMax-H3 完整参考模式指南](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_ref_en.md)
- [MiniMax-H3 官方 Skills 目录](https://github.com/MiniMax-AI/MiniMax-H3/tree/b7227fa6a6206e9fb30562383d39e53cf3866a48/skills)
- [MiniMax-H3 官方核心 Prompt Writing Skill](https://github.com/MiniMax-AI/MiniMax-H3/blob/093f3129a3f7bd27c74928b1cd31a54fbdebe057/skills/h3-prompt-writing/SKILL.md)
- [MiniMax-H3 官方 Music Video Subtitle Generator Skill v0.6.6](https://github.com/MiniMax-AI/MiniMax-H3/blob/b7227fa6a6206e9fb30562383d39e53cf3866a48/skills/music-video-subtitle-generator/SKILL.cn.md)
- [Seedance API 文档](https://api.seedance.nz/docs/llms.txt)
- [Seedance 模型页面](https://api.seedance.nz/pricing/bytedance%2Fdoubao-seed-evolving)
- [Seedance 2.0 官方模型页](https://seed.bytedance.com/en/seedance2_0)
- [Seedance 2.0 官方 Prompt Optimizer Skill](https://arkdocs.tos-cn-beijing.volces.com/files/video-generation/SKILL.md)
- [MiniMax Music 3 官方仓库](https://github.com/MiniMax-AI/MiniMax-Music3)
- [MiniMax Music 3 官方 `music-caption-rewriter` Skill（固定提交）](https://github.com/MiniMax-AI/MiniMax-Music3/tree/91410fb657c007ae57c60df8240f5ece5be089c7/skills/music-caption-rewriter)

## 说明

本项目是第三方 ComfyUI 自定义节点，不隶属于 MiniMax、ByteDance、Seedance 或 ComfyUI 官方。API 能力、价格和可用性以服务商最新说明为准。使用真人参考素材时，用户仍需自行确认身份授权和下游平台规则。

## 本地 Skill 与整合包

三个核心节点底部均提供“MiniMax & Seedance本地Skill和整合包”入口，点击会在新标签页打开 [T8 本地 Skill 与整合包](https://github.com/T8mars/minimax-h3-prompt-skill-T8)。该入口仅用于访问资源，不会写入工作流，也不会参与或改变任何 LLM 请求。
