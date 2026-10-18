# 独立分镜强化 / Experimental storyboard direction

这是可选的分镜方法，不是新模型，也不是独立的生成服务。仅接入 **MiniMax H3 / Seedance 2.0**；不接入 MOSS Image，MOSS 的问题修复与本功能无关。默认关闭，是否有正收益尚未通过真实模型/视频对照验证。

## 使用

1. 添加 `T8 Storyboard Director Config（分镜强化·实验）`（`T8/Utilities`）。
2. 将输出接到 H3 或 Seedance 的 `storyboard_director_config`，也可一份配置连接两者。
3. 需要时选择 `开启（实验） / On (experimental)`。未连接或 `关闭 / Off` 保持旧路径；不影响原表演配置未连接时的 AUTO。
4. 沿用原来的提示词、模型渠道、素材、导演、情感演绎和输出连接。不要把本配置接到 MOSS、Music、Storyboard Pack 或 LongForm。

只增加一个连接口，不增加 H3/Seedance 的可保存控件：原有 38 项数组和输出顺序不变。新配置只有一个原生模式下拉；重启/重新加载插件后才能看到新节点。不需读取原始 Markdown 的本机路径。

## 方法与边界

方法关注源事件由哪个画面/声音承载、观众和角色的知情先后、接触/交接可读性、世界位置与画面左右的区分，以及动作、持有物、速度和声音的跨镜承接。同一事件可以跨几个镜头继续，但不能重复完成。安静、无人、无变化、已完整分镜都允许保持原样，不要求强加冲突或切镜。

用户锁定事实、镜数、一镜到底、对白/说话者、等待时间、首尾状态和素材角色优先。既有导演负责场面策略，表演/Bible 负责演绎，本方法协助信息呈现。它不自动改变原有模板选择或关闭其他方法，也不加入“必须 CG／无配乐／无字幕”等全局默认。

**不新增任何时长上限，不截短，不自动拆片或分组。** 60、120、3600 秒均可原样进入当前增强合同；这些测试值不是推荐上限。下游视频平台本身是否支持、一次上下文能否容纳、语速和动作是否可实现，是独立问题；文本时序估算不是实测同步。

H3 保持当前任务的三/六字段、Hybrid 角色和 Relay 格式；Seedance 保持当前 2.0 合同，不混入 H3 标签或绝对分镜时间码。源文件名称含 2.5 不代表已升级现有节点。Storyboard Pack / LongForm / Relay 数据结构不变；完整事件 IR、生成段映射及专用 2.5 profile 不在本期。

## 调用、恢复与隐私

配置节点纯本地，启用后将紧凑方法并入原有第一条生成请求，不新增规划、评分或修复循环。输入 token/延迟可能增加；原有语言、质量、语音、Relay 修复及传输重试仍可能产生后续请求，不能把“无额外规划”理解为总共永远一次请求。

本地 GGUF 的预算估计和实际请求、三种云端渠道、现有 Strata 桥接均使用同一可选策略。语言修复仅凭已开启的配置保留分镜策略，不根据故事/Bible 中的文字标记启用；带语音参考时同一证据块只保留一次，不重新上传媒体。错误配置在生成/新缓存检查点前报错并保留旧缓存；正式开始新请求后若失败，沿用现有缓存语义，不保证回退到旧成功稿。

成功结果记录有限的 `storyboard_strategy=v20_storyboard` 和 `storyboard_revision=1.0.0`。恢复按钮显示原结果的策略；恢复的是原稿，不按当前开关重新生成，并跳过新的 lazy 分镜依赖。记录策略不代表质量验收通过；重启清空内存缓存等旧限制仍在。

只采用独立选取和表述的方法；不分发用户源文、原示例或本机路径，不在运行时加载该文件。来源 SHA256、许可观察与排除项见 [source lock](../research_sources/storyboard-v20.lock.json)。本方法非官方，不承诺模型遵从或视频改进。

## 独立对照示例

- [H3 Off / On](../example_workflows/storyboard_director_h3_comparison.json)
- [Seedance Off / On](../example_workflows/storyboard_director_seedance20_comparison.json)

两份示例各有两条同输入、同设置分支，只在分镜配置 Off/On 上不同。API Key 均为空；完整排队会执行两次基础增强，原有必要修复另计。只想用单分支时断开另一结果节点或只排所需输出。示例是接线演示，不是已取得正收益的样片。

