# ComfyUI MiniMax-H3 / Seedance 2.0 Prompt Enhancer T8

一组面向 MiniMax-H3 与 Seedance 2.0 视频生成的 ComfyUI 提示词增强节点。两个节点固定调用 `bytedance/doubao-seed-evolving`，能够把用户文字与真实 `IMAGE` / `VIDEO` 素材放进同一次多模态请求，输出可连接下游节点的 `STRING`。

两个节点共享已经验证的 API、上传、密钥和错误处理，但提示词协议完全隔离：MiniMax-H3 使用其官方字段、任务类型和时间码；Seedance 2.0 使用任务意图、`镜头N` 事件顺序和官方多模态引用语法，绝不是把 H3 节点换名字。

## 两个独立节点

| 节点 | 用途 | 主要任务 |
| --- | --- | --- |
| `MiniMax H3 Prompt Enhancer (Seedance / OpenAI)` | 生成 MiniMax-H3 提示词 | T2VA / I2VA / FL2VA / L2VA / Ref2VA |
| `Seedance 2.0 Prompt Enhancer (Seedance / OpenAI)` | 生成 Seedance 2.0 提示词 | T2V、首帧、首尾帧、多模态参考、编辑、延长、轨道补齐和组合任务 |

本项目目前不包含 Seedance 2.5 提示词节点，也不调用视频生成、轮询或下载接口。

## 功能特点

- 固定视觉模型 `bytedance/doubao-seed-evolving`，没有纯文本模型回退。
- 同时分析文字、图片和完整视频，不用抽帧冒充视频理解。
- 支持首帧、尾帧、首尾帧以及多图、多视频参考。
- 集成 MiniMax-H3 官方核心 Skill，规则冻结于官方提交 `093f3129a3f7bd27c74928b1cd31a54fbdebe057`。
- 支持现有中英文兼容协议，以及官方所有说明字段强制英文的严格协议。
- 内置 `无 / AUTO` 和全部 8 个官方场景写作预设；预设只优化提示词，不运行完整制作工作流。
- 支持中文 / English 输出。
- 支持 `strict / balanced / creative` 三档改写。
- 支持 `AUTO` 或固定 1–20 个镜头的下拉控制。
- 支持用户参考模板融合，主提示词与可观察媒体事实优先。
- 提供随机种子以及 `fixed / randomize / increment / decrement` 状态。
- 提供节点内 API Key 输入、遮罩显示、保存、清空和注册链接。
- 支持贞贞平价小屋固定接口和显式配置的 OpenAI 兼容备用接口。
- 输出单一 `STRING`，可直接连接下游提示词输入。
- 新增独立 Seedance 2.0 节点：简单/复杂双路径、AUTO/固定 1–20 镜头、官方/Seedance.nz 引用语法、字幕与稳定性策略。

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
MiniMax H3 Prompt Enhancer (Seedance / OpenAI)
Seedance 2.0 Prompt Enhancer (Seedance / OpenAI)
```

## 快速使用

1. 添加 `MiniMax H3 Prompt Enhancer (Seedance / OpenAI)`。
2. 在“视频创意 / 提示词”中输入基础意图。
3. 选择生成类型、时长、镜头数量、改写模式、输出语言、官方 Skill 协议和创意预设。
4. I2VA / FL2VA / L2VA / Ref2VA 按任务要求连接图片或视频。
5. 填写 API Key，点击“保存到工作流”；或者使用环境变量。
6. 点击节点底部的“运行提示词优化”。
7. 从 `enhanced_prompt` 获取最终字符串。

可以直接把 [`example/minimax_h3_prompt_enhancer_example.json`](./example/minimax_h3_prompt_enhancer_example.json) 拖入 ComfyUI。示例工作流不包含 API Key。

## Seedance 2.0 快速使用

1. 添加 `Seedance 2.0 Prompt Enhancer (Seedance / OpenAI)`。
2. 填写“视频创意 / 提示词”。任务意图、组织方式、时长和镜头数都可先保持 `AUTO`。
3. 按任务连接首帧、尾帧、参考图片或完整参考视频。
4. 选择官方中文 `@图片N/@视频N` 或 Seedance.nz 英文 `@Image N/@Video N` 引用格式。
5. 填写的是“提示词增强 LLM API Key”，保存后点击节点底部运行按钮。
6. 把 `enhanced_prompt` 连接到下游 Seedance 2.0 视频节点的提示词输入。

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

Seedance 2.0 目标视频模型能够处理音频，不代表本项目固定使用的提示词增强 LLM 能分析音频文件。2026-08-05 的真实能力探测中，`bytedance/doubao-seed-evolving` 明确拒绝 OpenAI 兼容 `input_audio`，返回“audio input is not supported by this model”。因此新节点没有 `AUDIO` 输入，也不会声称听过上传音频。

用户仍可在文字里描述对白、环境声、动作声、音乐和音色，或保留文字形式的 `@音频N/@Audio N` 意图；这些内容只作为文字理解。探测结论的脱敏记录位于 [`tests/fixtures/seedance20_audio_probe_2026-08-05.txt`](./tests/fixtures/seedance20_audio_probe_2026-08-05.txt)。

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
硬性要求 > 用户主提示词与媒体事实 > MiniMax-H3 核心规则 > 创意预设 > 参考模板
```

