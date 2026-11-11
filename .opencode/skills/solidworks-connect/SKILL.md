---
name: solidworks-connect
description: 检查或排查本机已有 SolidWorks 会话，读取版本与活动文档。在用户要求连接、确认当前模型或诊断连接失败时使用；不打开文档、不修改模型或遍历组件。
---

# 会话检查

输入：本机 Windows 与已激活 Conda 环境。输出：会话、解释器、活动文档与 token。

1. 调用 sw_session_status，核对实际 Python 路径；有活动模型时再调用 sw_active_document。
2. 区分协议连通与 COM 连通，保留 NOT_RUNNING、多进程与连接错误。纯查询不启动软件。
3. 仅当执行打开模型等任务且软件未运行时，交给启动能力；不关闭用户文档或改写工具。

仅在不确定参数、字段含义或遇到失败时读取 [细节与分支](references/details.md) 的对应段落；常规调用按 MCP Schema，不预加载参考文件或其他 skill。引用其他能力时只交接所需输入/输出。
