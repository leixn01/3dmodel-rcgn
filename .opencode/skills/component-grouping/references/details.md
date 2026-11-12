# 分组细节

输入完整空间清单；工具cad_group_components必填inventory_path、output_path，可选scope_occurrence_path。范围使用实际实例完整路径；不确定时先输出候选范围，可从整机角色候选开始，不把子装配或“三独立”名称直接当运动链。

通过角色规则与空间证据生成候选，保留pending和冲突；叶实例为单位，重复文件实例不能合并。缺包围盒时可完成名称候选，结果需说明空间信息缺失，之后按需补充几何或配合。

默认不调用人工复核。旧review_path只是兼容既有明确意见文件；自动流程不生成、索要或等待它，不把自己的推断伪装成manual_confirmed。requires_review是证据待核对标志，交给后续自动分析，最终报告未知与风险。

执行代码在cadkin/tools/grouping.py；详细旧接口保留在docs/TOOL_CONTRACTS.md。新一轮拆解方向见docs/DEVELOPMENT_PLAN.md，常规任务不必加载整份文档。
