# MCP 使用效率（0.25.0）

本轮从代码确认了调度开销：已有计划由agent逐个调用sw_execute_evidence_task，每次返回累计records。9步计划需要9次模型/工具往返，多轮会重复读入增长的JSON。当前没有用户本机逐次耗时记录，所以不能断言SolidWorks API本身是主要瓶颈。

## 已实现

sw_execute_evidence_batch在一次外部调用内串行复用原单步工具。默认最多12步、30秒软预算，允许1–20步、1–60秒；预算仅在步骤之间检查。每步仍保存原始envelope/receipt、验证源哈希、文档/位姿和停止条件。批次不会删除保护、自动重试、不增加采集预算或轮次，也不合并不同快照。

返回紧凑摘要与两个路径：execution_source是最新原格式receipt，可用于续跑/回填；batch_report_source是详细计时报告，不是执行输入。完整原始记录继续存盘。新链求解也只返回摘要，需要具体方向/证据再按路径读文件。MCP保留text和structuredContent兼容格式，不靠删掉兼容字段掩盖上下文体积。

同一进程的CAD调度在整个批次内独占；其它CAD请求BUSY且不排队。COM仍在原STA串行线程。取消请求后worker标不确定，后续调用不会入队；已在运行的COM仍可能完成。原180秒单工具超时不改；OpenCode客户端上限调为300000ms，为批次软预算和一个慢调用留余量。时间预算不是硬期限，不应据此盲目重试。

## 量化验收

```powershell
python scripts/verify_mcp_efficiency.py --output outputs/verify-speed-0.25
```

官方SDK/真实stdio，两份显式合成CAD夹具分别走单步和批次；比较完整状态/保护/原始返回（独立采集时间戳和项目根路径除外），检查实际返回字节及客户端往返数。完整调用参数、响应、receipt和比较报告存盘，10项检查。

本轮本地一组记录：

| 指标 | 单步 | 批次 |
|---|---:|---:|
| MCP工具调用往返 | 9 | 1 |
| 必要CAD工具调用 | 9 | 9 |
| 完整通过的保护/有效采集 | 8 / 1 | 8 / 1 |
| MCP结果序列化字节 | 63,450 | 2,716 |
| 返回量减少 | — | 95.7% |

字节数包含CallToolResult两种兼容内容，随路径/计时文本略变；不是token精确计数。合成后端下这次测量约0.212s/0.186s，**不能解释成用户实机速度提升比例**，也未模拟agent思考/网络延迟。复跑测得约0.208s/0.236s，批次墙钟时间也可能略慢；验收不要求不稳定的加速倍数，只要求调用语义相同、往返和载荷减少。

## 实机定位

每批保存performance.elapsed_seconds、tool_elapsed_seconds、orchestration_elapsed_seconds以及逐工具tool_timings。CAD工具耗时包括验证、STA等待、适配器/COM，不是逐个SolidWorks API的纯耗时；失败的工具调用也计数，不等于API实际执行次数。计时不进入证据或机械判断。

- 工具耗时为主：定位最慢的sw_*，结合模型规模、几何数量和软件对话框判断。已发现连接检查会重复枚举进程；本轮保留现有会话一致性检查，待本机计时确定贡献后再优化，不能直接称它是瓶颈。
- 编排/校验为主：检查来源文件数量、大小和重放路径。已有单次只读字节缓存、计划缓存继续校验内容哈希，不引入跨调用的陈旧CAD缓存。
- agent间隔为主：使用批次和摘要；不要逐步list_tools/session_status，不反复读取全历史。原token由每个实际工具校验，文档变化/报错时再刷新。

空间清单分页一次收齐再离线用；已有完整空配合也是可复用观测。增强失败、已完成面探测和4轮停止不能因为换批次而重新采集。仅在具体缺口需要时调用SolidWorks；工具、流程说明和结果解释保持分离。

后续依据实机报告再考虑进程枚举、COM成员访问和几何分页成本；本版没有宣称降低SolidWorks内部重建/几何计算耗时。

协议依据：[MCP Tools 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)，兼容返回保留序列化text与structuredContent。

## Windows首次数值调用卡住

0.24两组Windows CI都在首次局部数值MCP测试超过120秒，而CLI/数学测试通过。此路径与NumPy在已有后台stdin读线程时首次加载原生库的已知问题一致：[NumPy #24290](https://github.com/numpy/numpy/issues/24290)、[MCP Python SDK #2832](https://github.com/modelcontextprotocol/python-sdk/issues/2832)。这是结合日志与上游复现作出的定位，未取得本CI进程的原生线程栈。

0.25把NumPy及一次最小SVD初始化移到create_server、stdio开始后台读管道之前。没有修改数值算法、全局BLAS环境变量或原120秒协议测试期限。Windows CI增加优先冷启动检查，先验证该回归及新批次→回填→链求解流程，再跑全量回归；结果以本版Actions为准。
