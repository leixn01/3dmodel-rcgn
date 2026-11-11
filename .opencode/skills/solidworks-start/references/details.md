# 启动 SolidWorks

1. 确认 MCP 在安装 SolidWorks 的 Windows 电脑运行，工具目录包含 `sw_start_application`。不要重写工具或临时执行任意启动脚本。
2. 调用 `sw_session_status`。纯状态查询报告结果即可；用户要求启动软件或执行打开模型等任务时，即使尚未运行，也直接调用 `sw_start_application`，不要求用户提前手动启动。已有会话可用时按任务复用它。
3. `sw_start_application` 无必填参数；可选 `wait_seconds` 为 1–120，默认 120。检查 `status=ok`、`connected=true`、`startup_completed=true`、`visible=true`、`user_control=true`，记录 `process_id`、`revision` 与 `started`/`reused_existing`。启动成功可以没有活动文档，不为此创建空白零件。
4. 软件启动后按需交给 `solidworks-document` 打开指定模型，再用 `solidworks-connect` 检查实际活动文档。启动工具不负责文件路径、导入设置、显隐或空间计算。
5. `STARTUP_PENDING` 表示已有会话尚未启动完成；检查本机许可/恢复/插件弹窗，处理后可再次调用启动工具复用该进程。`CONNECT_FAILED`、`MULTIPLE_SESSIONS`、`SESSION_MISMATCH` 或进程查询错误时，不启动另一个实例绕过失败，不关闭用户工程。
6. `APPLICATION_NOT_REGISTERED` 需检查桌面版安装与 COM 注册；使用系统注册的默认版本，不猜可执行文件路径。`START_FAILED`、`START_OUTCOME_UNKNOWN`、`TIMEOUT`、`OUTCOME_UNKNOWN` 不能证明进程没有启动，先核对窗口和任务管理器；超时后重启 MCP，不盲目连续重试。
7. 不自动点击许可/恢复提示，不更改安装或注册，不退出 SolidWorks。退出 OpenCode 后启动成功的 SolidWorks 应保持运行；是否确实可见和保留必须在实机核对。按 [验收清单](../../../../docs/MCP_ACCEPTANCE.md) 的 0.4.0 项记录原始返回与人工结论。

参数、超时和错误语义见 [工具接口](../../../../docs/TOOL_CONTRACTS.md)；安装见 [使用说明](../../../../docs/OPENCODE_START.md)。
