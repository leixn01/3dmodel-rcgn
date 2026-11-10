---
name: solidworks-view
description: 调整 SolidWorks 当前模型的标准视图与缩放，在用户要求等轴测、正视、俯视或适合窗口时使用。不改变零件位置或装配关系。
---

# 视图调整

1. 用 `sw_active_document` 确认目标，取得当前 `document_token`。
2. 只要求适合窗口、不改变当前方向时，调用 `sw_zoom_to_fit(expected_document_token=...)`。需要标准视角时调用 `sw_set_view(expected_document_token=..., view=..., fit=...)`；默认 `isometric`、`fit=true`。支持视图值见 [工具约定](../../../docs/TOOL_CONTRACTS.md)。
3. 报告请求的视图和工具结果。API 完成不等于已看见正确画面；能访问窗口时核对，否则明确留待用户核对。
4. 文档变化时重新读取目标。超时按工具错误指引检查现场，不盲目重试。

选择高亮由独立组件选择功能负责；不调用移动组件、配合或保存操作。
