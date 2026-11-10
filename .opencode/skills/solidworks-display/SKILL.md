---
name: solidworks-display
description: 显示或隐藏 SolidWorks 当前模型的基准面、基准轴、临时轴、草图、原点和坐标系，或查询这些显示开关。在用户说隐藏基准面、清理辅助线或恢复辅助对象显示时使用；不隐藏零件、不删除特征。
---

# 辅助对象显隐

1. 调用 `sw_active_document` 确认当前零件或装配，取得 `document_token`；从实际 MCP 工具目录确认显示工具可用。缺少工具时按使用说明更新依赖并重新启动 OpenCode 的 MCP 进程，不重写已有工具。
2. 调用 `sw_get_display_state` 记录原有类别开关及 `hide_all_reference_geometry`。用户只要查询时到此为止。
3. 调用 `sw_set_display_visibility(expected_document_token=..., target=..., visible=...)`。隐藏基准面用 `target="planes", visible=false`；显示用 `true`。其他 target 为 `axes`、`temporary_axes`、`sketches`、`origins`、`coordinate_systems`。多个类别逐个调用，只处理用户要求的类别。
4. `all_reference_geometry` 对应“隐藏所有类型”总开关（也涉及注解等对象）。仅在用户明确要求时使用；`visible=true` 解除总屏蔽，但不改变各类别原有开关。单类显示遇到 `DISPLAY_BLOCKED` 时说明总开关遮挡，不擅自显示其他类别。
5. 再读显示状态核对目标类别；报告是否发生变化及回读结果。窗口可访问时检查实际画面，否则说明视觉效果待核对。重复隐藏应保持隐藏，不使用盲目切换。
6. 此工具设置整个文档的类别过滤，支持零件和装配。用户指定某一基准面/草图时，不扩大成隐藏全部同类对象；说明目前不支持单个特征显隐。显示类别不会强制显示已单独隐藏的特征。

不保存、不删除、不重建或切换文档。操作 token 过期时重新读取；超时不盲目重试。精确返回字段和错误见 [工具约定](../../../docs/TOOL_CONTRACTS.md)。
