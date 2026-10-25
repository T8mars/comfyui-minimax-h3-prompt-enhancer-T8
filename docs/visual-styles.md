# 独立色彩与导演风格 / Independent visual styles

搜索 `T8 Color Style Config`（色彩风格配置）或 `T8 Creator Style Config`（导演风格参考）。两个本地配置节点分别连接 H3 / Seedance 2.0 的 `color_style_config` / `creator_style_config`。默认关闭，不接入 MOSS、Qwen 或音乐节点。

## 怎么用

1. 添加配置节点，点击“浏览风格与帮助”，按分类、编号或中英名称搜索。
2. 点击列表中的条目看色块或拍法说明，再点“应用到当前节点”。
3. 把配置节点的模式切为“开启 / On”，接到增强器对应输入口；设置原有 LLM 渠道、自己的 Key 和原始内容，再运行。
4. 只接颜色、只接导演或两者自由搭配；选导演不会自动选他的色卡。关闭或断开回到旧行为。

示例均只含一个增强器、空 Key、配置默认 Off：

- [颜色 → H3](../example_workflows/visual_style_color_h3.json)
- [导演 → Seedance](../example_workflows/visual_style_creator_seedance20.json)
- [两者组合 → H3](../example_workflows/visual_style_combined_h3.json)

原有38个保存字段、输出顺序和旧工作流保持。配置节点的浏览按钮、弹窗、搜索与预览不保存到 `widgets_values`；颜色只保存3项、导演只保存2项。失效历史名称保留，需重新选择，不能静默换成另一条目。

## 两个入口的边界

色彩提供六个主色及原相对比例的软参考；不是 LUT、像素覆盖率或图像处理。无需全部用上，不要求创造六种道具。默认“仅色彩”不改光位、机位或构图；选择“色彩 + 光影”才附带兼容的光影建议。四个候选点缀色只供预览，不自动注入。锁定服装、品牌色、自然肤色和参考身份优先；空间框的颜色只是标识，不能当作衣服或画面配色。

导演入口采用具体的构图、运镜、调度、信息呈现或节奏方法，不把名人姓名当作未经定义的生成指令。不自动加颜色、年代、服装、渲染媒介、人物、台词或原电影剧情。部分资料只支持通用镜头模板，预览明确标记“来源有限，非独有导演理论”；摄影师、美术和团队也有对应角色标识。不是200套完整编剧理论或自动剧本生成器。

用户原事实、对白/文字、身份、时长、镜数、首尾与 LOCK 优先。原导演 Skill 仍负责场面策略，表演、角色 Bible、战斗、分镜各司其职。固定单镜时移除资源中明确需要切镜的方法；不能保证识别所有自然语言冲突。H3 保留三/六段、Hybrid 与 Relay 协议；Relay 的常驻风格属于 global，不新造事件或尾部动作。Seedance 保留现有2.0表达，不导入外部2.5时长、语速或字数协议。没有新增时长上限、自动拆片或截断。

## 调用、缓存与恢复

浏览和两个配置节点为纯本地操作，零模型请求。选中规则加入原有增强请求；原来的语言/质量/语音/Relay修复或传输重试仍可能额外调用，不能将“无独立规划请求”解释为永远只调用一次。本地 GGUF 使用最终请求作预算，不静默删除规则来塞入上下文。

配置只携带编号、版本、摘要及作用范围；增强器从已校验的发行资源读取规则，拒绝外部typed配置携带任意提示词、路径或不匹配摘要。资源随发行版固定，更新插件后重启 ComfyUI，不承诺任意修改文件的热更新。恢复操作只还原内存中的旧输出，显示当时的编号/版本，不按当前选择重生成；重启后旧内存记录不在。

这些是实验性提示词建议。资源整理、工程测试或回环响应都不证明真实 LLM 遵从或成片审美收益；开启并不要求明显改稿。请用自己的相同内容进行 Off/只色彩/只导演/组合对照，分别检查硬约束与视觉收益。

## English quick guide

Add either config, browse/search the local catalog, preview a record, Apply, switch On, and connect its matching optional input on H3 or Seedance 2.0. Each example has one enhancer and blank credentials. Both modifiers are independent, opt-in and experimental; creator selection does not imply color selection.

Color references are soft hierarchies, not LUTs or measured pixel ratios. Lighting is separately opt-in and accent swatches are preview-only. Creator entries contain independently adapted presentation methods, not screenplay generation or borrowed movie scenes. Limited-source entries and non-director roles are labeled explicitly. Existing facts, timing, shot counts, dialogue, reference roles and locks take priority. Single-shot mode filters methods requiring cuts. No duration cap or automatic segmentation is added.

Helpers and previews make zero model calls; selected rules join the existing first request. Existing bounded corrections/retries remain. Immutable resources are integrity checked; restart after upgrades. Recovery restores historical output rather than applying today's selection. Engineering acceptance does not establish model compliance, translation accuracy or rendered-video improvement.