## MiniMax-H3 官方 Skill 协议

| 选项 | 行为 |
| --- | --- |
| `现有兼容（保留中英文）` | 默认值；保留现有中文 / English 正文体验，同时使用新版结构、说话人、声音和 Ref2VA 素材角色规则 |
| `官方 Skill 严格（全英文协议）` | 所有说明字段和描述正文强制使用英文；仅用户原始对白、歌词、品牌/UI 文案和画面可见文字保留原语言 |

严格档位优先于“输出语言”选择。例如同时选择“中文”和“官方 Skill 严格”，实际说明正文仍为英文。这样不会静默改变旧工作流，新节点也继续默认中文兼容模式。Ref2VA 生成类任务在严格档位下默认以约 350–500 English words 作为软目标；未达到目标字数仍不是节点错误。

新版核心规则还包括：按目标视频首次真实发声顺序分配 `(S1)`，多人同声使用 `(S1,S2)`，跨切镜对白在两侧使用 `<scenetrans>`，只在片尾截断时使用 `<cutoff>`；Ref2VA 严格区分 Subject、Picture、Video 的实际角色，普通视频内声音不会被伪装成独立 Audio 素材。

## MiniMax-H3 创意预设

| 预设 | 主要强化内容 |
| --- | --- |
| `无（仅核心规则）` | 不附加场景风格规则 |
| `AUTO（根据意图判断）` | 意图明确时最多选择一个匹配预设，否则只用核心规则 |
| `极简产品广告` | 产品身份、材质、负空间、单节拍主动作、稳定闭幕和品牌事实安全 |
| `3D 动画短片` | 角色/场景连续性、可读轮廓、动作预备与跟随、单镜重要角色控制 |
| `品牌宣传短片` | 可核验品牌事实、精确文案、安全空间和具体功能证明 |
| `MV / 歌词贴字` | 歌词原文、口型/表演、空间文字层级和文本已知节拍；不假装分析音频附件 |
| `双人合作游戏开场` | 双人身份与左右位置、玩家名、UI 文案、按钮层级和颜色控制 |
| `纸拼贴讲解` | 半调纸片、视觉隐喻、停格组装动作和触感音效 |
| `立体纸艺停格讲解` | 分层纸景、折叠/弹起/翻页/纸偶动作、材料与景深连续性 |
| `手绘实拍融合` | 实拍接触、同一实体连续变形、慢半拍追拍、粗糙发光笔触和非恐怖基调 |

这些选项只把官方场景 Skill 中适合“单次 H3 提示词改写”的规则传给 LLM。节点不会安装远程 Skill、生成角色卡或锚点图、研究官网、分析音频文件、调用 H3 视频生成、拼接片段或执行交付流程。

### MV / 歌词贴字填写方式

选择 `MV / 歌词贴字` 后，主提示词会显示一份动态填写提示；它只是界面占位文字，不会写入工作流或自动成为提示词。可以直接按下面的结构填写，未涉及的项目留空：

```text
MV类型/视觉风格：暗色抒情 MV，低饱和蓝黑色，空间歌词排版
歌词原文（逐字保留，可空）：夜色落在我肩上，别回头。
演唱者或离屏人声：画内女歌手演唱
已知 BPM、时间点或节拍事件（可空）：00:04.200 鼓点进入，00:09.000 drop
字体包装与禁止项：文字在中景展开，不遮挡眼睛和关键口型
```

MV 规则按以下方式工作：

- 用户提供的歌词是唯一歌词来源，保持原语言、标点、顺序和重复，不翻译、不润色、不补写；没有歌词时不会自动创建歌词、歌手或口型。
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
| `official_skill_profile` | `现有兼容 / 官方 Skill 严格`；默认兼容，严格档位强制英文说明正文 |
| `creative_preset` | `无 / AUTO / 8 个官方场景写作预设` |
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

两个节点中的 Key 都用于 `bytedance/doubao-seed-evolving` 提示词增强请求，不是下游 Seedance 2.0 视频生成 API Key。

### 贞贞平价小屋（推荐）

聊天与素材上传地址固定为：

```text
https://api.seedance.nz
```

