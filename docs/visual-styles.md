# 独立色彩与导演风格 / Independent visual styles

搜索 `T8 Color Style Config`（色彩风格配置）或 `T8 Creator Style Config`（导演风格参考）。两个本地配置节点分别连接 H3 / Seedance 2.0 的 `color_style_config` / `creator_style_config`。默认关闭，不接入 MOSS、Qwen 或音乐节点。

## 怎么用

1. 添加配置节点，点击“浏览风格与帮助”，按分类、编号或中英名称搜索。
2. 点击条目查看直观示意：颜色对照“中性基准/所选配色”，导演可切换两条方法，动态方法可拖动进度或播放；再点“应用到当前节点”。
3. 把配置节点的模式切为“开启 / On”，接到增强器对应输入口；设置原有 LLM 渠道和原始内容，再运行。云端渠道填写自己的 Key，本地 GGUF 无需 Key。
4. 只接颜色、只接导演或两者自由搭配；选导演不会自动选他的色卡。关闭或断开回到旧行为。

示例均只含一个增强器、空 Key、配置默认 Off：

- [颜色 → H3](../example_workflows/visual_style_color_h3.json)
- [导演 → Seedance](../example_workflows/visual_style_creator_seedance20.json)
- [两者组合 → H3](../example_workflows/visual_style_combined_h3.json)

原有38个保存字段、输出顺序和旧工作流保持。配置节点的浏览按钮、弹窗、搜索与预览不保存到 `widgets_values`；颜色只保存3项、导演只保存2项。失效历史名称保留，需重新选择，不能静默换成另一条目。

## H3 普通开启的具体执行提示（1.40.0）

在色彩或导演配置节点选择 **开启 / On**，连接原来的 H3 输入口后正常生成。普通开启沿用旧试验模式的执行提示，并增加开放颜色补全说明：把所选色彩写到已有可见且未锁色的表面，把适用导演方法落实到具体机位、构图、运动或节奏。旧 **开启（H3强化试验） / On (H3 experimental)** 仍可读取，在本版与普通开启使用相同提示；它不再是另一套更强规则。

原文把已有可见表面的颜色写为“未指定”或“待定”，且没有要求保持原色、参考色或未知状态时，这一颜色可以由所选色卡补全。最终描述应指出表面的具体颜色，不能只重复“颜色未定”；已有黑衣、灰地等锁定色也不能代替开放表面的配色。原色、参考色、材质和明确的未知状态要求仍优先。

颜色与导演独立启用，只请求对应维度；默认仍是 **关闭 / Off**。Off 与 Seedance 的生成文本保持原样；没有新增节点、连线、保存字段或独立风格规划/纠正请求，原来的语言等处理仍按原链路执行。这些是写入正常增强请求的提示，不是程序自动判定风格合格。

如需退出这一维度的增强，把对应配置切为 **关闭 / Off** 并重新生成；切回普通 On 不会退出，因为两个开启选项都使用本版规则。“恢复上次结果”只恢复历史文本及当时模式，不会按当前模式重写。更新后重启 ComfyUI。

<a id="style-validation"></a>

### 当前验证结论 / Validation status

<!-- VISUAL_STYLE_VALIDATION_STATUS_START: update this block when the full run is reviewed. -->

固定版本已完成200个导演条目与200色卡配对的 **T2VA文字场景**，每条目一个场景，全部使用已安装的 `Qwen3.8-27B-Q4_K_M.gguf` 和同一种子104729。**190/200（95%）同时确认配色与拍法落实**，达到这组覆盖的90%文本验收门槛；5例失败、5例不确定均未计入通过。这是本组单次覆盖结果，不是每位导演反复生成的成功率。

The fixed implementation completed **200 paired T2VA text scenarios**, one per creator entry, using the installed `Qwen3.8-27B-Q4_K_M.gguf` and the single seed 104729. **190/200 (95%) concretely expressed both palette and method**, meeting the 90% text target for this coverage set. Five failures and five uncertain cases are excluded from passes. This is a single-run coverage result, not a repeated-generation success rate for each creator.

| 验证维度 / Dimension | 确认通过 / Confirmed | 失败 / Failed | 不确定 / Uncertain |
| --- | ---: | ---: | ---: |
| 配色 / Palette | 197/200 | 1 | 2 |
| 导演方法 / Creator method | 193/200 | 4 | 3 |
| 两者同时落实 / Both together | 190/200 | 5 | 5 |

