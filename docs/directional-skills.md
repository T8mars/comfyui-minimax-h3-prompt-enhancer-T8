# 定向创作 Skill / Directional creation Skills

H3 与 Seedance 2.0 提示词增强节点提供一个 **定向创作 Skill（T8，非官方）** 下拉项。新建节点默认关闭；不需要新节点或额外连线。八种方法帮助编排场景，不生成视频，也不替换平台格式。

更新插件后重启 ComfyUI 并强制刷新浏览器，再使用新下拉项。旧工作流加载时只补上关闭状态，不改变原来的模型、种子、时长和输出连线。

The existing H3 and Seedance 2.0 enhancers have one optional **Directional Skill** selector, off by default. These independently adapted, non-official methods guide choreography, not video generation or output syntax. No extra node or wiring is required.

Restart ComfyUI and hard-refresh the browser after updating. Historical workflows gain only the default Off selection; saved models, seeds, duration and output wiring stay intact.

## 选哪个 / Choose a method

| 技能 / Skill | 用途与简短输入 / Purpose and sample input |
| --- | --- |
| Fisher-连续战斗长镜头 / Continuous combat | 连续摄影路径与动作状态承接。例：双剑客走廊交锋，12秒，一镜到底。 / Continuous camera and action continuity. Example: two swordfighters duel along a corridor, 12 seconds, one take. |
| 土豆-高密度连续攻防 / High-density combat | 让攻击、回应、位移与下一动作互相衔接。例：两名成年练习者徒手攻防8秒，不停下来摆姿势，不强定胜负。 / Linked attacks, responses and displacement. Example: an 8-second unarmed practice duel, no posing or forced winner. |
| 兔子-电影枪战导演 / Cinematic gunfight | 围绕虚构场面的目标、空间变化与人物回应展开；不是枪械操作教学。例：雨夜车站，枪声与碎玻璃迫使两名同伴改变撤离路线。 / Fictional dramatic goals, space and reactions, not firearm instructions. Example: gunfire and breaking glass force two companions to change their escape route at a rainy station. |
| 宁版-文武双全 / Ning · Drama & Action | 围绕关键变化选择观看重点：文戏的信息接收，武戏的发力/受力与距离，文武衔接。 / Choose attention around meaningful information, reactions, force and distance, including dialogue leading into action. |
| 戏剧场面｜关系与潜台词 / Dramatic scene | 目标、说话意图、接收与关系，用现有动作表达，不强加隐情。例：主管劝再想一天，职员持信回答已经想好；去留未决。 / Goals, speech intent, reception and relationship through supported behavior, without invented secrets. Example: a resignation conversation ends unresolved. |
| 情境戏剧｜处境与铺垫回收 / Situational drama | 处境、期待与回应的可见关系；可有趣，也可和平、静默或未解决。例：两人搬桌短暂错拍后协调，桌停在门内。 / Visible situation, expectation and response; comedy, peace, silence and unresolved outcomes are all valid. Example: two people coordinate a table move after one brief mismatch. |
| 贞贞-POV剧情导演 / Zhenzhen POV | 视点归属、观众参与、信息接收及动作结果。例：朋友等观看者指向桌左，再把空白卡片放到所指位置。 / Viewpoint, participation, reception and consequence. Example: a friend waits for the viewer to point left before placing a blank card there. |
| Jojocodex-武术打斗 / Wushu combat | 身体发力、攻防回应、支撑与下一动作接口，跨镜继承。例：掌推被避开，顺势低扫，对方抬腿避让后站稳。 / Body drive, response, support and next-action continuity. Example: evade a palm push, sweep, then evade and regain support. |

直接写人物、场景、动作目标、时长和必须保留的条件即可；不需要填写资产表或模仿来源示例。技能不会自动添加对手、武器、超能力、BUNNY/LoRA 触发词或双语成稿。输出语言仍由原来的语言选项控制。

Fisher-、土豆-、兔子-为用户指定的作者署名前缀，仅改变显示名称；技能ID和创作方法不变。旧工作流保存的无前缀名称仍可读取，重存后使用原来的稳定ID。

