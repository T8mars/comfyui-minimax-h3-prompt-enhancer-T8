# 可选语音／字幕参考 / Optional speech reference

新增 `T8 语音参考 / Speech Reference`，默认 **Off**。它先把语音变成文字证据，再交给原增强节点；不是给 H3 增加原生音频素材，也不生成音视频。

## 最简单的接法

1. 添加辅助节点，将 `mode` 改为 `Enabled`。
2. 来源明确选一种：已有文字／字幕、`AUDIO`，或官方文件型 `VIDEO` 的音轨。
3. 把第一个 `speech_reference` 输出接到 H3 或 Seedance 最后一个同名可选入口。原提示词仍填写你想创作什么。
4. 用 `speech_text`、`timed_transcript_json`、`subtitles_srt` 查看和校对结果；校对后的字幕可以切回 `Provided text` 复用，不必重新识别。

其他音乐、作词、编曲、Qwen 节点通过原有文字输入复用 `speech_text`。已有 Strata 独立转写节点的 SRT、时标 JSON、Confucius result JSON 也可输入本节点，不重复下载或建立 ASR 后端。

字幕支持纯文本 cue 的 SRT/VTT，保留输入编号／cue ID，便于按 ID 指派角色；重复 ID 明确拒绝。带 `<v>`、排版标签或 HTML 实体的字幕请先导出纯文本／校对后的 JSON，不会把标签读成台词，也不从 `<v 名字>` 猜用户角色。JSON 保留任意 cue ID；SRT 只能在全部 ID 为数字时保留原编号，否则使用连续数字，跨节点保留任意 ID 请使用 JSON。

字幕 cue 之间需保留空行，缺失分隔且混入下一条时间码时明确拒绝。SRT 只有毫秒精度：极短 cue 导出时至少保留 1ms，原 JSON 时标不改；精确复用时优先传 JSON。导入规范 JSON 仍保留 partial／需复核状态，不会因转换成文字而自动变成完整结果。

来源切换会保留原先填写的字幕，但隐藏的旧字幕不会混入 AUDIO／VIDEO 请求，也不会阻断已明确选中的自动来源；切回已有字幕时仍可继续编辑。未选中的媒体即使已被其他节点缓存也不会参与本次请求，冷／热缓存行为一致；所选来源缺失仍在访问服务前报错。

独立示例：[已有字幕 → H3](../example_workflows/speech_reference_h3.json)、[已有字幕 → Seedance](../example_workflows/speech_reference_seedance20.json)。示例不包含密钥；填好原渠道配置后才执行增强。

## 两种用途不要混用

| 用途 | 实际含义 |
| --- | --- |
| `reference`（默认） | 只理解情境与内容，不把转写原句自动变成旁白或对白。主提示词另有明确指定的台词仍以用户要求为准。 |
| `keep_dialogue` | 保留校对后的原词、原语言、顺序和次数。必须由用户明确指派角色，不从声音猜人物。 |

保留对白时，在高级选项填写角色映射，例如 `{"default":"<Subject 1> / S1"}`。这是你指定“交给这个角色说”，**不代表识别出了单一说话人**。多人素材应按字幕 cue ID 或已有 speaker ID 分别映射。参考时间是源素材的时间，不会直接硬套成目标视频时间；长台词与短成片是否可行仍需人工判断。

上例是 H3 编号写法。Seedance 或跨节点共用时，优先写自然角色名，例如 `{"default":"讲解者"}`，不要把 H3 的 `<Subject>`／`(Sx)` 当成 Seedance 原生标记。两节点仍按各自格式编译，不互相复制格式。

## 自动识别需要什么

先启动已配置 CPU 语音模型的 Strata。默认连接后端主机的 `http://127.0.0.1:8080`；非默认地址接一个 `T8 LLM Provider Config`，选 `Strata`。这份连接配置仅决定转写服务，后面的增强仍可分别选云 API、直接 GGUF 或 Strata。

“只读检查语音组件”只 GET 能力，不加载模型、不转写。自动模式要求服务明确声明 `contract_version=1`、`cpu_guard=true`，且本次转写 POST 携带 `expected_device="cpu"`。缺少保护的旧服务拒绝自动识别，但已有文字／字幕照常离线使用。服务端必须在同一配置快照里原子核对 CPU，不能仅靠调用前看一次设备；CUDA ASR 可能卸载驻留的主模型和视觉模型。

本插件不修改 Strata 设备／模型设置、不启动或停止服务、不下载权重、不卸载你的 ComfyUI 模型。文件型视频交给服务的自有 CPU 工作进程提取音轨；不支持的拼接／未知 VIDEO 请先显式转成 AUDIO、字幕或官方文件。AUDIO 只接受单条流，保留采样率／声道并在有界窗口内编码，不按低音量阈值冒充静音。

## 高级选项与失败

高级区包括起点、时窗、语言、词汇提示、视频音轨、声道、人工毫秒偏移、角色映射、部分结果及失败策略。

