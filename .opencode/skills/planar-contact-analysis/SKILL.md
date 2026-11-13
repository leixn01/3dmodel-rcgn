---
name: planar-contact-analysis
description: 使用原始表面补证报告和最新索引，对真实邻接端面的有限区域计算投影重叠与定向平面间隙。用于排除孔区或分离端面的假接触候选；规划缺失区域读取，保持物理接触、轴向保持与行程未知。
---

# 有限端面接触候选分析

输入：原始engagement report及已有历史最新index；输出：摘要与来源绑定planar报告。

1. 调用cad_analyze_planar_contacts，传engagement_analysis_path、output_path；有更新历史传evidence_index_path。按[来源与结果](references/analysis.md)判断范围，默认max_plane_pairs=20可限输出。
2. 优先读coverage、rounds_completed、analysis_source；需要具体说明才展开pairs。未读取、未支持、零可解析面积和有正面积分别说明，不把零面积解释为绝无边接触。
3. 缺有限区域时交evidence-task-plan，传planar_analysis_path及同check；按[补采衔接](references/followup.md)运行批次→索引→重算→停止。数据来源不全先回surface-engagement-analysis，不另造邻面ID。
4. 保留全部alternatives、来源错误/遗漏和失败历史，未确认物理类型/DOF/行程。候选闭合方向不写成求解器约束，不据此移动或拆卸模型。

分析离线、不启动CAD；不设置人工复核节点。
