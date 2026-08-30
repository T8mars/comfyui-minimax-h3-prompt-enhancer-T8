# T8 Character Performance Bible Stack（多角色表演集合）

把 1–8 个 `T8 角色表演圣经` 汇总为一个可连接到 H3、Seedance 2.0 或 Storyboard Pack 的紫色合同。节点纯本地运行，不调用 LLM。

- 每个输入角色必须有不同的角色标识；重复标识会在本地拒绝执行。
- 集合不会合并人物目标、策略、身体惯性或视线关系。
- 下游按“每个角色、每个节拍”分别执行一个主策略和最多三个可观察线索通道。
- 在多角色 Storyboard 中，逐镜 JSON 会要求 `character_performance_beats`，便于检查每个角色是否被单独导演。

只需要一个角色时，可跳过本节点，直接连接单角色表演圣经。
