---
name: cad-intake
description: 检查 STEP 或 ZIP 模型的文件清单、来源、校验值和 STEP 文本统计。在用户要求模型体检、确认输入内容或排查损坏时使用；不负责 SolidWorks 连接、装配实例导出或运动推断。
---

# 输入体检

输入：STEP/ZIP 文件或固定来源配置。输出：原始文件的格式、清单与校验信息。

1. 确认用户给的是已有文件还是下载来源；已有 STEP 不重复下载或解压。
2. 调用 cadkin 的 inspect/fetch 共享工具，保存实际清单；不通过文本数量推断 SolidWorks 实例数或运动关系。
3. 只提交指定样例，用户工程与派生输出留在 outputs。

仅在不确定参数、字段含义或遇到失败时读取 [细节与分支](references/details.md) 的对应段落；常规调用按 MCP Schema，不预加载参考文件或其他 skill。引用其他能力时只交接所需输入/输出。
