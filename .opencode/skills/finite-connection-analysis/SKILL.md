---
name: finite-connection-analysis
description: 从几何解释报告及其最新观测索引分析有限圆柱面轴向范围和轴向局部平面样点。用于无配合模型的配合范围缺口；离线列出范围分离、重叠或端点接近，保留未知运动类型与限位。
---

# 有限连接范围分析

输入：原始geometry report和已有历史的最新index；输出：紧凑摘要与完整finite报告。

1. 调用cad_analyze_finite_connections，传geometry_analysis_path、output_path；有采集历史传evidence_index_path，max_face_pairs可限输出。先按[来源规则](references/inputs.md)核对同target及历史延续。
2. 先读coverage和analysis_source，只在解释具体实例/面时读取pairs；依据[结果判读](references/interpretation.md)区分轴向范围与真实啮合、行程。
3. 缺少已有候选面的边界时交evidence-task-plan，传finite_analysis_path及同check；按[补采衔接](references/followup.md)交接批次执行、索引，再重算finite报告。
4. 缺面目录只交已有face-probe-plan；其需要真实测距见证及最新索引。缺距离先回geometry分支，缺原始轴线先交component-relations。不猜face ID、不扫描目录补历史。
5. 保留源报告的解释、缺口、遗漏与失败记录，不更改原草案，也不传给原生运动求解器。

不为离线分析启动CAD。结论说明无法验证的啮合、角向覆盖、轴向保持、有限运动与行程；不设置人工复核。
