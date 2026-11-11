---
name: component-visibility
description: 按完整装配实例路径隐藏、显示或查询一个 SolidWorks 组件，检查父装配遮挡。在用户要求隐藏某个零件或恢复显示组件时使用；不执行抑制、删除、移动、配合编辑或多实体零件的实体显隐。
---

# 组件显隐

输入：完整实例路径、文档 token 和 visible。输出：目标自身及父级显隐读回。

1. 先用 sw_get_component_visibility 读取，按任务调用 sw_set_component_visibility，再核对返回。
2. 父级隐藏时不要为显示子件擅自展开全部父级；重复实例按完整路径定位。
3. 不抑制、解析、移动或保存模型。超时结果可能已生效，检查现场后再决定下一步。

仅在不确定参数、字段含义或遇到失败时读取 [细节与分支](references/details.md) 的对应段落；常规调用按 MCP Schema，不预加载参考文件或其他 skill。引用其他能力时只交接所需输入/输出。