分组保留如下，不能把开发回归混称独立留出。此前开放颜色补全候选的20/20记录保留：前10条是已知样本回归，后10条是首次未见输出。前20条候选请求与合入版本逐字一致，后180条直接使用正式源码，没有临时替换模块，也没有按案例挑选不同版本的最好结果。

The cohorts remain separate: development regressions are not independent holdouts. The earlier open-color candidate's 20/20 record is retained as ten known-case regressions plus ten first unseen-output cases. Those 20 requests match the merged implementation exactly; the remaining 180 use production code directly, without a temporary module replacement or per-case selection of the best version.

| 分组 / Cohort | 两维确认 / Both confirmed |
| --- | ---: |
| 001–010：已知开发样本回归 / Known development regressions | 10/10 |
| 011–020：候选冻结后首次看到输出 / First unseen-output holdout | 10/10 |
| 021–200：正式源码续测 / Direct production continuation | 170/180（94.44%） |

未确认案例全部保留；下列编号是案例编号，不是配对色卡编号。

All non-confirmed cases remain recorded. Numbers below identify cases, not their paired palette IDs.

| 案例 / Case | 维度与判定 / Dimension and status | 原因 / Reason |
| --- | --- | --- |
| 032 | 配色不确定 / Palette uncertain | 灰色表面与所选灰绿色卡的对应不足以确认 / Gray surface cannot be confidently matched to the selected gray-green palette. |
| 039 | 导演不确定 / Method uncertain | 跟随已体现，但广角或宽视域未确认 / Following is concrete, but the wide-angle or broad-view condition is unconfirmed. |
| 056 | 导演失败 / Method failed | 只有递卡剧情，缺少观看注意力交接 / Card handoff alone does not establish an attention handoff in the framing. |
| 086 | 配色失败 / Palette failed | 开放表面只写材质，未落实所选颜色 / Eligible surfaces name materials without selected colors. |
| 087 | 导演失败 / Method failed | 未落实所选运镜或紧接剪辑节奏 / Neither the specified camera movement nor tighter cutting is concrete. |
| 120 | 导演不确定 / Method uncertain | 平视与低角度描述冲突 / Eye-level and low-angle descriptions conflict. |
| 125 | 配色不确定 / Palette uncertain | 已写绿墙黄门，又称两处颜色未确定 / Green wall and yellow door are specified, then called undetermined. |
| 160 | 导演不确定 / Method uncertain | 固定机位与推进描述冲突 / Fixed-camera and push-in descriptions conflict. |
| 189 | 导演失败 / Method failed | 没有变焦，也无可用的重复情境处理 / No zoom or eligible repeated-situation treatment. |
| 199 | 导演失败 / Method failed | 未落实方法所需的观察高度或跟随 / Neither the method's observation-height condition nor following is realized. |

通过项中24条标为“来源有限”（`source_limited`），表示资源列出的通用方法已具体体现，不代表复刻独特导演签名。审查也标记了33条保留原有具体拍法的案例；保留适用方法可以通过，但不能据此证明比Off更好。没有验证生成视频、每位导演的多种子或重复生成成功率，也没有完成真实参考图输入的Ref2VA实模效果验证。

Among passes, 24 entries are marked `source_limited`: their listed generic methods are concrete, which does not establish recreation of a distinctive director signature. Reviews also flag 33 cases retaining an already concrete method; preservation can pass, but does not prove improvement over Off. Rendered video, repeated or multi-seed reliability per creator, and actual Ref2VA model effects with reference-image inputs were not validated.

<!-- VISUAL_STYLE_VALIDATION_STATUS_END -->

主验收项是 **所选色卡与适用导演方法是否在最终提示词中具体落实**：颜色有可识别的画面落点，至少一种原方法有实际拍法描述，同时开启时两者均可在所述画面成立。对白、人数、动作顺序和时间另行记录，不纳入风格成功率；原事实保留要求仍然有效，这些内容也不因此视为通过。

当前覆盖测试使用本机已安装的 `Qwen3.8-27B-Q4_K_M.gguf`，seed=104729、balanced 温度0.7、关闭thinking、上下文32768、输出预算4096、Quality Off、表演导向 Off，保留正式链路自身的语言处理。前20条候选的完整请求与合入版本逐字核对；后续直接使用正式源码。请求一致性与工程测试只证明接入和兼容性，不保证模型效果。没有新增模型下载，也没有生成或验收视频；浏览器中的“真实生成对比”仍是未实测。

The score covers concrete palette placement and at least one applicable original creator method in the described scene; both must coexist when both are enabled. Other content issues are recorded separately. The installed `Qwen3.8-27B-Q4_K_M.gguf` uses seed 104729, balanced temperature 0.7, thinking off, context 32768, output budget 4096, Quality Off and performance Off, retaining native language handling. The first 20 candidate requests match the merged implementation. Request equality and engineering checks do not establish model compliance. No model was downloaded and no rendered video was generated or evaluated.

