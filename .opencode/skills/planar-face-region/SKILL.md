---
name: planar-face-region
description: 读取真实邻接端面的闭合有限轮廓，支持完整圆盘、同心单孔圆环和无孔凸直边多边形。用于核对端面实际区域；绑定邻接原始来源，复杂形状保留未知，不确认接触或限位。
---

# 端面有限区域读取

输入：完整原始adjacency envelope、其真实平面邻面持久引用和当前token；输出：原始有界loop envelope与支持形状。

1. 按[读取规则](references/capture.md)调用sw_read_planar_face。引用必须来自该邻接原文，不猜面索引或用坐标造身份。
2. 计划内读取交evidence-task-execute批量执行；保留原始envelope/保护/receipt，不另起直接调用替代历史。
3. 查看complete、truncated、errors和region。partial或不支持形状仍留档，不增加预算重采，不用外圆填掉孔区。
4. 完整结果交planar-contact-analysis离线比较；读取不计算运动约束或移动模型。

不设人工复核；结论说明缺口、数值公差和零件定义不含装配级特征。