The Fisher-, 土豆- and 兔子- prefixes are user-requested author credits, not new methods. Stable IDs remain unchanged; historical unprefixed labels are still accepted.

Describe the participants, setting, goal, duration and constraints. No asset table is required. The Skill does not automatically add opponents, weapons, powers, BUNNY/LoRA triggers or two language drafts. The existing language selector still controls the output.

## 怎么运行 / Run an example

四个示例各有 H3、Seedance 两条并列分支，使用相同中文输入、同一种技能和现有贞贞渠道，分别显示两平台的原生提示词：

Each example runs the same idea through H3 and Seedance using the existing Zhenzhen cloud provider and displays each platform's native prompt:

- [Fisher-连续战斗长镜头 / Continuous combat](../example_workflows/directional_continuous_combat_comparison.json)
- [土豆-高密度连续攻防 / High-density combat](../example_workflows/directional_high_density_combat_comparison.json)
- [兔子-电影枪战导演 / Cinematic gunfight](../example_workflows/directional_cinematic_gunfight_comparison.json)
- [宁版-文武双全 / Ning Drama & Action](../example_workflows/directional_ning_wenwu_comparison.json)

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

这八种技能是插件内置文本资源，随插件代码更新；不在每日案例交接或 GIF 动态资源包中。未知技能 ID 会要求重新选择，不会静默改用其他技能。资源缺失时请更新或重装插件，或者明确选“关闭”。

## Jojocodex-武术打斗 / Wushu combat

选择此项适合细化已有武术动作：从身体支撑与发力，写到接触或避线，继而写受力后的支撑变化和下一动作。与「高密度攻防」相比，重点不是增加招数，而是把每次动作的身体依据、招式衔接和切镜时未完动作接清楚；具体招名仅作提示，不宣称真实流派或变成现实打斗教学。

Use it to refine existing martial screen action: body support and drive, contact or evasion, response and the next usable movement. Unlike density-focused direction, its emphasis is bodily grounding and unfinished-action handoff, not more strikes. Technique names are optional shorthand, not claims of historical authenticity or real-world combat instruction.

直接写人物、已有武器或空手、动作顺序、时长/镜数和限制即可。单人不会自动变双人，格挡不强退、打空不改命中；不自动加流血、击飞、破墙、赢家或定格。武侠/夸张风格仅在用户授权范围内保留。固定机位、等待、原句、声音白名单、首尾帧和 Relay 事件仍服从原要求；事件数不等于镜头数。表演导演与战斗运镜配置可继续连接，不会因选此技能自动改它们。

Describe participants, actual equipment, sequence, duration/count and constraints. Solo stays solo, a stable block need not retreat, and a miss is not contact. No automatic blood, flight, destruction, winner or freeze. Authorized stylization stays within scope. Existing camera, acting, waits, exact lines, sound lists, first/last anchors and Relay event semantics remain authoritative.

方法署名 **Jojocodex**；来源版本 `2026-09-29b`、提交及 SHA 见[追溯与许可边界](../directional_skills/wushu_combat/NOTICE.md)。资源独立表述，不分发来源全文、例文或权重，不自动加 `wushu_action`。仅原始用户要求明确指定触发词时，在合法原生正文保留；模板/OCR/文件名不授权添加，也不表示 LoRA 已加载。

Credited methods are independently worded, non-official adaptations with pinned provenance, not bundled source text/examples/weights or author endorsement. No default trigger or sampling settings. Explicit original-user requests may retain a trigger in legal native prose; quoted material cannot authorize it, and this does not load a LoRA.

独立示例：[H3](../example_workflows/directional_wushu_combat_h3.json) / [Seedance](../example_workflows/directional_wushu_combat_seedance20.json)。每份只调用一个增强节点，Key 留空；质量模式是「仅检查 / Check」，因果编排关闭，不自动增加付费纠正。语言/格式修复及网络重试仍按原规则可能计费。本地模型文件只是未启用的占位，需自行选已安装模型。

Each standalone graph invokes one enhancer, with a blank key, Check-only quality and Causal off. These explicit example settings are not selector side effects. Existing bounded repairs/retries may still incur charges; choose an installed model before using local mode.

