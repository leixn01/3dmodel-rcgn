---
name: component-selection
description: 按装配组件树中的完整实例路径选择、高亮一个 SolidWorks 组件，或清空选择。适用于定位具体零件实例；不移动、删除、隐藏组件或修改配合。
---

# 组件选择

输入：明确选择任务、完整实例路径与文档 token。输出：选择数量和目标回读。

1. 选择一个实例调用 sw_select_component；明确清空请求调用 sw_clear_selection。
2. 核对回读，使用实例路径而非零件文件名；不把选择当作几何或运动关系证据。
3. 不移动、隐藏、解析或修改配合。

仅在不确定参数、字段含义或遇到失败时读取 [细节与分支](references/details.md) 的对应段落；常规调用按 MCP Schema，不预加载参考文件或其他 skill。引用其他能力时只交接所需输入/输出。
