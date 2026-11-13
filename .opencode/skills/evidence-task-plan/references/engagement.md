# 表面补证分支

有原始engagement报告时传engagement_analysis_path，与所有其它profile互斥。v8计划沿用报告exact index；新索引先重算报告，不直接替换。只安排唯一完整boundary上的缺失采样/邻接，每面每工具去重；已有partial/failed也不再采。

采样是明确根坐标点，一面最多32点、容差min(来源距离容差,0.01mm)；邻接默认最多64边。不删文档或位姿保护：两个实例两面4capture+6guard=10调用；max_tasks不足保留deferred。

交evidence-task-execute批次执行，完成后同check索引，再原finite报告+最新index重算surface-engagement-analysis。全部来源、失败、遗漏和共享四轮保持；stop并不等于配合/运动已识别。缺完整boundary回finite-connection-analysis；不要加载全部采集skill或自动重扫装配。
