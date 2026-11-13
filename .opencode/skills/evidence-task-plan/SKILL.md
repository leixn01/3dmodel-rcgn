---
name: evidence-task-plan
description: 将草案检查或目标约束缺口转换成有预算的只读补采清单，包含准确工具参数、前后校验、依赖与原始返回保存路径。用于安排下一轮证据采集；仅规划，不执行CAD调用或自动回填结果。
---

# 补采任务规划

输入：原始draft check及全部可回读来源；继续补采时带最新evidence index；处理约束缺口时同时传constraint analysis。输出：outputs下新的evidence task plan。

1. 已有补采记录时先交接evidence-observation-index整理；调用cad_plan_evidence_tasks，传draft_check_path、output_path及evidence_index_path。首次无历史时可省略索引。缺少check时交接joint-draft-check，不读取全套开发文档。
2. 若请求补足约束报告，先读[约束缺口规划](references/constraints.md)，传constraint_analysis_path。新报告自带索引时沿用；只安排这一类缺口，其他发现保留并交接相应能力。
首次空证据链只采根配合时读[初始配合模式](references/initial-root-mates.md)；它不能替代后续约束缺口规划或索引。

有几何解释报告需补距离时读[几何缺口规划](references/geometry.md)，传geometry_analysis_path；与约束报告或初始profile互斥。

3. 读取tasks、deferred_tasks、reused_evidence、unresolved_findings与summary；带索引时同时读取完整remaining_findings，复用观测不消除原发现；报告真正的capture任务数和包含前后校验的总调用数。executed=false必须明确，不能称已采集或已验证。
4. 需要理解预算、依赖、来源复用或执行前置时读[计划细节](references/tasks.md)。不擅自增加工具、改旧token/来源哈希或猜测面索引/测点。
5. 带索引或约束报告的计划先读continuation：stop时报告原因和剩余风险，不执行保护空转或丢弃索引重新规划；collect时将原始计划路径交接evidence-task-execute；执行后的回填与比较继续由独立能力处理。当前入口只生成计划。

继续独立分析，在结论保留能力缺口与延期事项，不设置人工复核节点。

已有finite connection报告且缺圆柱面的有限边界时，按[有限边界分支](references/finite.md)使用finite_analysis_path；不要同时传其它profile。
