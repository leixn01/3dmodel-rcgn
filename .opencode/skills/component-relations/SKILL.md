---
name: component-relations
description: 根据已导出的装配空间清单和圆柱证据，生成同轴、平行的组件几何关系候选。用于“分析这些零件的轴线关系”“找同轴件”“继续分组后的关系分析”；保留公差、来源和未知项，不自动认定机械连接或运动副。
---

# 组件关系候选

1. 先明确分析范围，优先一条升降链上的 2–5 个具体叶实例。读取已有空间清单与圆柱原始 JSON；需要采集时分别复用 component-spatial、component-cylinders 流程，工具参数以仓库根目录 docs/TOOL_CONTRACTS.md 为准。采集期间保持同一会话、文档、配置和几何不变，不为本任务移动、重建、切配置或保存模型。
2. 用 spatial-export 的完整清单作为基准；单页不是完整输入。每个实例仅用一份 sw_component_cylinders 原始返回，保留 errors、raw_array 和变换，不能根据聊天摘要重新编数值。发生 EVIDENCE_MISMATCH 时核对文档/配置/实例/变换，重新采集一致证据，不修改 JSON 来消除报错。哈希与变换匹配不证明几何期间未改变。
3. 明确 distance_tolerance_mm 和 angle_tolerance_deg。优先使用用户或项目已有公差；仅做探索且没有公差时，可先使用 0.1 mm、0.1°，在记录和回答中明确这是探索参数而非制造/装配精度要求。必要时另写新文件做敏感性比较，不根据希望得到的运动副调参数。工具必须显式传入这两个值；角度范围为大于 0 且不超过 5°。
4. 调用 cad_component_relations，必填 inventory_path、cylinder_paths（2–32 个文件）、output_path（outputs 内新 JSON）、两项公差。可选 grouping_path 仅关联同一 inventory_sha256 的角色记录；无分组文件也能分析。默认 max_pairs=10000、max_candidates=1000；这是离线工具，不连接 SolidWorks。CLI relations 调用同一实现，不在 skill 中另写算法。
5. 读取输出文件，不只看工具摘要。列出完整实例路径、候选类型、angle_deg、axis_offset_at_reference_mm、reference_root_mm、来源文件/哈希、body_index/face_index 和角色状态。轴向正负等价；偏移是在两实例原点中点附近投影比较，两轴不严格平行时并非整个面长度上的最大偏移。
6. coaxial_candidate 仅表示角度和局部参考偏移都在阈值内；parallel_candidate 表示角度在阈值内但偏移超限。无限轴相符不证明有限面重叠、接触或孔轴配合。分割圆柱面保留多条证据对，不把记录条数称为机械连接数；同文件的不同实例不能合并。
7. 区分输入缺失与计算截断：complete=false 或 status=partial 要保留 source errors；comparison_complete 仅覆盖提供文件中的面；truncated=true/RELATION_LIMIT 表示仍有未比较对。先缩小实例范围、或核对后调整预算写新文件；没有候选、零圆柱面或未提供实例都不能推断“没有运动关系”。不能描述为整机关系分析完成。
8. 保留 requires_review=true、mechanical_relation_confirmed=false。角色复核不能替代连接复核；不把原始 MateEntity 参数当根坐标进行拼接，也不把 IsFixed 或几何同轴直接改写成旋转副/直线副。按 0.7.0 验收，让用户核对真实模型中的候选及零件定义/装配切除差异，列出下一步需要的配合活动状态、坐标上下文和接触证据。

实现位于 cadkin/tools/relations.py；验收见仓库根目录 docs/MCP_ACCEPTANCE.md 的 0.7.0 部分。新结果保存在 outputs，不覆盖输入、不提交用户工程或派生数据。
