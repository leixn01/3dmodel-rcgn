---
name: component-distance
description: 在 SolidWorks 只读测量两个已解析零件实例的最小距离和最近点。用于“这两个零件相距多远”“验证邻近候选”；可独立调用，不要求配合或圆柱文件，不编辑或选择模型。
---

# 两组件距离证据

输入：活动装配 token 和两个完整零件实例路径。输出：sw_component_distance 原始 envelope。

1. 核对目标为两个不同、已解析的零件实例；保持文档/配置/几何不变，不自动解析、切配置或退出编辑模式。
2. 调用 sw_component_distance，传 expected_document_token、left_occurrence_path、right_occurrence_path。一次一对，保存完整 envelope 到 outputs 新文件。
3. 读取 measurement_status、measurement、errors；失败/空值是未知，不写成零。最近点已经在根装配模型坐标中，不再乘实例变换。
4. 如需候选复核，只交付原始文件给 proximity-review；零或很小的距离不能自动确认接触、干涉或运动副。

解释坐标/单位或遇到失败时读 [字段与失败分支](references/details.md)。不强制先执行近邻筛选，也不加载无关 skill；实机验收读 docs/MCP_ACCEPTANCE.md 的 0.10.0 部分。