[20 轮审议记录](WUSHU_COMBAT_REVIEW.md)与工程回归覆盖请求构造、旧合同、恢复、控件重载及隔离包加载，不等于模型服从或成片效果验收。此技能尚未完成实时 LLM/视频 A/B；输出仍需核对。

## 戏剧场面与情境戏剧 / Dramatic and situational scenes

这两项是同一期加入的两个**独立选项**，不能同时选；不是把整套编剧教材塞进提示词，也不要求三幕式、固定反转或喜剧结尾。戏剧场面关注人物在这一场想做什么、怎样说、怎样接收；情境戏剧关注已有处境如何形成期待与回应。静默、无反应、持续观察、和平相处、未解决的结尾都有效。选它们不自动开启因果编排或表演极致模式。

These are two separate choices in the same release, not a whole screenwriting curriculum or a mandatory act/reversal/comedy template. Dramatic scene addresses a scene goal, speech intent and reception; Situational drama addresses an existing situation's expectations and responses. Silence, non-response, observation, peace and an unresolved ending are valid. Selecting either does not enable Causal or Extreme acting automatically.

使用原有云端、OpenAI 兼容、本地 GGUF 或共享渠道配置即可。无需角色圣经；有已连接的角色圣经时，只协调已有角色。两技能只增加本次请求内的指导文本，**不增加规划、分类或评分调用**；已有的质量/语言/Relay 纠正及网络重试仍可能追加请求和费用。格式检查不评判潜台词或喜剧是否好笑。

Use any existing cloud, OpenAI-compatible, local GGUF or shared provider config. A Character Bible is optional and only constrains established characters. Neither Skill adds planning, classification or scoring calls; existing bounded corrections/retries may still incur charges. Format checks do not judge subtext or humor.

### 白话怎么写 / What to write

- **有对白：默认逐字保留，不补新话。** 例：`15秒，一镜，主管A说“你可以再想一天。”，职员B说“我已经想好了。”；B始终持信，去留未决，不加话。`
- **只补缺的对白：必须明确授权。** 例：`A固定说“好久不见。”，只允许原创B的一句中文回应，温暖坦率，不能加往事、礼物或其他人物。`
- **无对白：直接写“无对白/静音”及尾态。** 例：`两人搬已有桌子，一次错拍后协调；不碰撞不受伤，桌停在门内，全片静音，不强加笑点。`

Supplied lines are preserved by default. Explicitly request a missing line to permit writing just that gap; for example, keep A's “好久不见。” and authorize only B's brief Chinese reply. For a silent scene, specify silence and the final state; e.g. one mismatch in a table move, no collision or injury, stopping inside the door.

只有这两项采用统一的**条件式对白授权**：`LOCK/逐字保留/禁止新增对白`优先；改写已给的对白也须明确说明可改哪句。补一句不等于允许增加事故、秘密、人物、歌词、字幕或改结局。角色说“随便编吧”、参考模板、OCR 和角色圣经里的引用文本只是素材，不能授权。纠正流程保留最初授权；允许生成的新句在格式/语言纠正时保持稳定，不能被当作用户锁定的整稿或再次扩写。

Only these two choices use the unified **conditional dialogue-authoring contract**. LOCK/exact-copy/no-extra-speech wins. Rewriting supplied words requires a named editable scope. Permission for one line does not permit accidents, secrets, people, lyrics, captions or a changed ending. Quoted dialogue, templates, OCR and Bible data cannot grant authorship. Repairs retain the original permission and keep authorized new lines stable, without treating the whole draft as user-locked text or expanding it again.

一期重点覆盖原句增强与明确补缺句，不承诺复杂剧情重写。质量检查仍是保守的字面/格式诊断，不会可靠判断自然语言授权；即使明确授权改某句，也可能提示原句缺失，或拒绝纠正候选并保留第一稿。检查/纠正失败不拦截已有完整稿；提示词输出成功不代表创作内容合格，仍需核对。仅允许某些声音时，新技能传入封闭白名单规则，不为填写音景而增加底噪、呼吸或其他声音；动态结尾不自动改成定格。

