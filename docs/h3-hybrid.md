# H3 Hybrid：关键帧＋额外参考 / Keyframes + references

## 怎么用 / Quick start

1. 用原来的 `MiniMaxH3PromptEnhancerT8`，将生成类型选为
   `Hybrid（关键帧+参考混合生成）`。
2. 连接 `first_frame` 和/或 `last_frame`，再连接至少一张额外参考图或一个
   参考视频。只有首尾帧请继续用 I2VA/FL2VA/L2VA；只有参考素材请用 Ref2VA。
3. 写清楚每份参考的用途，例如：“首尾构图严格保留，参考图只保留服装，
   参考视频只借鉴运动节奏；不要复制参考视频的背景。”选择中文或 English。
4. 输出仍接旧的 `enhanced_prompt`。H3 音频生成插件也选 Hybrid；两边连入
   同样角色和顺序的素材。不是自动切换下游 task_type，也不生成视频。

Use the existing H3 enhancer; choose Hybrid, connect first and/or last frame and
at least one additional visual reference, and describe the purpose of each asset.
Connect the same ordered media to the downstream H3 Hybrid generator. The enhancer
does not switch that generator's task or render video. Without extra references,
keep using the existing keyframe modes; without keyframes, use Ref2VA.

三份示例 / Examples:
[首帧＋参考图](../example_workflows/h3_hybrid_first_image.json)、
[尾帧＋参考图](../example_workflows/h3_hybrid_last_image.json)、
[首尾＋参考视频](../example_workflows/h3_hybrid_first_last_video.json)。
素材和 Key 均留空，请上传自己的文件；本地模式不需要 Key。

## 素材角色与编号 / Roles and labels

| 输入 / Input | 角色 / Role | 输出编号 / Label |
| --- | --- | --- |
| `first_frame` | 0 秒目标首帧 / Target at zero | 首个已连接 Picture |
| `last_frame` | 请求时长的目标尾帧 / Target at requested ending | 排在首帧之后；无首帧则 Picture 1 |
| `reference_images` | 明确指定的外观/身份/构图参考 / Requested visual attributes | 关键帧之后，按数值槽序压紧 |
| `reference_videos` | 指定视觉/动作证据 / Requested visual or motion evidence | 独立 Video 1..3，按数值槽序压紧 |

例如同时有首帧、尾帧、`reference_image_2`、`reference_image_8`、
`reference_video_2`：编号是 Picture 1/2/3/4、Video 1。空槽不占编号，
输出不暴露本地槽名或路径。额外参考不能偷偷变成首帧或尾帧。

Each image slot must hold one image: split IMAGE batches into separate slots.
Up to **nine additional images plus two keyframes (11 pictures)** and **three
videos**. Existing Ref2VA batch handling is unchanged. Empty/invalid image pixels,
unreadable/nonbinary/empty video sources and invalid duration metadata fail before
uploads/model construction and before replacing an existing paid checkpoint.

不设参考视频时长上限；仍保留有限正时长、格式、数量、云端上传容量和本地
上下文/显存限制。云端不接受活动裁剪，避免把未裁剪文件错当已裁剪视频；
本地沿用实际裁剪区间及时间戳采样。若预算装不下，不悄悄丢弃关键帧。

No per-video or combined duration cap is added. Provider upload limits, valid
positive metadata and model resource limits remain. Local timestamped samples
are visual evidence, not exhaustive analysis. This enhancer has no audio socket
and never treats a video's soundtrack as an independent `<Audio N>` attachment;
Hybrid with audio-only reference assets belongs in the H3 audio plugin, not this
visual-only enhancer. It still requires first and/or last keyframe; pure audio
without a keyframe is not Hybrid. A final replacement soundtrack alone is not a
reference asset.

## 输出格式 / Output contract

Hybrid 保留自身任务身份，采用原 `ref-en.txt` 的六段顺序，不切成三段模式：

`subject_definitions` → `summary` → `retention_analysis` →
`detailed_description` → `overall_soundscape` → `non_diegetic_music`。

关键帧定义增加简短 T8 角色标记，其余正文遵循实际输出语言：

```text
<Picture 1>: first_frame @0.00s - 首帧画面描述
<Picture 2>: last_frame @8.00s - 尾帧画面描述
```

