# 定向创作 Skill / Directional creation Skills

H3 与 Seedance 2.0 提示词增强节点新增一个 **定向创作 Skill（T8，非官方）** 下拉项。新建节点默认关闭；不需要新节点或额外连线。这三种方法帮助编排动作，不生成视频，也不替换平台格式。

更新插件后重启 ComfyUI 并强制刷新浏览器，再使用新下拉项。旧工作流加载时只补上关闭状态，不改变原来的模型、种子、时长和输出连线。

The existing H3 and Seedance 2.0 enhancers have one optional **Directional Skill** selector, off by default. These independently adapted, non-official methods guide choreography, not video generation or output syntax. No extra node or wiring is required.

Restart ComfyUI and hard-refresh the browser after updating. Historical workflows gain only the default Off selection; saved models, seeds, duration and output wiring stay intact.

## 选哪个 / Choose a method

| 技能 / Skill | 用途与简短输入 / Purpose and sample input |
| --- | --- |
| 连续战斗长镜头 / Continuous combat | 连续摄影路径与动作状态承接。例：双剑客走廊交锋，12秒，一镜到底。 / Continuous camera and action continuity. Example: two swordfighters duel along a corridor, 12 seconds, one take. |
| 高密度连续攻防 / High-density combat | 让攻击、回应、位移与下一动作互相衔接。例：两名成年练习者徒手攻防8秒，不停下来摆姿势，不强定胜负。 / Linked attacks, responses and displacement. Example: an 8-second unarmed practice duel, no posing or forced winner. |
| 电影枪战导演 / Cinematic gunfight | 围绕虚构场面的目标、空间变化与人物回应展开；不是枪械操作教学。例：雨夜车站，枪声与碎玻璃迫使两名同伴改变撤离路线。 / Fictional dramatic goals, space and reactions, not firearm instructions. Example: gunfire and breaking glass force two companions to change their escape route at a rainy station. |

直接写人物、场景、动作目标、时长和必须保留的条件即可；不需要填写资产表或模仿来源示例。技能不会自动添加对手、武器、超能力、BUNNY/LoRA 触发词或双语成稿。输出语言仍由原来的语言选项控制。

Describe the participants, setting, goal, duration and constraints. No asset table is required. The Skill does not automatically add opponents, weapons, powers, BUNNY/LoRA triggers or two language drafts. The existing language selector still controls the output.

## 怎么运行 / Run an example

三个示例各有 H3、Seedance 两条并列分支，使用相同中文输入、同一种技能和现有贞贞渠道，分别显示两平台的原生提示词：

Each example runs the same idea through H3 and Seedance using the existing Zhenzhen cloud provider and displays each platform's native prompt:

- [连续战斗长镜头 / Continuous combat](../example_workflows/directional_continuous_combat_comparison.json)
- [高密度连续攻防 / High-density combat](../example_workflows/directional_high_density_combat_comparison.json)
- [电影枪战导演 / Cinematic gunfight](../example_workflows/directional_cinematic_gunfight_comparison.json)

1. 把 JSON 拖入 ComfyUI，在左侧 `T8 Prompt Text` 填入自己的 API Key；示例不含密钥。 / Drag the JSON into ComfyUI and enter your own API key in the left `T8 Prompt Text` node; no credentials are included.
2. 两分支可分别改写输入；完整运行会执行两个增强请求，按渠道实际计费。只比较一种平台时，用该节点自己的运行按钮。 / Running the whole graph invokes both enhancers and incurs the provider's normal charges. Use one enhancer's run button to test only that branch.
3. 右侧两份结果采用各自平台格式，不应逐行相同。这是跨平台示例，不是开/关盲测或效果保证。 / Outputs use different native formats; this is not an on/off benchmark or a quality guarantee.
4. 分享工作流前清空 Key。示例默认为云端，不下载、不加载本地模型。 / Clear the key before sharing. These cloud examples neither download nor load local models.

需要改用本地 GGUF 或其他 API 时，使用原有渠道设置或连接 `共享 LLM 渠道配置`；共享配置仍覆盖节点的渠道字段。本地模式请手动选择自己已安装的模型；示例隐藏字段的 9B 文件名仅作占位，不代表该模型已经安装或经过本次效果验收。

To use local GGUF or another API, use the existing provider controls or shared provider config, which retains its override priority. Choose an installed model manually for local execution. The examples' inactive 9B field is a placeholder, not a bundled or quality-certified model.

## 优先级与兼容 / Priority and compatibility

