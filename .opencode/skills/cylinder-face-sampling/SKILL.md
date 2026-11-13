---
name: cylinder-face-sampling
description: 对有原始有限边界的指定圆柱面读取有限查询点成员关系与朝向法向。用于区分采样内外表面、角向裁剪缺口；只读单面，不判定完整圆周、轴孔配合或运动副。
---

# 圆柱面有限采样

输入：完整原始boundary envelope、当前token与明确根坐标测点；输出：原始采样envelope。

1. 先读[参数与来源](references/capture.md)，调用sw_sample_cylinder_face；不凭名称或模板猜面、角度或测点。
2. 若来自补采计划，交evidence-task-execute运行原计划，原返回自动保存和绑定。手动单次读取不能冒充已有保护receipt；离线分析只消费索引中的有效观测。
3. 只把成功点的membership_at_query理解为给定容差下的点成员关系；solid_surface_side是该点材料侧，sheet_orientation_only不能解释为轴或孔。
4. partial、未命中和未知完整保留，交surface-engagement-analysis解释；本能力不创建关系或求解运动。

不改变选择、可见性、位置或文件。所有点命中也不证明点间区域存在，不算整圆比例，不设人工复核。
