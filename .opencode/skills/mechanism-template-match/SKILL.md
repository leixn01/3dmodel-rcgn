---
name: mechanism-template-match
description: 对已有目标实例图进行可选参考模板类比，输出结构对应、参考关节语义和竞争解释。用于明确要求比较参考结构的任务；不作为目标关系分析的必要步骤，不采集CAD、不确认目标关节类型或运动。
---

# 模板局部匹配

输入：可追溯target graph，可选template_ids。输出：outputs下的新匹配报告。

1. 一般关系分析先交接mechanism-rigid-groups和mechanism-joint-draft生成不依赖模板的目标基线。需要参考类比时才调用cad_match_mechanism_templates；可明确template_ids，本工具不传时搜索参考库，heldout仅用于明确评测任务。
2. 报告候选映射及score_components、轴向检查、缺边/额外联系、来源风险。查看template_rankings，避免把返回前几项当全部解释。
3. 必须一起报告search_exhaustive、output_truncated、同分数候选数。预算不足可按任务适当扩大，仍保留未搜索范围；无候选只代表本范围未找到支持。
4. reference_joint_kind属于参考；target_joint_kind/hypothesis_kind为unknown，target_degrees_of_freedom为null。不能将swivel/revolute等参考类型继承到目标零件。score只评结构/相对轴线，不区分旋转和平移等目标类型；不迁移行程或移动模型。没有合适模板仍继续目标基线分析，不等待人工复核。

需要多零件共同运动的候选分组时，将原始target graph交接mechanism-rigid-groups，不把一对一匹配结果当刚体真值。

需要预算、评分或输出含义时读[搜索细节](references/search.md)。本流程不自动调用旧图评分工具；两者输入格式和目的不同。
