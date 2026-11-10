---
name: solidworks-connect
description: 检查或排查本机已有 SolidWorks 会话，读取版本与活动文档。在用户要求连接、确认当前模型或诊断连接失败时使用；不打开文档、不修改模型或遍历组件。
---

# SolidWorks 会话检查

1. 确认运行在 SolidWorks 所在 Windows 电脑；安装与排错见 [使用说明](../../../docs/OPENCODE_START.md)。当前连接代码已存在，普通使用请求不自动扩展为重写工具。
2. 检查实际 MCP 工具列表，调用 `sw_session_status`；客户端可能添加服务名前缀，按名称和描述识别。协议连接成功不代表 SolidWorks 已连接。
3. 会话可用时调用 `sw_active_document`，报告真实版本、文档标题、路径、类型、配置和 dirty 状态。无活动文档、未运行、多进程与 COM 错误分别说明。
4. 纯状态检查不启动软件。执行打开模型等任务但尚未运行时，交给独立的 `solidworks-start` 流程直接启动，无需用户手动提前打开；再使用独立文档操作功能。连接失败或多实例时不创建额外会话绕过问题，不关闭用户文档。
5. 工具缺失时检查安装与项目配置；只在用户要求开发/修复时改代码。没有 Windows COM 实测就明确说明，不能使用离线 STEP 统计代替。

接口与错误语义见 [工具约定](../../../docs/TOOL_CONTRACTS.md)。
