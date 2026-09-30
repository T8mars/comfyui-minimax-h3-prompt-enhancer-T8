# 战斗运镜配置 / Combat Camera Config

## 怎么连接

新增 `T8 战斗运镜配置 / Combat Camera Config`（`T8/Utilities`），将输出接入
MiniMax H3 或 Seedance 2.0 左侧的 **战斗运镜配置（可选）**。可以同时连接表演导演、
角色表演圣经，并保留当前独立 Skill。重启 ComfyUI、刷新页面后可找到新节点。

它只增强**已有动作的拍法**，不替用户创造敌人、招式或胜负。没有连接或选择关闭时，
不向原有请求增加运镜规则。原有输入、输出和保存的参数顺序不变。

| 设置 | 含义 |
| --- | --- |
| AUTO | 已有战斗/演练需要时补充运镜；非战斗不强行套用。 |
| 强化 | 明确观察路线、动作方向、接触点，改善空泛的运镜描述；仍不增加剧情。 |
| 沿用原设定 | 保留原有镜头组织。默认值。 |
| 偏好连续镜头 | 未指定剪切或镜头数时倾向连续观察；不覆盖固定镜数、固定机位、POV、首尾帧。 |
| 写实 | 优先看清动作与接触，不默认添加慢动作、定格、震动或粒子。默认值。 |
| 风格化 | 允许适度强调冲击，不要求每次命中都震动，不硬编码停顿秒数。用户限制优先。 |

简单输入：`两名成年练习者用木剑演练，红袖者向前一步挥剑，蓝袖者格挡后退半步。
保持侧面视角，让方向与接触清楚，不加敌人、招式、胜负或慢动作。`

选择「强化＋沿用原设定＋写实」即可开始。文档中的十种运镜是按已有动作选择的候选机制，
不是必须依次完成的十连招。固定机位可以通过构图、焦点保持动作可读，不强行移动相机。

独立示例：[H3](../example_workflows/combat_camera_h3.json) / [Seedance](../example_workflows/combat_camera_seedance20.json)。
每份只有一个增强器，密钥为空；按自己使用的渠道填写或连接共享配置。本地 GGUF 沿用原有能力限制。

## 融合、费用与恢复

- H3 继续使用原生字段、媒体身份和对白语法；Relay 保留原有封装和时间范围，事件不等于剪切。
- Seedance 继续使用自己的自然语言格式，每个镜头最多一个主运镜。轨道补齐是前后视频之间的过渡，不是补音轨。
- 首尾帧、媒体事实、明确时长/镜头数、台词、人物和物品归属、固定机位与终态优先。
- 表演导演负责人物表演，本配置负责相机观察；不替换独立 Skill，不停用案例模板。
- 没有额外规划、分类或评分请求；规则会增加输入 token，原有纠正和重试仍可能调用模型并计费。
- 语言、格式、质量纠正沿用同一份配置。恢复上次结果只读原缓存，不按当前运镜设置重新创作。
  恢复提示中的「上次选择」表示请求配置，不代表模型遵守了它，更不是成片验收。

## English quick guide

Connect **T8 Combat Camera Config** to the optional `combat_camera_config` input of H3
or Seedance 2.0. It supports the existing cloud/local providers and can coexist with
Performance Director, character Bible and a directing Skill. Unconnected/Off preserves
the original request exactly. AUTO fills useful gaps; Strong clarifies existing action
paths and contact without inventing choreography. Follow/Natural are the default
continuity/impact policies. Prefer continuous and Stylized remain subordinate to the
user's fixed camera, viewpoint, shot count, source frames and ending.

No extra planning request is added, but additional input tokens and existing repairs
may affect cost. Recovery returns the original cached result. Selection metadata is
not evidence of scene classification, model compliance, or rendered quality.

## 来源与 20 轮联合审查

