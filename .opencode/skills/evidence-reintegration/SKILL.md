---
name: evidence-reintegration
description: 将通过前后校验的完整补采结果回填到兼容的证据来源，重算机构链、目标图、刚体候选和关节草案。用于补采后的离线更新；保留旧版本、公差和预算，不执行CAD或直接确认机械关系。
---

# 回填并重算证据

输入：完整执行receipt及所有绑定来源。输出：新的回填报告和派生文件目录。

1. 调用cad_reintegrate_evidence，传execution_path、新的output_path。缺少执行记录交接evidence-task-execute。
2. 读取recomputation_complete、applied_capture_ids、superseded_sources、supplemental_captures、excluded_captures、steps和remaining_findings_summary。区分已回填、只作上下文、失败或部分观测。
3. recomputation_complete=true时，将before_check_source.path和after_check_source.path交接joint-draft-compare。否则保留pipeline_error与中间文件，只能用于诊断。
4. 具体兼容范围及失败分支按需读[回填细节](references/reintegration.md)。结论保留不确定项，继续独立工作，不等待人工机械确认。

再次规划前，将执行receipt和当前有效check交接evidence-observation-index整理完整观测与失败尝试；新计划必须携带该索引，避免重复补采。索引关联不替代本工具的兼容回填。
