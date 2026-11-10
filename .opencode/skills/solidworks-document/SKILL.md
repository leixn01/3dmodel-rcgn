---
name: solidworks-document
description: 按用户请求在已有 SolidWorks 会话打开或导入 STEP/原生模型，或重建指定活动文档。不负责软件启动、保存覆盖、关闭文档、视图调整或运动分析。
---

# 文档操作

接口见 [工具约定](../../../docs/TOOL_CONTRACTS.md)，安装与样例路径见 [使用说明](../../../docs/OPENCODE_START.md)。

1. 确认请求的是打开/导入还是重建，只执行请求对应的动作。先检查 `sw_session_status`。打开模型任务发现软件未运行时，先使用独立 `solidworks-start` 流程启动并确认 `startup_completed=true`，无需让用户手动提前打开。连接错误时不要通过重复启动绕过。
2. 打开时确认实际输入路径，调用 `sw_open_document(path=...)`。样例 STEP 为 `examples/three_servo_lift/3X Lift Assembly.STEP`，已随仓库提供。直接打开 STEP，不向用户索要解压操作。
3. 检查返回文档、类型、配置与错误。STEP 的导入方式由本机设置决定；导入为零件时不得声称已经获得装配组件树。
4. 重建时先调用 `sw_active_document`，确认任务目标，并将其 `document_token` 作为 `expected_document_token` 调用 `sw_rebuild`。结果不会自动保存，记录 dirty 状态。
5. `DOCUMENT_CHANGED` 时重新确认目标；超时/取消可能留下已执行的操作，检查窗口与结果后重启 MCP，不能直接重复打开或重建。

报告实际执行与未验证部分。当前没有保存、覆盖、关闭或任意宏工具，不为普通操作临时编写绕过工具层的脚本。
