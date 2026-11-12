---
name: component-proximity
description: 从已有完整空间清单离线生成待测组件对，按近似包围盒筛选测量顺序。用于“没有配合先找邻近零件”“缩小距离测量范围”；不连接 SolidWorks，不把包围盒重叠认定为接触。
---

# 邻近测量候选

输入：包含包围盒的完整空间 envelope、筛选阈值和可选叶实例范围。输出：来源绑定的待测组件对 JSON。

1. 检查空间清单已收齐分页/层级；缺少包围盒时只请求空间采集能力补取，不能补零。
2. 调用 cad_proximity_candidates，显式传 max_box_gap_mm 和 outputs 新文件路径；未知工程阈值时只可明确标注为探索值。
3. 保留 unranked_occurrences、覆盖计数、partial/truncated；候选排序只安排测量，未列出的组件对仍未知。
4. 如需距离证据，交付少量候选完整实例路径给 component-distance；本流程不串行启动整机全部测量。

参数、预算或阈值含义不清楚时读 [参数与范围](references/details.md)；不要预加载其他 skill。验收时读 docs/MCP_ACCEPTANCE.md 的 0.10.0 部分。