用户提供《万能战斗运镜.txt》，SHA-256：
`be8feebd2b16bc915ee080f3903945651bbe1dc2997dd1392b0c1eabe263e3cc`。
独立表述其运镜机制，非官方规则；不转载整份文档、示例场景或推断作者身份。
这不是执行外部 Skill 或套用它的输出格式。

主 AGENT 与子 AGENT 逐轮讨论后确定以下决策，而非单方列出的假想讨论：

1. 独立类型配置节点，两个视频增强器末尾追加可选输入。
2. 三个原生选项，避免按钮/DOM 值混入工作流。
3. 同次模型条件处理，不用关键词硬判断、不新增分类调用。
4. 运镜是从属修饰，保留当前场景 Skill、表演与人物约束。
5. 十种机制只按已有动作选用，不强制整套连招。
6. 连续偏好不改镜数；固定机位和 POV 优先。
7. 写实不默认特效；风格化不强制停顿、震动或冻结。
8. 保留首尾帧、参考身份及编辑/延长范围。
9. Relay 保持原封装、时间线与事件衔接。
10. 云端、本地生成、预算构造透传同一配置，输入早校验。
11. 单独开运镜时也保留语言修复上下文，不重复上传图片。
12. 根据源码纠正 TrackFill 含义：多视频过渡；Seedance 每镜头一个主运镜。
13. 仅保存完整有限枚举的选择元数据；无效新配置不覆盖旧付费结果。
14. 原主节点 38 个序列化字段不变；新增 socket 不是 widget。
15. 两份独立示例，避免全图运行同时调用两个增强器。
16. 记录来源摘要；第 29 个节点追加注册，原 28 个次序不变。
17. 冻结已发布代码比对 None/Off，并覆盖真实构造/修复/恢复代码路径。
18. 工程测试不冒充真实模型效果或成片质量；不使用历史密钥。
19. 保留调用次数、失败回稿与本地释放策略，运行完整发布前门禁。
20. 确认方案后分工实现与独立回归，仍明确未验证的效果边界。

## 验收边界与后续对照

2026-09-30 工程验收：全量 Python 676 项（674 通过、2 跳过），前端 41 项全部通过，
Chrome 浏览器回归、示例生成器校验、密钥/包内容扫描通过。新增 16 项战斗运镜回归；
None/Off 与已发布 `db1121b99730a570bff0c84cc854c0c6948eed77` 消息逐字一致。
候选 ZIP CRC 与隔离加载通过：29 个节点、8 个官方 GIF、0 个 T8 GIF，不包含模型文件。
这是本地候选验证，并非 GitHub 推送或 Registry 发布。

上述工程测试使用真实 ComfyUI schema 和真实消息构造/恢复/前端钩子，但模型传输用测试替身，
不产生付费请求，也不加载 GGUF。另按用户授权进行了真实贞贞渠道 A/B，记录原始请求与结果，
与工程测试分开评价；未部署 RunningHub 或生成视频，不能宣称成片一定更好。

真实初测发现：固定双镜头的开、关两组都把时间码后的英文逗号写成中文逗号；开启组还把
红袖/蓝袖改成了护臂。现在仅对完整原生 H3 输出修复实际镜头时间码标点，不改数字、对白或
可见文字，不新增模型调用；并强化开启配置中的衣物/装备边界、第一人称手部可见性和时长保留。
这不是语义合规的确定性保证，仍需核对输出。详细真实验收见 [A/B 记录](combat-camera-live-ab.md)。

真实对照建议：同一输入、素材、模型、参数和 seed，比较关闭/AUTO/强化。
六组分别为冲刺格挡、单人演练、非战斗场景、固定机位、第一人称、首尾帧＋Relay。
逐项核查方向、接触清晰度、不加戏、终态与原生格式，再评价运镜是否有用。
云端 seed 不保证确定性；首尾帧忠实度需要实际媒体，成片质量需要实际生成的视频。
实测工具 `tools/combat_camera_live_ab.py` 默认隐藏输入密钥，只将无密钥证据写到仓库外；
它会产生真实付费调用，不能在普通 CI 或没有用户授权时运行。
