---
name: mechanism-constraint-analysis
description: 综合同一目标组件对的根装配配合、引用面与轴线，输出固定、旋转、滑动的局部约束组合候选及冲突和缺失依据。用于判断目标关系有什么约束支持；独立于模板、刚体分组和CAD采集，不求解整机自由度或执行运动。
---

# 目标约束组合分析

输入：原始target graph及其可回读来源。输出：outputs下新的constraint analysis；原文件保留。

1. 缺target graph时只交接mechanism-target-graph。已有时先读[参数与判读](references/analysis.md)，调用cad_analyze_constraints，明确毫米/度公差；不加载模板。
2. 按pairs[].snapshots[]分别报告constraint_facts、candidates、conflicts、missing_evidence。引用源哈希、feature_id、entity_index和实例路径；没有匹配目录时不补造body/face索引。同一feature_id在不同源中不是同一次观测，不能跨快照拼约束。
3. supported_local_pattern表示所实现的局部约束规则支持候选，conditional表示仍有缺口，opposed表示存在冲突。target_joint_kind和target_degrees_of_freedom仍保持unknown/null；不覆盖草案、不合并刚体、不宣称模型能运动。
4. 缺配合引用几何或锁定旋转状态时，将原报告和同target的check交接evidence-task-plan，按需读[补采交接](references/followup.md)。已有采集历史必须沿用；本分析工具不触发COM或执行任务。
5. 回填成功后读取新约束报告及其索引绑定，按原公差比较新旧候选、缺口和覆盖。仍缺证据、失败或不支持的规则保留未知，不循环重采或改写最终类型。
6. STEP缺少配合时保留几何上下文与未知；名称、近接触、同轴或参考swivel都不填入约束。可以继续独立分析其它对，结论列风险，不设置人工复核。

只有要解释实体绑定、不同快照或API语义时读[证据边界](references/evidence.md)。只需草案/补采时交接相应功能，不预加载其它skill。