可以在节点底部填写 API Key，或点击[获取贞贞 API Key](https://api.seedance.nz/sign-up?aff=5f4w)。节点中的 Key 留空时读取环境变量 `SEEDANCE_API_KEY`。

PowerShell：

```powershell
$env:SEEDANCE_API_KEY="你的 API Key"
```

Linux / macOS：

```bash
export SEEDANCE_API_KEY="你的 API Key"
```

### OpenAI 兼容接口（备用）

备用模式支持服务根地址、以 `/v1` 结尾的地址，或完整 `/chat/completions` 地址。节点 Key 留空时读取 `OPENAI_API_KEY`，Base URL 留空时读取 `OPENAI_BASE_URL`。

OpenAI Chat Completions 兼容并不自动代表支持图片和视频上传：

- T2VA 只要求兼容聊天端点。
- 图像或视频任务必须配置 `openai_upload_url`，或设置 `OPENAI_MEDIA_UPLOAD_URL`。
- 上传端点必须接收 multipart 字段 `file`。
- 上传响应必须包含可公开访问的 HTTP(S) `url`。

缺少媒体上传合同会在联网前报错，不会悄悄降级成纯文字或抽帧请求。

## API Key 安全

节点底部提供遮罩、显示、保存和清空按钮。遮罩只能避免画布上直接显示明文：点击“保存到工作流”后，Key 会进入工作流 JSON。

- 分享工作流前务必点击“清空”。
- 更安全的方式是把节点 Key 留空并使用环境变量。
- 节点不会把 Key、请求正文、素材 URL 或响应正文写入日志。
- 仓库示例和测试不包含真实 API Key。

## 图片与视频处理

- 图片编码为 PNG 后上传。
- 视频使用 ComfyUI 原生 `VIDEO` 的完整流，不抽帧、不转成图片列表。
- 支持 MP4、AVI、MOV、MKV，单文件不超过 50 MB。
- Ref2VA 单个视频时长 2–15 秒，多个视频总时长不超过 15 秒。
- Ref2VA 最多 9 张图片、3 个视频，总素材数最多 12。
- 带活动裁剪窗口的原生 `VIDEO` 会在上传前被拒绝，因为底层流可能仍指向未裁剪原文件。请先把片段另存为新视频再连接。
- 素材上传 URL 是临时链接，应只用于当前模型请求。

## 输出与错误行为

输出只有：

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

以下情况仍会报错：

- API Key 无效或余额不足；
- 网络、超时、限流或供应商 5xx；
- 图片或视频上传失败；
- 响应不是合法 JSON；
- 响应缺少正文或正文全空白。

付费聊天请求不会自动重试，避免超时后重复计费。免费素材上传遇到 429 时最多重试一次。

## 测试

在 ComfyUI 根目录的上一级运行：

```powershell
.\python\python.exe -m unittest discover -s ComfyUI\custom_nodes\comfyui-minimax-h3-prompt-enhancer-T8\tests -v
```

单元测试使用 mock API 和本地媒体夹具，不联网、不上传素材、不产生费用。

`live_smoke.py` 用于 MiniMax-H3；`seedance20_live_smoke.py` 用于 Seedance 2.0。两者都会生成本地图片和 4 秒 MP4，对图片事实、视频时间顺序和跨素材关系做真实联合测试。它会产生实际 Token 费用，只有明确接受费用时才运行：

```powershell
.\python\python.exe ComfyUI\custom_nodes\comfyui-minimax-h3-prompt-enhancer-T8\live_smoke.py --confirm-paid
.\python\python.exe ComfyUI\custom_nodes\comfyui-minimax-h3-prompt-enhancer-T8\seedance20_live_smoke.py --confirm-paid
```

运行前必须设置 `SEEDANCE_API_KEY`。不要把真实 Key 写进命令参数、脚本或工作流后上传到公开仓库。

## 参考资料

- [MiniMax-H3 基础提示词指南](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_base_en.md)
- [MiniMax-H3 完整参考模式指南](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_ref_en.md)
- [MiniMax-H3 官方 Skills 目录](https://github.com/MiniMax-AI/MiniMax-H3/tree/093f3129a3f7bd27c74928b1cd31a54fbdebe057/skills)
- [MiniMax-H3 官方核心 Prompt Writing Skill](https://github.com/MiniMax-AI/MiniMax-H3/blob/093f3129a3f7bd27c74928b1cd31a54fbdebe057/skills/h3-prompt-writing/SKILL.md)
- [Seedance API 文档](https://api.seedance.nz/docs/llms.txt)
- [Seedance 模型页面](https://api.seedance.nz/pricing/bytedance%2Fdoubao-seed-evolving)
- [Seedance 2.0 官方模型页](https://seed.bytedance.com/en/seedance2_0)
- [Seedance 2.0 官方 Prompt Optimizer Skill](https://arkdocs.tos-cn-beijing.volces.com/files/video-generation/SKILL.md)

## 说明

本项目是第三方 ComfyUI 自定义节点，不隶属于 MiniMax、ByteDance、Seedance 或 ComfyUI 官方。API 能力、价格和可用性以服务商最新说明为准。使用真人参考素材时，用户仍需自行确认身份授权和下游平台规则。