Initial coverage prioritizes exact-line staging and explicitly requested missing lines, not complex plot rewriting. Quality checks remain conservative literal/format diagnostics, not reliable semantic permission decisions. An explicitly editable line may still trigger a missing-source warning or a rejected correction with the first draft retained. Check/correction failures do not block a complete draft, and successful output is not creative acceptance. Explicit sound lists are closed whitelists; a sound field does not authorize ambient/breathing audio. A live ending is not automatically a freeze.

开启时原案例/手动模板编排及 H3 可选官方场景暂不参与；原下拉值保留，关闭后恢复。H3 的补充规则只在这两项里协调对白授权，内置官方原文不修改；严格官方配置仍输出英文描述并保留原语言台词。Seedance 仍使用自己的镜头组织及中文对白 `{}`，不收到 H3 的字段或说话人标签。普通 H3/Relay 的输出接口不变。

Optional template/scene choreography is paused for this request, without changing saved selections. Only these two choices adapt the normalized H3 supplement for dialogue permission; the bundled official source remains untouched. Strict H3 still uses English descriptions and original-language speech. Seedance keeps native organization/`{}` speech, not H3 fields or speaker tags. Normal H3 and Relay interfaces are unchanged.

### 四份独立示例 / Four standalone examples

每份仅执行一个文本增强节点。Key 留空，默认云端，质量纠正开启、因果编排关闭；这些是示例的明确设置，不是选技能后自动改设置。本地模型文件名只占位，需选择已安装模型。

Each graph invokes one text enhancer: blank key, cloud default, explicit Repair quality and Causal off. These example settings are not automatic Skill side effects. The inactive local model filename is only a placeholder.

- 戏剧场面：[H3](../example_workflows/directional_drama_scene_h3.json) / [Seedance](../example_workflows/directional_drama_scene_seedance20.json)
- 情境戏剧：[H3](../example_workflows/directional_situational_drama_h3.json) / [Seedance](../example_workflows/directional_situational_drama_seedance20.json)

恢复上次结果仍读取历史完整稿，不重新生成；来源提示显示原技能、资源版及对白授权版，不会把新选择冒充成旧结果来源。普通运行的缓存按输入选项区分；选择另一技能应重新运行。重启 ComfyUI 后进程内恢复缓存消失。

Recovery reads the historical completed draft without regeneration and shows its recorded Skill/resource/authoring revision, not the current selection. Normal execution caches include input choices; changing the Skill changes the request. Process recovery expires on restart.

两项为基于固定上游版本的 T8 方法改编，非作者提供或背书，也非 MiniMax/Seedance 官方技能。[来源与权利边界](../directional_skills/SCREENWRITING-NOTICE.md) · [MIT 许可](../directional_skills/SCREENWRITING-LICENSE.txt)。不分发书籍、剧本、译文案例摘录；情境戏剧不是上游 sitcom Skill 的直译。方法传入不等于模型必遵守，尤其 9B 本地模型请核对对白、角色/道具、静音、等待及结尾。新增两项本地验收为参数传输/卸载替身测试，不能称为真实 9B 创作效果验收。

These are bounded, pinned T8 method adaptations, not upstream-authored/endorsed or official model Skills. No books, screenplays or translated case excerpts are bundled; Situational drama is not a literal sitcom translation. Instruction transmission does not guarantee model compliance. Check speech, actors/props, silence, waits and endings, especially with small local models. Local coverage for these additions uses transport/unload doubles, not real 9B creative generation.

## 宁版-文武双全 / Ning Drama & Action

选择“宁版-文武双全”，填写想拍的内容即可。它帮助决定关键变化让观众看谁、何时看、怎样看清。高密度攻防更侧重下一招如何接；宁版可以只把少数重要交换拍明白，也能用于没有打斗的文戏。无需连接角色圣经或表演导演才能使用；已连接的辅助配置仍按原规则协调。