<details>
<summary>历史：首组小样本与扩大测试中的配色遗漏</summary>

最初27B测试通过正式 `enhance_prompt` 链路完成12个文本场景：10个适用场景全部体现启用维度，分别为8个组合、1个仅颜色、1个仅导演；另外2个观察边界，不计入成功率。该组使用seed=109，其余参数同上，测试的是尚未增加开放颜色澄清的旧试验提示。已有9B thinking输出按相同风格口径回溯为9/10，不是新请求或多种子复测。

随后扩大测试的旧版本在完成001–010后停止：导演10/10、配色8/10、组合8/10。003、006两例仍将已有可调表面的颜色写为“未确定”；请求传入、完整响应及最终输出都已核对，原始失败保留。修正后的001–010属于已知样本回归，011–020单列为未见输出的留出样本，不能把它们混称20条独立留出，也不能把最初小样本结果外推为全部条目有效。

The initial 27B set had 10 applicable cases: eight combined, one color-only and one creator-only, plus two separate boundary observations. All enabled dimensions appeared, using seed 109 and the earlier experimental instructions. Rescoring existing 9B thinking outputs gave 9/10. The later expansion stopped after its first 10 cases: creator methods passed 10/10, palettes 8/10, jointly 8/10. Cases 003 and 006 left eligible colors undetermined. Those failures remain recorded; corrected regressions and held-out outputs are reported separately.

</details>

<details>
<summary>历史：1.39.0 为什么先提供独立试验选项</summary>

1.39.0 把执行与保源提示放在新增的“开启（H3强化试验）”选项，当时普通 On 保留旧行为。该历史行为已被上面的1.40.0说明取代。

当时本地 `Qwen_Qwen3.5-9B-Q8_0.gguf` 的正式链路对照使用8个合成场景、同seed=71和相同采样，共16次完整调用，Quality保持Off，未使用外部人工方案或槽位。部分人物台词补上原生发声标签，但061卧室和无人画外音仍漏标签，配色与部分拍法仍未落实；画外音案例出现了原文禁止的物理接触声，玻璃行走的“固定机位/跟随视角”也有歧义。因此当时只交付手动试验选项，不宣称稳定正收益。该记录保留，不与后续27B测试合并计分，也不是成片验证。

</details>

## 直观预览：200 色彩 / 200 创作者

- **色彩**：同一原创矢量室内/街景提供中性和配色并排对照，肤色与衣服固定。保留六主色、候选色与精确说明；场景面积不代表六色比例。可预览原说明的一类光影，初始开关跟随节点的作用范围，但弹窗中的场景/光影开关仅控制示意，不修改节点。
- **导演**：400条现有方法各有人工对应的构图、机位、空间、动作或节奏图式。选择第1/2条方法，动态示意可拖动相对进度或播放/暂停，默认不播放；静态构图会禁用进度与播放，避免制造原方法没有的运动。灰度画面不暗中采用该导演的色卡。箭头、A/B、物件是解释拍法的教学符号，绝不加入提示词。允许切镜的条目明确提示固定单镜会跳过；其他原有条件仍以完整方法文字为准。
- **真实生成对比**：当前条目没有经验证的H3/Seedance成片，面板明确显示“未实测”。矢量图不是模型输出、电影剧照、LUT或审美收益证明；不拿同一个样片冒充200种效果。实际比较需要记录模型、版本、完整输入、参数、增强结果并控制相同内容。浏览不会发起生成或付费调用。

全部示意由本地浏览器绘制，离线可用，无外部素材下载，不依赖原资料D盘，不分发原电影剧照。映射以原规则资源SHA256绑定；版本不匹配或示意缺失时显示不可用，已校验的风格说明/选择继续可用。演示播放在关闭、换条目、搜索、切工作流、所属节点失效或页面隐藏时停止；预览进度不是生成时长，不增加时长限制。缩小窗口时改为单列，不更改画布节点尺寸。

## 两个入口的边界

色彩提供六个主色及原相对比例的软参考；不是 LUT、像素覆盖率或图像处理。无需全部用上，不要求创造六种道具。默认“仅色彩”不改光位、机位或构图；选择“色彩 + 光影”才附带兼容的光影建议。四个候选点缀色只供预览，不自动注入。锁定服装、品牌色、自然肤色和参考身份优先；空间框的颜色只是标识，不能当作衣服或画面配色。

