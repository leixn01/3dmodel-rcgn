---
name: mechanism-rigid-groups
description: 对已有目标实例图生成多零件刚体候选分组，保留不合并基线、竞争方案和原始实例归属。用于判断哪些零件可能共同运动；不采集CAD、不运行模板匹配、不确认刚性连接。
---

# 刚体候选分组

输入：原始target graph及其可回读来源。输出：outputs下新的rigid candidates文件。

1. 调用cad_build_rigid_candidates；已有目标图时不重采集。缺少目标图才交接mechanism-target-graph。
2. 读取原始输出，检查每个partition保留全部实例且每实例只归属一个group；同时报告不合并基线、合并依据、弱接触假设、被阻止/省略的分组和来源风险。
3. 需要关节草案时只交接rigid candidates路径给mechanism-joint-draft；不能凭最高匹配分数决定哪个分组真实，不删除竞争方案。
4. 分组仅写新JSON，不修改SolidWorks。没有合并候选也正常；自动继续可完成的分析，不设置人工复核。

参数、边界和输出解释按需读取[分组细节](references/groups.md)。