Select Ning and describe your scene. It chooses what the audience should understand and how attention makes that change readable. High-density combat emphasizes linked exchanges; Ning also handles drama without a fight. Character Bible and performance controls remain optional.

[双平台工作流 / Dual-platform workflow](../example_workflows/directional_ning_wenwu_comparison.json)：默认文武混合，可把两个节点的输入替换为以下任一例。完整运行会调用两个增强节点，原有修复/重试费用另按渠道规则计算。

这份新示例明确开启原有“质量纠正”，因果编排关闭；并非选择宁版就自动改变这些设置。质量流程会局部修正定位明确的协议标点，保留原句；若仍有可检查的问题，最多追加一次LLM纠正。纠正失败仍保留已完成稿并显示诊断，不保证语义或视频效果。原三份技能示例与旧工作流的质量设置不变。

This new example explicitly enables the existing Repair quality mode and leaves Causal off; selecting Ning alone does not change those settings. Located protocol punctuation can be repaired locally without changing quoted words. Remaining checked issues may trigger at most one extra LLM correction; failures retain the completed draft and diagnostics. Semantic/rendered quality is not guaranteed; legacy examples/settings are unchanged.

- 文戏 / Drama：10秒，成年姐姐在左、妹妹在右。姐姐低声说原句“钥匙给我。”；妹妹听完才停下擦杯，仍握着右手中的钥匙，不交出。只这一句，不新增人物或台词，无字幕无配乐。 / 10 seconds: an adult sister asks for the key; the other sister finishes listening before pausing her cup-wiping task and keeps the key. Keep the single supplied line.
- 武戏 / Action：8秒，两名成年练习者各持自己的软垫短棒。甲试探点肩，乙后撤避开，继续格挡练习；不分胜负，不受伤，一个连续镜头，无对白字幕配乐。 / An 8-second padded-stick rehearsal: a probe, a retreating dodge and continued practice, one take, no injury or winner.
- 混合 / Mixed：使用工作流内原句与动作：说完“到此为止。”，来客收信，侍卫拔剑挡路但不出手；保留人物、道具和关闭的门。 / Use the workflow's exact line, letter ownership and closed door; draw the sword to block the passage without attacking.

一句话输入允许细化已有事件的执行过程；明确要求原创剧情、允许补对白时，可在实际授权范围创作。选择此技能不自动授权新增主角、秘密、武器或超能力。它不强制反打、听者反应、粒子、慢动作、黑屏或固定胜负；用户要求无反应、静音、固定镜头、等待或明确尾帧时照原约束执行。

Sparse input can gain execution detail. Explicit original-writing requests can authorize new dialogue or story detail within their constraints. The Skill alone does not authorize new principal characters, powers or outcomes. Silence, stillness, no reaction, fixed framing, waits and required final frames are valid.

H3严格官方配置继续使用英文描述、保留原语对白/歌词/可见文字；兼容配置按已有中文/English选择。Seedance使用自己的格式。宁版共用云端、OpenAI兼容接口、共享配置和本地GGUF路径；小模型收到指令不代表一定遵守，复杂场景建议检查人物、道具、原句和尾态。

H3's strict official profile keeps English descriptions and source-language speech/text; its compatibility profile follows the language selector. Seedance retains its own format. All existing provider paths receive the method; model compliance and rendered video quality require separate evaluation.

真实API对照中，宁版也出现过额外环境底噪、遗漏指定等待时长；已核对完整原要求与宁版指令确实进入请求，不是选中后没有传入。质量纠正能修部分协议，不会保证这些语义条件。复杂场景请逐项核对原句、动作先后、等待秒数、声音范围和结尾，不只看格式通过或总分。

Real API samples also included an extra ambient layer and an omitted wait duration even with the full request and Ning instruction present. Repair handles some protocol issues, not guaranteed semantic compliance. Check exact speech, action order, wait durations, permitted sounds and the ending, not just a format pass or score.

宁版为用户提供方法的独立改编，非官方。摄影策略属于提示词指导，不是帧率、参考权重或成片质量保证。恢复旧结果不会按新技能重新创作，有来源记录时仍显示原稿的技能ID。

