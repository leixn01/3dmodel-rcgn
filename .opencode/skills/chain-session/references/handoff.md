# 续跑与失败

不要用新输出名重跑首次联调来清掉历史。只在明确的新模型/新快照任务中建立新的初始范围；跨会话历史仅来自用户/任务提供的文件，本入口不扫描全目录猜测历史。

- 已有完整check、constraints、index：交给evidence-task-plan，始终携带最新索引；已有solution可以直接解释，不再采集。
- 中断在批次内：根据最后完整call响应的execution_source及plan_source，交给evidence-task-execute，从原receipt继续。不要把batch报告当receipt。report空白表示进程中断，逐条call日志和原receipt仍保留；若有占用/空白的步骤文件，先核对实际状态，不盲目重跑。
- 首轮完成且保护通过、尚无关系基线：交给chain-baseline，使用原receipt和原配置公差。这个步骤离线，不消耗新采集轮次。
- DOCUMENT_CHANGED、COMPONENT_CHANGED或保护失败：停止与旧快照的回填；保留旧记录，获取新快照后明确作为新上下文重建，不替换旧token。
- TIMEOUT/OUTCOME_UNKNOWN：调用可能仍在完成，先核对软件状态；不自动重试或提升预算。
- 补采回填失败：保留原check/index及失败receipt；中间派生文件只诊断，不据此更新机械结论。
- SOURCE_CONTEXT_UNAVAILABLE、无配合、未支持规则等：结论列出缺失能力与风险，不用重复扫描替代求解/几何推断。

handoffs是已保存文件的定位信息；workflow_complete=false时不能把其中某个旧solution或中间结果当本轮最终结论。cad_capture_tool_timings是批次内部工具的时间；performance.stage_tool_timings含整个批次和离线分析，两者不能相加。若首个日志之后没有完整报告，保留文件并使用已有独立工具恢复，不删除占用文件重试。
