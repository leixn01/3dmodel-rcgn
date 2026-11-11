---
name: component-constraints
description: 读取 SolidWorks 指定组件的固定或浮动标志、关联配合及配合引用参数，用于“零件是否固定”“有哪些配合”“给分组补充约束证据”。保留嵌套层级与未知状态，不求解自由度、不修改配合、不把无配合当可自由运动。
---

# 单实例约束证据

输入：当前装配 token 和一个完整实例路径。输出：固定标志与 GetMates 原始记录。

1. 调用 sw_component_constraints，保存原始 envelope；已有 JSON 的解释任务只读文件。
2. 嵌套 IsFixed 保持未知；mates=[] 与读取失败分开，不由无配合推出自由运动。
3. 本工具不读配合特征状态，实体坐标上下文未验证。需要根装配配合状态时交给独立 assembly-mates 能力，不在此处扩展职责。

仅在不确定参数、字段含义或遇到失败时读取 [细节与分支](references/details.md) 的对应段落；常规调用按 MCP Schema，不预加载参考文件或其他 skill。引用其他能力时只交接所需输入/输出。
