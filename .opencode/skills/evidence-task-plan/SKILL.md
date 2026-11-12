---
name: evidence-task-plan
description: 将已有草案检查转换成有预算的只读补采清单，包含准确工具参数、前后校验、依赖与原始返回保存路径。用于安排下一轮证据采集；仅规划，不执行CAD调用或自动回填结果。
---

# 补采任务规划

输入：原始draft check及全部可回读来源。输出：outputs下新的evidence task plan。

1. 调用cad_plan_evidence_tasks，传draft_check_path、output_path。缺少check时交接joint-draft-check，不读取全套开发文档。
2. 读取tasks、deferred_tasks、reused_evidence、unresolved_findings与summary；报告真正的capture任务数和包含前后校验的总调用数。executed=false必须明确，不能称已采集或已验证。
3. 需要理解预算、依赖、来源复用或执行前置时读[计划细节](references/tasks.md)。不擅自增加工具、改旧token/来源哈希或猜测面索引/测点。
4. 若后续任务明确包含执行，将每项交给对应已有采集能力；按execution_policy串行执行及核对，保存原始envelope。当前入口自身不执行清单；补采后的证据重算也单独交接。

继续独立分析，在结论保留能力缺口与延期事项，不设置人工复核节点。
