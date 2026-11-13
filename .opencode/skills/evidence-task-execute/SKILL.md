---
name: evidence-task-execute
description: 执行已有只读补采计划，自动核对文档和实例位姿，保存原始返回及逐步执行记录。用于把计划落实为观测，支持有预算的服务端串行批次与单步诊断；不负责规划、回填或机械确认。
---

# 执行只读补采

输入：原计划及全部来源，当前SolidWorks配置/位姿与采集一致。输出：逐步receipt、原始envelope；批次另外保存计时报告。先读continuation，action=stop时不调用执行器。

1. 常规执行优先读[批量执行与效率](references/batch.md)，调用sw_execute_evidence_batch（默认最多12步、软时间预算30秒），减少agent往返。服务端仍串行调用原单步工具并保留全部保护；不并行COM、不重新扫描已完整证据。
2. 批次返回continuation.action=continue时，沿用同一plan及execution_source.path作为previous_execution_path，用新的batch output_path继续。complete后看guards_passed/eligible_capture_ids；blocked或不确定结果停止。不要把batch_report_source.path当执行receipt。
3. 仅逐项诊断时用sw_execute_evidence_task，每次新output_path并传前一receipt；不要同时运行单步和批次。工具自行校验参数和状态，skill不实现另一套判断。
4. 完整且保护通过后，把**execution_source.path**交接evidence-reintegration或索引功能。面探测缺复核依据才读face-contact-review；目录走索引再交接face-probe-plan。约束回填已输出新check/index/analysis则直接沿用，不重复索引同receipt。
5. 缺计划才交接evidence-task-plan。partial/failed/skipped保留；错误、超时或占用文件按[执行细节](references/execution.md)处理，不盲目重试、提高预算、换旧token或重置4轮历史。

不启动/打开其他文档，不执行计划外操作，不设置人工复核。性能先读计时摘要；完整raw/receipt只在定位失败或核对具体证据时展开，不反复把全部数据灌入上下文。
