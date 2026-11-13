---
name: face-adjacency
description: 从指定圆柱面解析边逐边读取真实邻面，保留缝边、空邻面、持久面身份及同体核对。用于端面邻接证据；不推断其它组件接触、轴向保持或限位。
---

# 面拓扑邻接读取

输入：完整原始boundary envelope、当前token；输出：有界原始邻接envelope。

1. 按[邻接读取](references/capture.md)调用sw_read_face_adjacency；计划内任务交evidence-task-execute，避免另起重复读取。
2. 保留每条边两槽中的null、重复选中面、邻面身份及descriptor，不把圆柱缝边当成端面，也不只按坐标猜邻接。
3. 遇partial或失败仍保存原返回，按原计划继续允许的独立任务和保护；索引中保留尝试。已有同面同工具尝试不自动换预算重试。
4. 成功结果交surface-engagement-analysis离线解释；这个能力只读取拓扑，不生成几何运动约束。

同体共享边不证明跨组件接触，也不证明挡肩、止推或行程；风险留在结论，不设置人工复核。