These bundled text resources update with the plugin, independently of daily case imports and GIF packages. Unknown IDs require an explicit selection rather than silently switching methods. If resources are missing, update/reinstall the plugin or explicitly select Off.

编排约束不等于模型输出保证。真实 API 抽测也发现过 H3 说话人标签全角化，以及把“仍朝出口移动”提前写成“已到出口外”；复杂任务请检查协议、原文对白、人物/道具归属和尾态，不能只凭输出成功或总分判断合格。

Directing constraints are not output guarantees. Real API samples also included fullwidth H3 speaker IDs and an ending advanced from moving toward an exit to already outside. Check protocol syntax, exact speech, actor/prop ownership and final state; successful execution or a total score alone is not acceptance.

本地小参数模型也会收到完整创作参数，但这不等于它一定遵守所有要求。既有三技能的 9B 抽测出现过对白标记错误、门的开闭状态被改写、动态护送变成静态对峙；宁版本次只有本地传输替身回归，没有真实GGUF推理效果测试。复杂人物/道具/尾态任务建议使用 API 或更高参数模型，并逐项检查原文对白、持有关系和结尾状态；不要把输出成功当作质量合格。

Small local models receive the complete creation settings, but may still violate them. Earlier 9B tests of the original three Skills included incorrect speech markup, changed door state and a moving escort reduced to a static standoff. Ning's local path was tested with transport doubles, not real GGUF generation. Prefer an API or larger model for complex actor/prop/end-state constraints and check exact speech, possession and the ending. Successful execution alone is not quality acceptance.

可把结果接到 `T8 Prompt Inspector` 做不改原文、不调用 API 的格式检查；H3 的 `(S1)` 与 `<d>[Chinese] 原句</d>` 是协议，不能本地化为全角括号或 `[中文]`。Seedance 中文对白采用自己的 `{}`，不要套 H3 标签。Inspector 的结构分不是创作质量或成片分数。

Connect the result to `T8 Prompt Inspector` for a non-mutating, local format check. H3's ASCII `(S1)` and `<d>[Chinese] exact line</d>` are protocol syntax, not localized fullwidth IDs or `[中文]`. Seedance Chinese speech keeps its own `{}` policy. The Inspector's structural score is not creative or video quality.

维护者可运行 `python tools/build_directional_skill_workflows.py --check` 校验十份定向示例（四份双平台示例、四份戏剧独立示例和两份 POV 独立示例）。`python tools/build_example_workflows.py --check` 仍检查原18份工作流与缩略图，并额外检查这些示例；不会调用模型。

Maintainers can run `python tools/build_directional_skill_workflows.py --check` for ten directional examples: four dual-platform graphs, four drama graphs and two POV graphs. The existing checker retains all checks on the original 18 workflows and thumbnails. Neither command invokes a model.

## 贞贞-POV剧情导演 / Zhenzhen POV

在原 H3 或 Seedance 2.0 节点的 **定向创作 Skill** 选择本项，照常填写一个场景即可。稳定 ID 为 `zhenzhen_pov`。「贞贞」是方法署名，不指定人物姓名、性别、伴侣关系、身份图或 API 渠道。所有现有渠道和共享配置继续可用，角色圣经选填，不需要额外节点或表格。

它重点指导四件事：谁在看、观众怎样参与、人物何时收到信息、动作怎样产生可见结果。人物不是一直微笑着等镜头；但安静、无回应、等待、合作和未解决也都是有效剧情，不强制冲突、搞笑或反转。

Select this method in the existing H3 or Seedance selector and describe one scene. It guides viewpoint ownership, viewer participation, information reception and consequences. The credit selects neither a character nor a provider. Existing cloud/local/shared configurations remain available; the Character Bible is optional. Silence, cooperation and unresolved outcomes are valid, not defects that require a twist.

### 最简单的用法 / Quick start

