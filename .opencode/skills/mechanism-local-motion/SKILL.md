---
name: mechanism-local-motion
description: 从目标配合约束报告计算两个组件之间当前姿态的剩余瞬时平移和转动方向，报告约束秩、数值敏感性和证据缺口。用于分析已有约束允许怎样的局部微小运动；独立于配合采集、模板匹配、整机运动和拆卸路径。
---

# 局部瞬时运动

输入：原始constraint analysis及其可回读来源、显式毫米特征长度。输出：outputs下新的local constraint solution；原始证据保留。

1. 缺约束报告才交接mechanism-constraint-analysis。已有报告时读[调用与尺度](references/solve.md)，调用cad_solve_local_constraints；该工具离线，不启动SolidWorks或采集配合。
2. 按pairs[].snapshots[]逐份解释结果，先看status、coverage、unresolved_evidence、source_conflicts，再读modeled_instantaneous_dof与motion_modes。不同快照不合并；无可用约束是未知，不是6个已证实自由度。
3. 报告velocity_origin_root_m、特征长度和根装配坐标。motion_modes允许平移和转动耦合；需要解释方向、依赖方程或数值敏感性时才读[结果边界](references/interpret.md)。
4. 仅modeled_local_snapshot可报告“这份已建模局部约束的瞬时维数”。partial只描述已知约束子集，敏感/冲突不宣称可运动。target_joint_kind仍unknown、target_degrees_of_freedom仍null，不修改草案或刚体分组。
5. 缺几何/LockRotation才将**原constraint analysis**及同target的check交接evidence-task-plan；沿用最新索引与共享4轮历史。求解结果不能替代规划器的约束报告。无配合/不支持/已停止时保留风险，继续有独立依据的其它对，不设置人工复核。

不把模板、名称、近接触、CAD固定标志当约束，不改配合、移动零件或保存原模型。该结果不证明整机自由度、有限行程、避碰或拆卸路径。

需要联合多个组件或检查闭环额外限制时，交接原analysis给mechanism-chain-motion；不能直接相加局部维数。
