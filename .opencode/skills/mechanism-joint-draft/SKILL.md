---
name: mechanism-joint-draft
description: 根据目标模型的配合、几何和冲突证据生成关系草案，保留未知关节类型与自由度；可选显式模板类比。用于分析零件间关系及多零件共同运动候选，不依赖模板、不采集CAD、不做运动求解。
---

# 关节参数草案

输入：原始rigid candidates及可回读来源。输出：outputs下新的joint draft文件。

1. 调用cad_draft_joints，不传template_ids，先生成目标证据基线。读取partition_results[].connection_candidates：按实例成员报告assessment、signals、flags、geometry和target_pair_coverage，不因没有模板匹配就丢弃关系或停止分析。
2. target_joint_kind=unknown、target_degrees_of_freedom=null时明确保留未知；配合特征、同轴/近接触和名称不独立证明机械关节。轴线规范点不是运动副枢轴，行程、零位、螺距未知。
3. 只有任务需要参考结构类比时才明确传template_ids；先读[草案说明](references/drafts.md)。报告reference_joint_kind/reference_dof与目标字段的区别，不能把台钳swivel等参考语义写成目标零件的revolute。缺少合适模板也继续基线分析；score不用于确定类型或选定刚体分组。
4. automatic_followup是后续采集建议，没有在本工具里执行。确需补充时只调度缺失的独立采集能力，重算相关来源，再生成新结果。遇到无法解决的差异继续独立部分，结论说明风险，不等待人工复核。

需要综合同一目标实例对的具体配合时，将原target graph交接mechanism-constraint-analysis；结果独立保留，不据候选覆盖本草案。

需要检查草案内部结构、证据冲突和覆盖缺口时，将原始draft路径交接joint-draft-check；不以匹配分数替代一致性检查。

没有刚体候选文件时交接mechanism-rigid-groups。本入口不加载整套采集或开发说明。
