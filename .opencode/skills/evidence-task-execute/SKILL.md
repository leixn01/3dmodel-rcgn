---
name: evidence-task-execute
description: 执行已有只读补采计划，自动核对文档和实例位姿，保存原始返回及逐步执行记录。用于把补采计划落实为观测；每次最多一次CAD读取，不负责规划、回填或机械确认。
---

# 执行只读补采

先读取计划的continuation；action=stop时不调用执行器，报告剩余风险。旧版无此字段的计划按原规则执行一轮。

输入：cad_plan_evidence_tasks原始计划及全部来源；当前SolidWorks文档应保持采集时的配置和位姿。输出：新执行记录和计划指定的原始envelope。

1. 首次调用sw_execute_evidence_task，传plan_path和新的output_path。缺少计划交接evidence-task-plan。
2. 后续调用使用相同plan_path，将上一条返回的output_path作为previous_execution_path，并提供新的output_path。串行继续到execution_complete=true；每次最多一个CAD工具调用。
3. 读取guards_passed、eligible_capture_ids、records、summary。只有完整执行且全部校验通过才交接evidence-reintegration；partial/failed/skipped和未覆盖范围留在结论，不设置人工复核。
4. 遇到错误、超时或占用文件，按[执行细节](references/execution.md)处理，不盲目重试、提高预算或修改旧token。

工具自行完成参数与上下文校验，skill不实现另一套判定。不自动启动/打开其他文档或执行计划之外的操作。
