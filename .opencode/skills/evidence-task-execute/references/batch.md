# 批量执行与效率

sw_execute_evidence_batch必填plan_path、output_path；可选previous_execution_path、max_steps（1–20，默认12）、time_budget_seconds（1–60，默认30）。只执行现有计划的一个前缀，不能传任意工具列表。计划预算/依赖和所有前后保护不变，失败/超时/状态变化沿用原停止规则。

```powershell
python -m cadkin execute-evidence-batch outputs/plan.json --output outputs/batch-01.json
```

未完成则下一批加`--previous-execution <上一批execution_source.path>`，换新output；不是换计划、增加采集轮次或从第一步重来。CLI与MCP同一实现。

返回字段：

- execution_source：最后有效的原格式receipt及哈希，继续/回填的实际输入。只有execution_complete且guards_passed才允许复用，eligible_capture_ids为空时没有可回填的完整观测。
- batch_report_source：完整计时/每步receipt列表/错误文件，仅诊断；不能传作execution_path。
- continuation：continue传前述receipt续跑；complete检查保护；blocked停止，先核对已保存状态。TIMEOUT/OUTCOME_UNKNOWN时可能已有CAD操作仍在完成，不能自动重试。
- performance：本批耗时、CAD工具调用耗时之和、编排/校验耗时、步数和客户端调用次数。工具耗时包含参数验证、STA等待、适配器与COM，不等于纯API时间；失败工具调用也计数。不包含agent思考/网络/UI。
- observation_error_codes：快速定位原始失败；详情在receipt绑定的envelope。不反复读取全部历史。

时间预算只在步骤之间检查，不会取消正在运行的COM调用；极慢单步仍按原180秒超时并标不确定。项目OpenCode timeout=300000ms留给默认预算和单步调用；不是靠增加预算重试。如果改了MCP --timeout，需相应核对客户端上限。

批次独占本进程的CAD调度，其他CAD请求返回BUSY，不排队；离线分析仍可独立进行。取消MCP请求会将worker标为不确定，后续CAD步骤不执行；保存的未完成记录不自动复用。不要用并发“加速”同一SolidWorks会话。

已存在最新document token就继续使用，由工具验证；不要每次动作前都重新session_status/list_tools。开模型/切配置/状态报错后才刷新上下文。完整空间清单、空配合、已增强失败和已有index要复用；需要新证据才采集。计时若以工具耗时为主，再检查SolidWorks对话框/几何规模；以编排为主再检查来源重放，不凭感觉扩大扫描。
