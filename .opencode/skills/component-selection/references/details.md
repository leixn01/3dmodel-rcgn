# 组件选择

1. 读取 `sw_active_document` 确认目标；选择组件需装配文档。取得当前 `document_token`。
2. 选择时从最新 `sw_component_tree` 结果取得完整 `occurrence_path`。同名文件的多个实例分别处理；路径不明确时列出候选，不靠简称猜测。`@unreadable/...` 不能作为选择目标。
3. 调用 `sw_select_component(expected_document_token=..., occurrence_path=...)`；该工具替换现有选择并回读核对。清空选择则调用 `sw_clear_selection(expected_document_token=...)`。
4. 报告实际实例路径和选择数量；需要视觉确认时核对窗口高亮，无法访问窗口则说明尚未视觉核对。

重建/编辑后重新读取组件清单。错误处理见 [工具约定](../../../../docs/TOOL_CONTRACTS.md)。本流程只操作选择状态。
