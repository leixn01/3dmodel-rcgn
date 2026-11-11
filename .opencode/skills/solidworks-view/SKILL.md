---
name: solidworks-view
description: 调整 SolidWorks 当前模型的标准视图与缩放，在用户要求等轴测、正视、俯视或适合窗口时使用。不改变零件位置或装配关系。
---

# 视图操作

输入：目标文档 token 和明确的视图请求。输出：API 返回与待核对的窗口效果。

1. 指定标准方向时调用 sw_set_view；只要求适合窗口时调用 sw_zoom_to_fit。
2. 检查 token 和工具返回，窗口效果需要核对；不把 API 成功冒充截图/视觉证明。
3. 不修改选择、显隐、配合或模型几何。

仅在不确定参数、字段含义或遇到失败时读取 [细节与分支](references/details.md) 的对应段落；常规调用按 MCP Schema，不预加载参考文件或其他 skill。引用其他能力时只交接所需输入/输出。
