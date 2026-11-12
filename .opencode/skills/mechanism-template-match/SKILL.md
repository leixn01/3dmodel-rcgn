---
name: mechanism-template-match
description: 对已有目标实例图搜索参考模板中的局部连接结构，输出实例对应、关节假设、排序依据和竞争解释。用于“用参考模板分析机构”“找一条升降链的候选结构”；不采集CAD、不编辑配合、不确认运动或拆卸路径。
---

# 模板局部匹配

输入：可追溯target graph，可选template_ids。输出：outputs下的新匹配报告。

1. 调用cad_match_mechanism_templates；默认参考库，heldout仅用于明确评测任务。pattern_size默认3，表示局部窗口，不能称整机识别。
2. 报告候选映射及score_components、轴向检查、缺边/额外联系、来源风险。查看template_rankings，避免把返回前几项当全部解释。
3. 必须一起报告search_exhaustive、output_truncated、同分数候选数。预算不足可按任务适当扩大，仍保留未搜索范围；无候选只代表本范围未找到支持。
4. 关节类型来自模板假设，score不是置信概率；不迁移模板行程，不把几何轴当已验证关节轴，不自动移动模型。继续可独立完成的分析，在结论保留替代解释与风险，不等待人工复核。

需要多零件共同运动的候选分组时，将原始target graph交接mechanism-rigid-groups，不把一对一匹配结果当刚体真值。

需要预算、评分或输出含义时读[搜索细节](references/search.md)。本流程不自动调用旧图评分工具；两者输入格式和目的不同。