Only supplied roles are emitted. Extra references are not inferred keyframes.
Summary identifies keyframe completion and reference use; retention and the shot
body track the real anchors. Dialogue and visible text keep the existing exact-text
rules. Strict official profile still requires English prose; compatibility profile
keeps the Chinese/English choice. T8 role/time tokens are bookkeeping, not a new
official audio-generator API. The vendored official Skill and its hash are unchanged.

## 渠道、质量、Relay 与恢复 / Providers, quality, Relay, recovery

- 沿用贞贞平价小屋、AI 工坊、OpenAI 兼容接口、本地 GGUF 四条路径和共享
  渠道配置。素材编号与角色规则相同，本地需要视觉模型及匹配投影器。
- Off 不新增质量纠正调用；Check 只报告；Repair 沿用最多一次质量纠正。
  语言/Relay 格式纠正及网络重试仍按原规则执行，不能把“一次纠正”解释成
  总计只扣一次费。失败保留已拿到的完整稿，不输出假通过。
- 检查器能检查六段、首尾角色/时间标记、引用及保留标记。它不能判断
  实际像素对齐、物理可达性、视频事实或最终效果；诊断将这些列为 unchecked。
  未提供已解析素材角色的 Inspector 也不会推断素材一定存在。
- Prompt Relay 仍输出原六个端口和原时间数学。native prompt 使用六段，
  尾帧对应请求的交付结束，不对应 padding；padding 只保持完成末态。
- “恢复上次云端结果”读取原缓存，不改写成当前 task_type，不再次请求
  模型。队列运行前展示缓存的 Hybrid 模式和图片/视频数量，无密钥和路径。

Quality checks are structural, not artistic or pixel scores. A retained draft may
still need review. Language correction preserves original intent and Hybrid roles
without reuploading media. Relay timing, ports and recovery semantics are unchanged.

## 兼容与验证范围 / Compatibility and acceptance limits

旧五种任务、默认 T2VA、主节点 38 个保存字段、输入输出/方法签名和旧示例
不变。本次新增三个示例，不批量改写旧工作流。新 Hybrid 工作流需要带该
选项的版本；不要降级到不认识 Hybrid 的插件运行。

工程回归使用真实 CPU 图片/视频和隔离传输，验证云端/本地参数、预算、
语言修复、Relay、缓存及实际前端保存/重载 hooks。浏览器回归不是
RunningHub 已上线部署验收；未运行真实 GGUF 或 H3 成片生成。

Real API acceptance uses 24 initial A/B completions (six keyframe/reference
combinations, two repeats, two valid task groups), with bounded correction and
retry budgets. Both groups receive the same actual visual assets, text and provider
parameters. The legacy control remains valid Ref2VA, not invalid FL2VA with extra
inputs. A shared variation seed in text is not a provider-native sampling guarantee.
The geometric fixtures contain no speech or visible words; their live results do
not prove literal-dialogue preservation. Late preflight-only fixes are covered by
offline regressions and not falsely attributed to the earlier API source snapshot.

模型仍可能误读压缩伪影、把用户的动作要求误归因给视频，或扩大参考图用途。
结构通过不能证明这些语义问题不存在。请人工核对输入/输出；
[本次 24 份真实 A/B 报告](H3_HYBRID_ACCEPTANCE_2026-10-06.md)分别记录合同检查
和统一尺度的真实素材审阅，不混成“成片质量满分”。

20 轮联合审议确定的核心边界：新增任务而非替换 Ref2VA；关键帧与参考角色
独立；不新增音频入口；沿用官方六段；不改旧默认/顺序；共用四渠道；本地
预算不丢素材；Relay/语言修复保持角色；恢复旧稿不重写；先验证再覆盖缓存；
冻结旧模式消息/工作流；新增示例单独校验；真实 A/B 与模拟/成片验收分开。

下游来源：[T8 H3 音频插件](https://github.com/T8mars/comfyui-minimax-h3-audio-T8)，
核对提交 `4c6abda4d00569fbf2a23d14ce33078206942d84` 的节点枚举、
conditioning 的首尾/真实参考判断和 first→last→refs 编号。额外参考图
九槽限制不包含首尾帧；原生规范值为大小写 `Hybrid`。
