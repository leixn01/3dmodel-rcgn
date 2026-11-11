---
name: component-spatial
description: 读取 SolidWorks 装配组件的位置、局部和整机变换、近似包围盒与尺寸，查询单个实例或导出空间清单。用于“零件在哪里”“读取组件尺寸”“导出装配空间 JSON”等请求；不执行组件移动、配合编辑或运动推断。
---

# 空间信息

输入：活动装配 token 和实例路径，或整机范围。输出：根/父变换、原点、近似包围盒。

1. 单件调用 sw_component_spatial；全量使用 spatial-export 收齐 sw_spatial_inventory 各页，不能把单页用作完整清单。
2. 保持采集期间配置和几何不变；保留 partial、缺失字段和源错误。
3. Transform2 已相对根装配，不再乘父矩阵。原点不是质心，近似盒不能证明接触或碰撞。

仅在不确定参数、字段含义或遇到失败时读取 [细节与分支](references/details.md) 的对应段落；常规调用按 MCP Schema，不预加载参考文件或其他 skill。引用其他能力时只交接所需输入/输出。
