---
name: surface-engagement-analysis
description: 从原始finite连接报告及最新索引汇总圆柱面点成员关系、采样内外侧和实际邻接轴向平面。用于无配合模型的配合假设补证；定向补采、不强制模板、不确认物理关节或行程。
---

# 表面配合假设补证

输入：原始finite report、已有历史的最新index；输出：摘要与完整engagement报告。

1. 调用cad_analyze_surface_engagement，传finite_analysis_path、output_path；有更新索引传evidence_index_path。先按[来源与判读](references/analysis.md)核对来源和已有历史。
2. 优先读coverage、rounds_completed与analysis_source；只有解释具体候选时读pairs/faces。采样内外侧互补只是局部支持，点间裁剪、接触、间隙、保持与运动仍需区分。
3. 有缺失读取时交evidence-task-plan，传engagement_analysis_path和同check；按[取证衔接](references/followup.md)执行批次→索引→重算→停止。无需为每点独立调用MCP。
4. 无完整boundary则回finite-connection-analysis；无目录/测距则沿既有分支补缺。不能绕过共享四轮、改旧文件或丢弃失败历史。
5. 结论保留alternatives、遗漏、未命中、来源错误和未确认事项。目标类型unknown、DOF与行程null，不写入原生约束求解器，也不移动零件。

离线分析不启动CAD；不设人工复核节点。
