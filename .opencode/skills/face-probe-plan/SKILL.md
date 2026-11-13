---
name: face-probe-plan
description: 用已有组件最近点和来源绑定面目录，自动筛选平面/圆柱面候选并规划有限面探测。用于草案补采后继续定位具体待测面；只规划、保留竞争候选和预算，不连接CAD、不确认接触或运动副。
---

# 规划具体面的探测

输入：当前草案check、最新evidence index及全部来源；明确组件距离筛选与解析面残差阈值。输出：新的只读任务计划。

1. 调用cad_plan_face_probes；参数与阈值含义先读[规划细节](references/planning.md)。使用当前check对应的最新索引，不扫描目录猜历史，也不手写面索引或种子。
2. 读取continuation、coverage、pair_contexts和face_candidates。缺目录时计划先安排sw_component_faces；已有目录时使用真实距离端点和中点生成种子。保留共面/同轴竞争解释、缺失来源、截断和剩余发现。
3. collect交接evidence-task-execute；目录采集完成且guards_passed后交接evidence-observation-index，再用新索引规划。沿用原阈值与预算，最多4轮；stop时结束自动采集并报告风险。
4. 具体面探测完成后交接evidence-reintegration沿用原复核阈值。尚无兼容依据的组件对，将完整probe交接face-contact-review生成明确阈值的复核，再供回填使用。回填成功后独立比较，并用新check和当前receipt建立索引，才继续规划；失败时保留原有效check和诊断。

解析曲面残差不检验有限面的裁剪边界；持久引用须在实际探测时解析核对。近测点、收敛或停止都不表示机械关系已确认，不设置人工复核节点。

几何连接分析交来的近距离缺口同样使用本流程；完成guarded面探测并索引后，可交接geometric-connection-analysis按原target和最新index解释局部证据。仍不确认真实运动副。
