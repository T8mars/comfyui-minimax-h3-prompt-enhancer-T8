# ComfyUI MiniMax-H3 Prompt Enhancer T8

一个面向 MiniMax-H3 视频生成的 ComfyUI 提示词增强节点。节点固定调用 `bytedance/doubao-seed-evolving`，能够把用户文字与真实 `IMAGE` / `VIDEO` 素材放进同一次多模态请求，输出可连接下游节点的 `STRING`。

支持 T2VA、I2VA、FL2VA、L2VA、Ref2VA，默认输出中文，也可切换 English；同时提供严格、平衡、创意三档改写，以及官方增强和参考模板融合两种提示词模式。

## 功能特点

- 固定视觉模型 `bytedance/doubao-seed-evolving`，没有纯文本模型回退。
- 同时分析文字、图片和完整视频，不用抽帧冒充视频理解。
- 支持首帧、尾帧、首尾帧以及多图、多视频参考。
- 集成 MiniMax-H3 官方基础与完整参考提示词规则。
- 支持中文 / English 输出。
- 支持 `strict / balanced / creative` 三档改写。
- 支持 `AUTO` 或固定 1–20 个镜头的下拉控制。
- 支持用户参考模板融合，主提示词与可观察媒体事实优先。
- 提供随机种子以及 `fixed / randomize / increment / decrement` 状态。
- 提供节点内 API Key 输入、遮罩显示、保存、清空和注册链接。
- 支持贞贞平价小屋固定接口和显式配置的 OpenAI 兼容备用接口。
- 输出单一 `STRING`，可直接连接下游提示词输入。

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

在节点菜单中搜索：

```text
MiniMax H3 Prompt Enhancer (Seedance / OpenAI)
```

## 快速使用

1. 添加 `MiniMax H3 Prompt Enhancer (Seedance / OpenAI)`。
2. 在“视频创意 / 提示词”中输入基础意图。
3. 选择生成类型、时长、镜头数量、改写模式和输出语言。
4. I2VA / FL2VA / L2VA / Ref2VA 按任务要求连接图片或视频。
5. 填写 API Key，点击“保存到工作流”；或者使用环境变量。
6. 点击节点底部的“运行提示词优化”。
7. 从 `enhanced_prompt` 获取最终字符串。

可以直接把 [`example/minimax_h3_prompt_enhancer_example.json`](./example/minimax_h3_prompt_enhancer_example.json) 拖入 ComfyUI。示例工作流不包含 API Key。

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
硬性要求 > 用户主提示词与媒体事实 > MiniMax-H3 规则 > 参考模板
```

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

唯一的本地整理规则：

1. 当前任务的全部预期字段均以精确字段名命中；
2. 每个字段只出现一次；
3. 字段顺序确实错误。

三个条件同时成立时按官方顺序重排；任何字段未命中、缺失、重复，或者本来就是正确顺序时，保持上游原文。

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

`live_smoke.py` 会生成本地图片和 4 秒 MP4，对图片事实、视频时间顺序和跨素材关系做真实联合测试。它会产生实际 Token 费用，只有明确接受费用时才运行：

```powershell
.\python\python.exe ComfyUI\custom_nodes\comfyui-minimax-h3-prompt-enhancer-T8\live_smoke.py --confirm-paid
```

运行前必须设置 `SEEDANCE_API_KEY`。不要把真实 Key 写进命令参数、脚本或工作流后上传到公开仓库。

## 参考资料

- [MiniMax-H3 基础提示词指南](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_base_en.md)
- [MiniMax-H3 完整参考模式指南](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/docs/VIDEO_PROMPT_WRITING_GUIDE_ref_en.md)
- [Seedance API 文档](https://api.seedance.nz/docs/llms.txt)
- [Seedance 模型页面](https://api.seedance.nz/pricing/bytedance%2Fdoubao-seed-evolving)

## 说明

本项目是第三方 ComfyUI 自定义节点，不隶属于 MiniMax、ByteDance、Seedance 或 ComfyUI 官方。API 能力、价格和可用性以服务商最新说明为准。