## A/B 验收协议

先固定实际模型版本、provider、seed/temperature、输出语言、同一输入及媒体哈希、导演、表演、质量和修复设置。先保持表演 AUTO 比较分镜 Off/On；如要研究情感交互，再独立登记“分镜 × 情感”2×2试验，不混进第一组。

离线工具 `tools/storyboard_ab.py`（完整 GitHub 安装的开发工具，不进入 Registry 包）准备 8 类 × 2 模型目标 × 2 开关的 32 槽计划：静景、一次交接、延迟揭示、跨镜对白、产品锁镜、左右反转、超长单镜、运动结尾。`--repeats` 只控制测评重复，不限制片长。

```powershell
python tools/storyboard_ab.py plan --model "实际模型版本" --provider "实际渠道" --output-dir "D:/storyboard-evidence/plan-001"
python tools/storyboard_ab.py blind --manifest "D:/storyboard-evidence/plan-001/manifest.json" --observations "D:/storyboard-evidence/plan-001/observations.json" --output-dir "D:/storyboard-evidence/blind-001"
```

计划命令不调用模型；所有槽初始为 pending。实际执行需要另行确认成本和数据权限；交错/平衡 Off、On 顺序。按槽登记捕获的输出、`digest(output)` 哈希（工具中规范 JSON 序列化 SHA256）、结果、实际调用/HTTP尝试数与耗时；失败、截断、中断必须保留。修改共同设置应另存新计划，不能默默改写旧实验。

盲评工具拒绝空实验、遗漏、重复、不配对、输入/设置变更、输出哈希不符以及 pending；调用/HTTP 尝试数和已知 token 数须为非负整数，耗时/成本可为有限非负小数。本地生成允许 HTTP 尝试数为 0，未知 token/成本保持 null。哈希只校验登记数据的一致性，不证明执行时真实使用了这些设置，仍须保存实际请求证据。

工具不添加开关标签，并生成独立私密映射。同一对的 `focus` 评审说明必须是相同文本，不能写入某一臂专属提示。工具原样保留模型输出；如果输出自行提到所用方法，或人工输入含臂标签，评审仍可能猜到分组，因此不是绝对盲法保证，应记录这种泄露而非篡改输出。评审只看候选，逐条引用输出证据标记 pass/fail/unknown；硬合同失败不能用风格分抵消。封存判断后解盲，按同例同重复比较：硬违规率、失败率、信息效率/可读性/连续性/简洁性，以及 token、耗时和成本。更长提示词、更多镜头或命中关键词不是改进指标。

文本合同通过后，再在另外授权的同素材/同视频模型设置下比较渲染；模型版本、素材数量、样本量和不确定性必须明确。小样本、单模型或只测文本不能推广为普遍正收益。

## Engineering scope (English)

An independent, default-Off custom-type config for H3 and Seedance only; **no MOSS integration**. None/Off preserves old messages, defaults, widgets and output ports. On adds independently worded v20 directing advice to the existing first request, retaining native grammar, source locks, other directors and acting. No added duration cap, deliberate shortening of the target duration, auto-split, extra planner or new repair loop. Existing context and output-token limits still apply; increased input tokens and existing corrections still cost resources.

Recovery restores the original cached result and its finite method revision, not the current switch. Source text is not redistributed. Current Seedance 2.0 is not silently upgraded to 2.5. The paired examples and offline manifest/blinding tool support evaluation; software contracts and loopback queues do not establish model compliance or rendered benefit.

Follow-up local engineering acceptance (2026-10-18): 1,063 Python tests (1,061 passed, two existing opt-in skips), including 32 storyboard/A-B tests and missing-package-file checks; 93 frontend tests and Chrome extension contracts passed. Eleven owned CPU queue cases include four expected failures; responses came only from a loopback fixture (six completions per run). Native Comfy save/reload/reconnect checks now compare all 38 saved values on freshly reloaded nodes, alongside API values and stable heights. Current and minimum ComfyUI 0.33 candidate-package loading is checked separately. No paid LLM evaluation, real GGUF generation, rendered-video A/B or RunningHub deployment is claimed. Passing these checks does not prove the absence of all bugs.
