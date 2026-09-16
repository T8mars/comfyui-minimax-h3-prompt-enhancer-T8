# 质量流程与因果动作优化 / Quality and causal creation

这是原 H3 / Seedance 2.0 增强节点中的两个选填项，不是新的输出格式，不需增加连线或填写表格。旧工作流默认 Off / Original，原有渠道、共享配置、模板、表演导演与输出保持原用途。

## 选择 / Selection

| 选项 | 作用 | 可能追加调用 |
| --- | --- | --- |
| 保持原样 / Off | 原有生成与语言修复流程 | 原有规则 |
| 质量检查 / Check | 只检查完整输出，原样返回 | 不增加纠正调用 |
| 质量纠正 / Repair | 精确修复已定位的协议，再最多一次 LLM 纠正 | 最多 1 次逻辑语言/质量纠正，可能计费 |
| 原有编排 / Original | 保留原编排方法 | 不增加规划调用 |
| 因果动作优化 / Causal | 同次生成补“初态→动作/回应→可见变化→状态继承” | 不增加规划或评分调用 |

网络重试仍沿用渠道策略，逻辑调用不等于一个 HTTP 尝试。Relay 原有格式修复最多一次，与新的语言/质量纠正预算分别计数：首轮 + 格式修复 + 质量修复最多三次逻辑调用。Check 不修原文、不纠正语言；想检查并纠正请选择 Repair。

Options live in the existing nodes. Check preserves the draft and adds no correction. Repair performs only located protocol edits, then at most one logical quality/language correction. Existing network retry policy is independent. Relay retains its separate one-format-repair allowance. Causal is a method within the initial generation, not a planner call or a new schema.

## 检查范围 / Scope

H3 按实际任务解析三/六字段、真实镜头与时间码、强制首行对齐、传入素材集合、明确标签与说话人、正文对白/歌词/画面原文以及音层。描述语言不统计受保护台词和画面文字；严格官方模式按实际英文协议，不误按中文按钮判断。

Seedance 只使用自身自然语言，不套 H3 字段、speaker 或绝对切点。检查描述语言、明确原文与 H3 协议泄漏；未显式分镜时镜头数标为待确认。

Only deterministically supported text contracts are checked. Quoted dialogue, lyrics and visible words are protected; metadata does not satisfy an actual vocal event. Seedance keeps its own natural-language grammar. Ambiguous ownership, waiting, end-state semantics, physical feasibility and rendered video remain **unchecked**, not silently passed.

## 输出与失败 / Output and failures

运行后节点说明卡显示检查状态、失败项数、追加纠正次数；“查看/复制脱敏诊断”显示失败代码和未验证项。H3 第一个输出仍是完整原生提示词；Relay 仍是原有六输出；Seedance 仍是一输出。Inspector 可独立查看详细告警且不改写原文，结构分不是创作分。

候选空、错误增加、可确定原文丢失或请求失败，保留最后完整稿并明确标记。修复无法保证复杂事实不漂移，须人工核对人物、道具、等待与尾态；不要将无格式告警视为创作或成片验收通过。恢复上次结果只恢复已选定的完整稿，不重新运行模型或根据当前设置重写。清理运行时失败会单独提示，不能冒称显存已释放。

Rejected/empty/erroring corrections retain the last complete draft. No extra output socket is introduced. The UI exposes finite diagnostic codes rather than private prompts or model reasoning. Recovery restores the prior final result without regeneration. Cleanup errors are visible and do not erase a successful draft.

## 示例 / Examples

- [只检查双节点示例](../example_workflows/h3_seedance_quality_check_example.json)：Key 留空，填写后分别调用两个文本增强节点。
- [因果优化＋纠正示例](../example_workflows/h3_seedance_causal_creation_example.json)：保留无脸机器人、单镜头和动态尾态，不强行加脸、对白或定格；每节点质量纠正可能增加一次计费请求。

API 测试脚本 `tools/h3_quality_acceptance.py` 只串行运行，密钥无回显输入，证据写在仓库外。首尾帧实验上传真实合成 PNG；音层只检验文字合同，不宣称音频分析。创作实验独立固定质量策略，不能把格式修复收益混作创作增益。

因果编排仍是可选实验，不默认启用，不宣称稳定提升。真实文字测试发现：模型可能把未提供的路线图、栏带等补成“已有”道具；这一自称不等于来源证据，机器无协议告警也不能代替事实核对。尤其是“不得新增人物/道具”场景，请人工复核场景扩展。

Causal remains opt-in and experimental, with no stable-gain claim. A model can invent a route map or barrier and call it existing; that is not source evidence. A clean protocol check does not guarantee ownership, factual restraint or rendered-video quality. Review scene additions, especially when new entities/props are forbidden.
