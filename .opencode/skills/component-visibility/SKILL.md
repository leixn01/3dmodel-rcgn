---
name: component-visibility
description: 按完整装配实例路径隐藏、显示或查询一个 SolidWorks 组件，检查父装配遮挡。在用户要求隐藏某个零件或恢复显示组件时使用；不执行抑制、删除、移动、配合编辑或多实体零件的实体显隐。
---

# 组件显隐

1. 用 `sw_active_document` 确认当前装配并取得 `document_token`；零件文档中的实体不作为组件处理。
2. 从最新 `sw_component_tree` 取得目标完整 `occurrence_path`；相同文件的不同实例分别处理。用户简称对应多个实例时列出候选，不猜测，也不批量隐藏全部实例。不能使用 `@unreadable/...`。
3. 调用 `sw_get_component_visibility(expected_document_token=..., occurrence_path=...)`，记录原始自身可见状态和隐藏父路径；只查询时到此为止。
4. 按明确请求调用 `sw_set_component_visibility(..., visible=false或true)`，再查询回读。操作无需先选择组件，不改变当前选择。恢复此前状态时使用记录值，不一律设为 true。
5. `PARENT_HIDDEN` 表示显示子组件仍被父级挡住；报告具体父路径，只有用户要求显示该父级时才修改它。抑制、轻化或未解析的目标/父级报错时，不擅自解除抑制或解析。
6. 报告实际实例路径、回读状态和是否保存（工具不保存）；窗口可访问时核对画面，否则说明尚未视觉核对。显示标志不等于没有遮挡或一定出现在当前视野。

仅改变显示属性，不改几何/位置；隐藏子装配会影响其子件的可见画面，不逐个改写子件属性。文档或配置变化后重新获取 token 和实例树，超时不盲目重试。错误与参数见 [工具约定](../../../docs/TOOL_CONTRACTS.md)。