- 开启时，仅当前请求暂停旧 T8 案例、手动模板的动作编排，以及 H3 可选官方场景；界面保留原值，关闭后恢复。用户明确要求保留的模板事实仍按原要求处理，不能借此继承整份旧模板。 / For this request, the selected Skill replaces optional T8 case/manual-template choreography and H3 scene presets. Saved selections remain intact and resume when switched off. Explicitly requested template facts are not permission to inherit the whole old template.
- H3 官方核心、当前模式格式、素材角色、原文对白、语言、时长和硬性约束仍然优先；Seedance 保留自己的原生格式，不套 H3 字段或时间码。角色圣经和表演导演只协调已有角色，不凭空加人或把每次受击变成停顿。 / The platform core, media roles, exact dialogue, language, duration and hard constraints remain authoritative. Seedance does not inherit H3 fields or timing syntax. Character Bible and performance guidance coordinate existing characters without inventing people or requiring stops.
- **连续战斗长镜头：镜头数 AUTO 会按 1 镜处理；明确选择 2 镜或更多，会在上传素材/付费调用前报错。** 改成 `1 / AUTO`，或换另一技能；动作阶段、Relay 事件不等于切镜。来源的“30秒”不是固定限制。 / **Continuous combat resolves AUTO to one shot and rejects an explicit count of two or more before upload/paid calls.** Choose 1/AUTO or another Skill. Action beats and Relay events are not cuts; 30 seconds is not imposed.
- 技能本身不新增规划或评分 LLM 请求；原有语言纠正、Relay 格式修复、传输重试仍可能发生，并保留本次创作约束。恢复上次结果不会按新选技能重新生成；先检查恢复结果的来源信息。 / The Skill adds no planning/scoring call. Existing bounded language/Relay repairs and transport retries may still run. Recovering a previous result does not regenerate it with the newly selected Skill; inspect its recorded source.
- 默认关闭保留旧行为、节点 ID 和输出。H3 普通模式仍使用第一个输出，六个输出的用途不变；Seedance 仍输出自己的增强提示词。Relay 下游视频执行效果需单独实测，不能仅凭提示词结构宣称成片效果。 / Off preserves legacy behavior, node IDs and outputs. H3 keeps all six output roles and its normal first output; Seedance keeps its native prompt output. Downstream Relay video quality requires separate execution tests.

## 更新与检查 / Maintenance

这三种技能是插件内置文本资源，随插件代码更新；不在每日案例交接或 GIF 动态资源包中。未知技能 ID 会要求重新选择，不会静默改用其他技能。资源缺失时请更新或重装插件，或者明确选“关闭”。

These bundled text resources update with the plugin, independently of daily case imports and GIF packages. Unknown IDs require an explicit selection rather than silently switching methods. If resources are missing, update/reinstall the plugin or explicitly select Off.

编排约束不等于模型输出保证。真实 API 抽测也发现过 H3 说话人标签全角化，以及把“仍朝出口移动”提前写成“已到出口外”；复杂任务请检查协议、原文对白、人物/道具归属和尾态，不能只凭输出成功或总分判断合格。

Directing constraints are not output guarantees. Real API samples also included fullwidth H3 speaker IDs and an ending advanced from moving toward an exit to already outside. Check protocol syntax, exact speech, actor/prop ownership and final state; successful execution or a total score alone is not acceptance.

本地小参数模型也会收到完整创作参数，但这不等于它一定遵守所有要求。本次 9B 抽测出现过对白标记错误、门的开闭状态被改写、动态护送变成静态对峙。复杂人物/道具/尾态任务建议使用 API 或更高参数模型，并逐项检查原文对白、持有关系和结尾状态；不要把输出成功当作质量合格。

Small local models receive the complete creation settings, but may still violate them. Exploratory 9B tests included incorrect speech markup, changed door state and a moving escort reduced to a static standoff. Prefer an API or larger model for complex actor/prop/end-state constraints and check exact speech, possession and the ending. Successful execution alone is not quality acceptance.

可把结果接到 `T8 Prompt Inspector` 做不改原文、不调用 API 的格式检查；H3 的 `(S1)` 与 `<d>[Chinese] 原句</d>` 是协议，不能本地化为全角括号或 `[中文]`。Seedance 中文对白采用自己的 `{}`，不要套 H3 标签。Inspector 的结构分不是创作质量或成片分数。

Connect the result to `T8 Prompt Inspector` for a non-mutating, local format check. H3's ASCII `(S1)` and `<d>[Chinese] exact line</d>` are protocol syntax, not localized fullwidth IDs or `[中文]`. Seedance Chinese speech keeps its own `{}` policy. The Inspector's structural score is not creative or video quality.

维护者可运行 `python tools/build_directional_skill_workflows.py --check` 校验三份新示例。`python tools/build_example_workflows.py --check` 仍检查原18份工作流与缩略图，并额外检查这三份示例；不会调用模型。

Maintainers can run `python tools/build_directional_skill_workflows.py --check`. The existing example checker also validates these three additions while preserving all checks on the original 18 workflows and their thumbnails. Neither command invokes a model.