- 导入一份示例：[H3](../example_workflows/directional_zhenzhen_pov_h3.json) 或 [Seedance](../example_workflows/directional_zhenzhen_pov_seedance20.json)。每份只有一个增强分支，Key 留空；云端执行需要填自己的 Key，本地 GGUF 不需要。12 秒、质量纠正是该图的设置；一镜写在示例原文，镜数控件仍为 AUTO，都不是技能默认。 / Each standalone graph has one enhancer and an empty key. Its 12-second and Repair settings are example choices; one take is requested in the prompt while the shot-count control stays AUTO. None is imposed by selecting the Skill.
- 普通增强：`眼睛第一人称，朋友等我指向桌面左侧，再把手中的空白卡片放在那里，最后卡片留在左侧。不新增对白、人物或道具。` 这是动作与持有关系示例，不是高分剧情展示。 / Ordinary enhancement: a friend waits for the viewer's leftward point before placing the held blank card there; no new speech, people or props.
- 允许创作：`12秒眼睛POV，两名成年朋友一起等雨停。允许为对方原创一句简短中文提议，我不回答。结尾继续等待，不新增道具、人物、字幕或配乐。` 明确允许才补对白，提供的原句仍逐字保留。 / Explicitly allow one brief proposal while the viewer remains silent and both continue waiting; only that dialogue gap is editable.
- 静默场景：`8秒固定眼睛POV，对方一直看窗外，不看我、不回应。全片完全静音，不加人物或事件，结尾保持原状态。` 不会因为勾选技能就自动开启极致表演或因果创作。 / A fully silent, unresponsive observation remains valid; selecting POV does not automatically enable Extreme or Causal controls.

### 适配与边界 / Adaptation and limits

无冲突的人物互动生成可采用眼睛 POV；明确的第三人称、固定外部机位、自拍、手持拍摄和原素材编辑要求优先。俯视／平视／仰视通过实际站坐关系与动作表达，不强制每条三角度。局部编辑不把原视频重拍成主观视角，延长／补轨沿用原素材职责。身份图不是首帧，首尾帧仍为各自锚点。

The method prefers eye POV only for unconstrained character interactions. Explicit external cameras, selfies, hand-held filming and editing boundaries take priority. Relative angles follow established positions; they are not three mandatory labels. Identity references do not replace first/last-frame anchors. Edits, continuation and track completion retain their native media responsibilities.

H3 保留所选模式、字面协议与严格英文选项；Seedance 不混入 H3 六段、标签或时间码。H3 Relay 沿用原 JSON 编排与分时逻辑，事件不等于切镜。用户时长、镜数、字数目标和禁止项优先；技能不会强制三条故事、15/20 秒、16:9 或附加 LoRA 触发词。仅当用户原始要求明确给出 H3 触发词时，才在合法正文位置保留原词，不检测或保证 LoRA 已加载。

H3, Seedance and Relay keep their existing separate output contracts. Duration, shot count, length targets and hard constraints remain authoritative. No fixed batch, duration, aspect ratio or automatic LoRA trigger is imported from the source package.

不增加规划、独立导演评分或视频调用；原有语言／格式修复、传输重试仍按原逻辑运行，开启质量纠正可能再请求一次。已有完整稿的质量纠正失败通常保留原稿，但首次生成失败、前置校验失败或无效 Relay 封套仍可能报错；保稿不代表质量合格。恢复上次结果仅恢复原稿及其技能来源，不按当前选项重新生成。

No additional planning, scoring or video request is introduced. Existing language/format repair and transport retries still apply; Quality Repair can add one logical correction request. Retention requires an existing complete draft and does not cover every failure or certify quality. Restoring a result uses its original content and provenance, not the currently selected Skill.

来源：[v1.5.9 快照及改编边界](../directional_skills/zhenzhen_pov/NOTICE.md)。工程验收与20轮讨论摘要：[接入记录](zhenzhen-pov-integration.md)。自动测试验证传参、协议与兼容链路，不保证模型遵循物理动作、相对机位或剧情效果；本次未调用真实云端／本地 LLM 或生成视频。

See the [source notice](../directional_skills/zhenzhen_pov/NOTICE.md) and [integration record](zhenzhen-pov-integration.md). Automated contracts do not prove camera compliance, physical execution or artistic quality. This integration was not evaluated through live cloud/local LLM generation or rendered videos.
