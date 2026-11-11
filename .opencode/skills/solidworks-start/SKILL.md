---
name: solidworks-start
description: 在 Windows 上启动 SolidWorks，或复用已有单个会话并显示窗口、等待启动完成。用户要求打开软件，或执行打开模型等任务但软件尚未运行时使用；不打开文件、不重建或保存模型。
---

# 软件启动

输入：明确需要启动软件的任务。输出：唯一会话的 PID、启动完成状态。

1. 调用 sw_start_application；已有进程优先复用，未运行才启动。
2. 检查 started、startup_completed 与会话结果；许可/恢复对话框和连接失败先核对现场，不新增第二进程。
3. 本功能不打开文档。交付会话结果后，仅按后续任务调用文档工具。

仅在不确定参数、字段含义或遇到失败时读取 [细节与分支](references/details.md) 的对应段落；常规调用按 MCP Schema，不预加载参考文件或其他 skill。引用其他能力时只交接所需输入/输出。
