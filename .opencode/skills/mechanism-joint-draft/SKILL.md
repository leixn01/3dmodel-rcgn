---
name: mechanism-joint-draft
description: 对已有刚体候选分组分别匹配机构参考并生成关节类型、自由度及目标几何轴线草案，保留成员映射和未知参数。用于继续分析多零件共同运动结构；不采集CAD、不修改配合、不做运动求解。
---

# 关节参数草案

输入：原始rigid candidates及可回读来源。输出：outputs下新的joint draft文件。

1. 调用cad_draft_joints；默认参考库，不使用heldout。pattern_size默认3；如果任务关注两个刚体的局部关系，可统一用2重新计算所有方案。参数细节按需读[草案说明](references/drafts.md)。
2. 按partition_results分别报告映射到的member_occurrence_paths、候选类型/自由度、方向/轴线几何、缺失参数和竞争解释；一起报告同分数、搜索/输出截断及分组风险。
3. 轴线点只是目标圆柱无限轴线上的规范点，不是运动副枢轴；模板类型只是条件假设。未知行程、零位、螺距与运动可行性保持未知，不能复制参考值。
4. automatic_followup是后续采集建议，没有在本工具里执行。确需补充时只调度缺失的独立采集能力，重算相关来源，再生成新结果。遇到无法解决的差异继续独立部分，结论说明风险，不等待人工复核。

需要检查草案内部结构、证据冲突和覆盖缺口时，将原始draft路径交接joint-draft-check；不以匹配分数替代一致性检查。

没有刚体候选文件时交接mechanism-rigid-groups。本入口不加载整套采集或开发说明。