导演入口采用具体的构图、运镜、调度、信息呈现或节奏方法，不把名人姓名当作未经定义的生成指令。不自动加颜色、年代、服装、渲染媒介、人物、台词或原电影剧情。部分资料只支持通用镜头模板，预览明确标记“来源有限，非独有导演理论”；摄影师、美术和团队也有对应角色标识。不是200套完整编剧理论或自动剧本生成器。

用户原事实、对白/文字、身份、时长、镜数、首尾与 LOCK 优先。原导演 Skill 仍负责场面策略，表演、角色 Bible、战斗、分镜各司其职。固定单镜时移除资源中明确需要切镜的方法；不能保证识别所有自然语言冲突。H3 保留三/六段、Hybrid 与 Relay 协议；Relay 的常驻风格属于 global，不新造事件或尾部动作。Seedance 保留现有2.0表达，不导入外部2.5时长、语速或字数协议。没有新增时长上限、自动拆片或截断。

## 调用、缓存与恢复

浏览和两个配置节点为纯本地操作，零模型请求。选中规则加入原有增强请求；原来的语言/质量/语音/Relay修复或传输重试仍可能额外调用，不能将“无独立规划请求”解释为永远只调用一次。本地 GGUF 使用最终请求作预算，不静默删除规则来塞入上下文。

配置只携带编号、版本、摘要及作用范围；增强器从已校验的发行资源读取规则，拒绝外部typed配置携带任意提示词、路径或不匹配摘要。资源随发行版固定，更新插件后重启 ComfyUI，不承诺任意修改文件的热更新。恢复操作只还原内存中的旧输出，显示当时的编号/版本，不按当前选择重生成；重启后旧内存记录不在。

这些是提示词层面的建议，小样本真实文本验证范围见上文。资源整理、工程测试或回环响应不能代替真实生成评估，也不能证明成片审美收益；无需为制造差异而大改，但有适用空间时应写清所选维度。可用相同内容进行 Off/只色彩/只导演/组合对照，分别检查所选风格与原内容是否保留。

## 开启后应该看到什么

开启表示明确要求在兼容范围内落实所选维度。色彩应在最终画面描述中指出可用色相及其对应的未锁定表面/背景；导演应写明至少一种适用方法如何用于现有主体、空间或机位。已经具体体现的方法可以保留；“电影感”“自然”“暖色”等泛词不能代替所选配色与拍法。极致表演负责演技结构，其“不随意改其它画面”的限制不取消用户另外开启的颜色/导演选择。

例如022色卡的深紫、红、深青绿可用于原场景已有且未锁色的区域，人物黑色上衣和自然肤色仍保留。022拍法若没有已知玻璃或反射，不应凭空加镜子；可以选择另一条允许的近距离观察或横移。此处只是如何读结果的例子，不是实测输出，也不要求每次都强行制造差异。颜色选“仅色彩”不会启用彩色灯光，所有可用维度都被明确锁定时仍以锁定内容为准。

曾有版本只传HEX和弱提示，允许“原样不变”，容易被表演细节掩盖；现已增加中性的色相词、逐维度落实与同次回答内的自检要求。色相词由RGB计算，不把“恐惧”等色卡命名转成剧情或情绪。编译规则缓存版本独立更新，原400资源摘要与工作流接口不变。更新后重启ComfyUI，确认使用正常生成而不是“恢复上次结果”，再运行开启/关闭对照；恢复功能会保留旧输出。

节点不会为风格自动增加纠正请求，也不会把色卡机械拼到生成结果后。以上工程修正仍不等于真实模型必然遵从；只看截图无法证明某次远端请求携带了哪些配置。

### 历史：早期本地 GGUF 对照发现的限制

以下保留早期候选的原结论；它们采用不同模型、参数和验收口径，不与上面的27B风格成功率合并。当时撤回的候选不代表当前 On 的测试结果。

2026-11-02 用本机 `Qwen3.5-9b-heretic-v2-q8_0.gguf` 做真实文本对照：同一模型、种子、温度及完整首次请求，分别关闭、仅色彩、仅导演、同时开启。使用合成场景，不使用用户截图或凭证；没有生成视频，也没有把回环测试当作模型结果。

在 seed=12 的两个允许调色场景中，原规则的四条启用颜色输出都未写出具体选中色。把简短风格说明加到任务末尾后，部分结果出现了深紫背景，但也出现持续行走被改成定格；再强调两个维度同时落实，甚至把锁定白墙改成紫色。前置说明也出现过漏掉准确台词。因此这些任务说明方案均已撤回，未进入运行逻辑；不能用“配色更明显”抵消硬约束退化。

