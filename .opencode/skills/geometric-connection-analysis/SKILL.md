---
name: geometric-connection-analysis
description: 从已有目标图的轴线、局部面探测和距离证据提出几何连接的竞争解释，并列出验证缺口。用于无配合STEP或需要区分几何相似与真实运动关系的任务；离线分析，不采集CAD、不套模板、不生成物理约束。
---

# 几何连接解释

输入：原始target graph，明确毫米/角度公差；有采集历史时带最新evidence index。输出：紧凑摘要及完整几何解释报告。

1. 来源已齐时调用cad_analyze_geometric_connections，传target_graph_path、distance_tolerance_mm、angle_tolerance_deg、output_path；有历史传evidence_index_path。max_pairs可限输出。参数与来源规则见[调用与来源](references/inputs.md)。
2. 先读coverage和analysis_source，需要解释具体组件对才读完整pairs。按[判读](references/interpretation.md)报告观测、竞争解释、未验证条件及风险，不把candidate_kind写成目标类型。
3. 缺距离且有几何线索时交接evidence-task-plan，传geometry_analysis_path；执行与索引继续由独立能力完成，再用同target和新index重算。具体衔接见[验证衔接](references/followup.md)。
4. 已有距离需有限面证据时交接face-probe-plan；使用其真实目录/测点与原保护、索引和四轮上限。已有完整或失败尝试不盲目重采。
5. 没有几何来源就保留source_gap，并只交接缺失的component-relations或face-contact-review能力。已有配合可另交mechanism-constraint-analysis；此报告不能传入运动求解器，也不改草案/分组。

不为离线分析启动SolidWorks；不设置人工复核。需要的运动、保持接触或连接验证尚无能力时，在结论明确保留缺口。
