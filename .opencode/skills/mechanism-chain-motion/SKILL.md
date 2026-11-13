---
name: mechanism-chain-motion
description: 将同一目标机构链的多组件配合约束组装为瞬时运动模型，计算剩余运动并检查闭环增加的限制。用于分析各组件对如何共同限制一条链；独立于局部关系判断、配合补采、整机运动与拆卸路径。
---

# 机构链瞬时运动

输入：原constraint analysis及全部来源，显式参考实例和数值特征长度。输出：新chain constraint solution和紧凑摘要；不连接CAD。

1. 缺报告才交接mechanism-constraint-analysis；已有时读[调用与范围](references/solve.md)。使用原链中2–20个实例，明确相对参考与毫米尺度；不要求模板，也不把每对局部DOF相加。
2. 调用cad_solve_chain_constraints，先读返回的status、coverage和缺口/冲突计数。详细矩阵和运动模式已保存到solution_source.path，仅解释具体方向/来源时读取该文件的对应快照。
3. 需要解释闭环、参考组件或耦合运动时读[结果解释](references/interpret.md)。逐源快照报告modeled_chain_instantaneous_dof；不同快照不合并，缺失或不连通时只描述已知约束子集。
4. 保留target_degrees_of_freedom=null、assembly_dof_solved=false及风险，不将参考实例宣称物理接地，不改草案或组件位置。当前姿态的瞬时维数不是有限行程或拆卸路径。
5. 缺几何/锁转时向evidence-task-plan交接**原analysis及同target的check**，沿用最新index和4轮历史。批量采集由evidence-task-execute处理，求解不安排或重置采集。没有新证据能力则停止重复调用，继续独立部分，不设置人工复核。