另用 seed=37 做原版与候选各16条对照，加入未参与调词的商品场景。更强调来源权重的候选把一条锁定杯色 `#C8102E` 改成色卡 `#C41E3A`，因此也撤回该加强规则；不能据一对样本断言某一句是唯一原因。两版都未稳定落实可调区域的配色，撤回后的状态也不能冒充已经通过这次留出评估。

保留的修正针对可核验的信息和边界：深/中/浅灰不再合并成同一描述；导演方法同时携带原中英文，避免遗漏“缓慢”等限定，并明确双语是一种方法；允许已有剪辑点使用对应方法，但 AUTO 也服从用户的一镜到底要求。语言纠正只翻译已有结果，不借机补色或重排机位。资源编号、摘要、配置接口与未开启行为保持。

这些改变不能宣称已让颜色与导演组合稳定生效。首次输出中的说话人/语言标签问题也应与风格分开检查；本次对照不代替完整质量纠正链、真实 Ref2VA 图片验证或成片审美评估。

最终共102次真实本地调用：12次探索、88次正式首次请求对照/回归，以及一次完整增强流程的2次调用。撤回后8条已知案例回归未再次改变锁定杯/桌色，但仍有英文初稿、额外渲染风格或含糊场景描述。另一次完整增强实际触发现有语言纠正，最终中文保留了 `#C8102E` / `#808080`，没有补配色；这只证明该单例修复链可用，不是独立风格收益证明。

## English quick guide

Add either config, browse/search the local catalog, preview a record, Apply, switch On, and connect its matching optional input on H3 or Seedance 2.0. Each example has one enhancer and blank credentials. Both configs default Off and combine independently; creator selection does not imply color selection. Since 1.40.0, ordinary H3 On uses the earlier experimental execution instructions plus the open-color clarification. The legacy On (H3 experimental) choice uses the same current instructions. Off and Seedance generation text are unchanged; no new fields or separate style requests are introduced. To stop applying a dimension, switch its config Off and regenerate.

Unspecified or undetermined colors on existing eligible visible surfaces can be completed from the selected palette. Original colors, reference colors, materials and explicit instructions to keep a color unknown remain protected. The output should name the resulting surface color, rather than repeat that it is undetermined or substitute a coincidentally matching locked color. See the centralized [validation status and historical findings](#style-validation) for measured scope and limitations.

All 200 palettes have local neutral/colored vector-scene comparisons (interior or street), with locked illustrative skin/clothing and separately toggled lighting demonstrations. These controls do not change the node scope. All 400 creator methods map to reviewed neutral diagrams; dynamic methods allow scrubbing and Play/Pause, while static compositions disable playback. Nothing autoplays or enters saved widgets/prompts. Illustrations are pinned to resource hashes, work offline and fail independently of valid style selection. The real-output section explicitly says untested: these are original teaching diagrams, not rendered H3/Seedance results or film stills. No inference, downloads, new duration cap, or hidden palette selection is involved.

Color references are soft hierarchies, not LUTs or measured pixel ratios. Lighting is separately opt-in and accent swatches are preview-only. Creator entries contain independently adapted presentation methods, not screenplay generation or borrowed movie scenes. Limited-source entries and non-director roles are labeled explicitly. Existing facts, timing, shot counts, dialogue, reference roles and locks take priority. Single-shot mode filters methods requiring cuts. No duration cap or automatic segmentation is added.

Enabled selections now request concrete visible realizations in the native description: neutral hue words on eligible existing areas, and an applicable creator method with a specified framing, camera or timing choice. Acting-only restrictions do not cancel separately enabled style requests. Explicit locks still prevail; no missing prop or light may be invented. The instruction cache revision changes independently of resource/config identities. Restart after updating and use normal generation, since recovery intentionally keeps the previous result. This is a prompt-policy fix, not a verified model-output guarantee or an additional automatic correction call.

Helpers and previews make zero model calls; selected rules join the existing first request. Existing bounded corrections/retries remain. Immutable resources are integrity checked; restart after upgrades. Recovery restores historical output rather than applying today's selection. Engineering acceptance does not establish model compliance, translation accuracy or rendered-video improvement.

Earlier local GGUF text probes found that stronger task-level style reminders could improve palette visibility while breaking locked colors, motion endings or exact dialogue. Those earlier candidates were withdrawn, as was stronger weight-priority wording after a held-out locked-product color failure. The historical findings above remain recorded separately from the later 27B style-only evaluation; they must not be pooled into its score or treated as rendered-quality evidence.