- 0 秒时窗表示已知输入的剩余全段；ASR 单窗最多 3600 秒。请求 JSON 最大 64 MiB、原始上传预检约 45 MiB、返回合同最大 2 MiB，LLM 另有上下文预算。它们是资源保护，不是重新给 H3／Seedance 设 15／30 秒业务上限；超出时明确要求裁剪或分段，不静默截断。
- 文件型 VIDEO 直传源文件后由服务隔离提取音轨；只改时间窗不会缩小源文件的上传体积。文件过大时先导出短片／AUDIO，或在独立转写工具中取得字幕后复用；AUDIO 则会先截取所选波形再编码。
- 手动偏移只用于自动转写：先在源时钟中选择整句，再在本地加一次偏移；不会因为偏移超出原选区而丢词。负起点截到 0 并标记复核；整句被移到 0 之前则明确报错，不能悄悄删掉。VIDEO 组件只有单条 AUDIO 时音轨必须是 0。
- 无音轨、数字静音、未识别到语音分别显示；部分结果默认拒绝，显式接受时标记需复核。时标是段级近似，不是逐词或口型对齐。
- 真正操作失败默认停在增强调用前。只有显式选 `continue_empty` 才可对可降级操作错误继续；锁词模式、取消、来源／契约错误或 CPU 安全保护缺失不能被吞掉。
- ASR 返回 409 冲突时也一律停止：它可能是服务端原子 CPU 断言拒绝配置切换，不能当成普通服务失败而继续空参考。缺少能力端点也不会降级；不通过私有错误正文猜测具体原因。
- 不自动重发转写 POST。正常重新运行自动模式会重新提交；服务缓存不等于免上传或免解码。取消仅关闭本次任务连接，服务须清理自己的工作进程，不停止用户服务。

## 输出检查、费用与恢复

语音参考开启后，最终输出检查已知的锁词、顺序、次数、描述语言及原生格式。先做不增加模型调用的白名单格式修正，必要时**最多追加一次语音合同纠正**；这与原有可选质量／语言纠正分别计数，不是网络重试。仍不合格时明确报错，不缓存成“成功输出”。这些文本检查不能证明 ASR 识别正确、创作更好或成片口型正确。

锁定的外语台词不会参与描述语言判断，也不因其中出现协议样式文字而被改写。Relay 模式的实际对白必须放在事件 prompt，不能放 global_prompt／end_state 代替。合法结果不因长外语台词多发纠正请求；[第二次交叉检查报告](SPEECH_REFERENCE_SECOND_REVIEW_2026-10-14.md) 区分了本地合同测试与真实模型验收。

未连接或 Off 时不走这条额外检查／纠正路径。恢复上次完整结果仅读取当前 ComfyUI 进程缓存，不重新识别，也不套用当前字幕或角色映射；缓存丢失会提示正常运行，不自动生成。lazy 仅跳过不需要的依赖执行，不能绕过 ComfyUI 整张图的静态验证。

隐私：Strata 有本地转写缓存，ComfyUI 历史／工作流可能保存输入输出；增强选择云 API 时，转写文字会发送给该渠道。诊断／恢复元数据仅保存有限状态和数量，不保存字幕、角色名或本机模型路径。分享工作流前自行清除私有台词和密钥。

## English

Use the default-Off **T8 Speech Reference** helper before an existing enhancer. Select one explicit source: provided text/SRT/VTT/JSON (offline), AUDIO, or an official file VIDEO's audio track. Connect its typed output to the appended optional lazy socket on H3/Seedance; other nodes reuse the plain text output. Transcription and enhancement providers are independent.

`reference` supplies semantic context without copying transcript speech. `keep_dialogue` preserves exact utterances and requires an explicit user role map. ASR does not identify speakers, emotion, music/BPM or environmental sounds. Segment timestamps are approximate, and source time is not target film time.

Automatic ASR requires an already running, CPU-configured Strata advertising an atomic CPU guard. This plugin never changes device settings or owns service/model lifecycle. Old API/GGUF/visual-Strata workflows stay inactive unless explicitly connected/enabled. Failed active-output validation permits at most one additional correction, then refuses success; existing language/quality calls remain separately chargeable. Recovery reads the original in-memory output without rerunning ASR. See the acceptance report for measured coverage and untested environments; no rendered-media quality claim is made.

SRT/VTT imports require reviewed plain-text cues, not voice/style markup or HTML entities. Cue IDs are retained in JSON; numeric SRT IDs are retained when all cues use numeric identifiers. Switching to automatic speech ignores the hidden provided-text cache. Manual calibration is applied once locally after source-window selection, never before the service's cropped-audio clock is mapped back to the original source.

Separate subtitle cues with blank lines. SRT export preserves positive intervals at its millisecond resolution without modifying original JSON timestamps. Canonical JSON retains partial/review flags. Locked foreign-language speech does not vote on descriptive language; Relay dialogue belongs in event prompts, not global constraints or end states.
