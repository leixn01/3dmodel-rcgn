---
name: assembly-inventory
description: 读取 SolidWorks 活动装配的组件树，保留重复实例、父子关系及抑制或未解析状态，导出并核对清单。不负责运动推断、组件移动或配合编辑。
---

# 组件清单

输入：活动装配。输出：完整实例路径、父子关系和覆盖信息。

1. 需要时取 sw_active_document；确认 assembly 后调用 sw_component_tree。
2. 同文件的不同实例分别保留，检查 complete/truncated/errors，不把部分树称为完整清单。
3. 保存原始 JSON 到 outputs 新文件；只交付实例路径与上下文，不移动、解析或改配合。

仅在不确定参数、字段含义或遇到失败时读取 [细节与分支](references/details.md) 的对应段落；常规调用按 MCP Schema，不预加载参考文件或其他 skill。引用其他能力时只交接所需输入/输出。
