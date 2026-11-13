# 单链瞬时约束（0.25.0）

在0.24两实例局部模型上，本版把同一源快照的有效根配合联合为一条显式机构链的速度约束。2–20个叶实例是本轮范围；每源快照最多6000行方程，超限明确失败，不静默截断。目标机械DOF仍未知。

## 输入、坐标与组装

输入是原cad_analyze_constraints报告及其原target/raw sources；不是手工矩阵、局部求解输出或模板。参考实例必须属于原链，仅用于去掉整体共同刚体运动，不声明物理接地。数值特征长度L必填，原几何公差不变。普通和绑定索引的约束报告均可重放，沿用index/check/轮次。

所有实例速度用根装配坐标、共同原点o表达，每个非参考实例有6个变量x_i=[v_i(o)/L, omega_i]。共同原点为所选配合参考面点的均值；仅lock时为根原点。设局部约束在原点o_p的行系数为[a,b]，令r=(o_p−o)/L，则共同原点下为c=[a,b+r×a]。该约束在全链矩阵的两个实例块中分别填入−c和+c，参考实例块省略。

这是相对点速度v(p)=v(o)+omega×(p−o)的换原点关系，不能直接拼不同局部原点的矩阵，也不能把局部nullity相加。原0.24有效lock、同心轴、重合平面与显式锁转规则继续适用。行归一化后统一SVD，报告秩、零空间、数值敏感性及各实例耦合模式。算法在cadkin/constraints/chain_motion.py，来源与紧凑返回在cadkin/tools/chain_motion.py，流程说明独立。

## 内部联系、边界与闭环

原局部报告把“另一对实例的配合”视为本对边界。本版仅当其两个引用都准确绑定原链内实例，才把该项作为内部跨对联系；真正链外、多实体、未知引用仍是缺口。原局部missing记录保存在pair_diagnostics，不改原analysis。不存在直接配合的一对不必单独连边，但没有足够约束路径形成多个图分量时，整条链保持partial/未知。

受支持且有方程的实例对组成约束图。固定pair_id顺序构造生成森林，剩余边是闭合边；graph_cycle_count=边数−节点数+连通分量数。分别求森林/全图的秩，稳定时additional_loop_rank记录闭合边增加的独立线性限制。比较若数值不稳定则不给确定增量。该诊断依赖选定森林顺序，不能据此自动删配合。

| 示例（合成） | 森林/图 | 当前建模瞬时维数 |
|---|---|---|
| 两级同向锁转同心连接 | 开链 | 2 |
| 同方向增加第三条连接 | 一个重复约束回路 | 2 |
| 三边分别限制为不同方向的平移 | 闭合边增加2条独立限制 | 0 |
| 两个不同位置的轴+平面组合 | 两个局部转动组合 | 2，含耦合原点平移 |
| 有连接但第三组件孤立 | 不连通 | 未知；保留已知子集诊断 |
| 完整空配合 | 无可建模方程 | 未知，不称12DOF |

这些例子不是升降机实际结果。图回路、齐次线性系统可解及一阶零空间都不证明非线性闭合可行；奇异姿态可能产生无有限路径的瞬时方向。物理固定、碰撞、驱动、行程、子装配内部约束和未支持配合不参与本轮求解。

## 输出与判读

工具默认只返回summary、solution_source、coverage、各快照状态/维数/缺口计数。完整JSON保留方程、证据、模式、原点、输入哈希与历史，需要解释具体来源时才读取相应部分。

- modeled_chain_snapshot：已建模支持范围完整且稳定，modeled_chain_instantaneous_dof为当前线性模型维数。
- partial_constraint_model：缺少、截断、不连通或存在未支持约束；只保留known_constraint_nullity和已知子集模式。
- numerically_sensitive/conflicting_source：保留诊断与风险，不输出运动模式；模式空不等于锁死。
- no_supported_constraint_model：没有可用方程；维数null。

目标target_degrees_of_freedom=null，assembly_dof_solved/finite_motion_verified/mechanically_verified=false。源快照分开求解，不选“最合理”的一份拼接。批量补采仍使用原analysis/check/index，链结果不代替规划输入，也不重置4轮。

数学参考：[Modern Robotics Chapter 7](https://modernrobotics.northwestern.edu/nu-gm-book-resource/kinematics-of-closed-chains/)关于闭合约束、速度Jacobian与奇异性；局部方程与SVD实现见[LOCAL_CONSTRAINTS.md](LOCAL_CONSTRAINTS.md)。这里只实现受限的一阶约束组装，不实现完整闭链正/逆运动学。
