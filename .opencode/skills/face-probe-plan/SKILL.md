---
name: face-probe-plan
description: 用已有组件最近点和来源绑定面目录，自动筛选平面/圆柱面候选并规划有限面探测。用于草案补采后继续定位具体待测面；只规划、保留竞争候选和预算，不连接CAD、不确认接触或运动副。
---

# 规划具体面的探测

输入：当前草案check、最新evidence index及全部来源；明确组件距离筛选与解析面残差阈值。输出：新的只读任务计划。

1. 调用cad_plan_face_probes；参数与阈值含义先读[规划细节](references/planning.md)。使用当前check对应的最新索引，不扫描目录猜历史，也不手写面索引或种子。
2. 读取continuation、coverage、pair_contexts和face_candidates。缺目录时计划先安排sw_component_faces；已有目录时使用真实距离端点和中点生成种子。保留共面/同轴竞争解释、缺失来源、截断和剩余发现。
3. collect交接evidence-task-execute；完整执行且guards_passed后交接evidence-observation-index。使用新索引再规划，沿用原阈值与预算，最多4轮；stop时结束自动采集并报告风险。
4. 具体面探测完成后，仅将可复用face_probes的原始文件交接face-contact-review，使用明确的接触候选/角度阈值。面探测暂不自动回填关节草案。

解析曲面残差不检验有限面的裁剪边界；持久引用须在实际探测时解析核对。近测点、收敛或停止都不表示机械关系已确认，不设置人工复核节点。
