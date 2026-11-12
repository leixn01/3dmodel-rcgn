# 搜索细节

工具必填target_graph_path、output_path。可选template_ids（1–8个）；不传则使用6个reference，两个无关节项会在reference_coverage中说明未生成模式。include_heldout默认false；即使显式给测试ID也需要true，结果记录heldout_exposed。

参数：pattern_size=3（2–6，目标可用节点不足时缩小并记录effective_pattern_size）、max_candidates=5（1–20）、max_states=20000（1–100000）、beam_width=50（1–1000）、angle_tolerance_deg=10（0–45，不含0，探索性排序参数）。参考窗口是若干启用刚体及其内部支持关节形成的连通子图。映射一对一，所有目标节点须通过正向证据连通；不随意填入无证据节点。世界/静态端点不映射，原模板边界关节保留为未匹配上下文。一个模板刚体对应多零件的情况仍待后续分组能力。

分数=max(0,0.7×平均连接支持+0.3×包含覆盖率的轴向关系符合度−额外联系惩罚)。连接支持及风险来自目标图。轴向检查比较两条参考关节轴的无向夹角与两条目标几何轴的夹角，fit=max(0,1−角差/angle_tolerance_deg)；缺失/多义方向记0，不自动选择有利方向。相对角不依赖整体旋转，但不能证明统一坐标对齐。额外联系惩罚为0.1×其支持之和/映射节点的潜在对数。

关节类型本身不由上述证据评分；joint_hypotheses.kind_basis=reference_template_only。limits和axis_origin_m留空，joint_axis_verified=false。不得称“0.8分即80%正确”。角色、名称、尺寸不贡献分数；实例ID只决定稳定排序，在预算截断时顺序会影响搜索覆盖。

搜索为每个模式分配状态预算，按部分连接证据保留beam，再评完整映射。search_exhaustive只说明选定范围和窗口内没有状态/beam截断，不代表全机证明。output_truncated表示已发现的候选只返回前N条；best_score_ties_found与template_rankings保留竞争解释。ambiguous只是排序歧义标志，即使false也没有机械确认。

cad_compare_mechanism_graphs用于已知对应的两份机构图定量比较；本工具输出是假设报告和模板窗口映射，不是该比较工具要求的body_correspondence或目标关节真值，不能直接传入制造“识别率”。

EVIDENCE_MISMATCH重建改变的来源/目标图；HELDOUT_TEMPLATE在普通任务改用参考库；MATCH_SEARCH_LIMIT保存现有结果并说明未搜索范围；NO_SUPPORTED_MATCH保留未知，可自动缩小窗口/补采必要证据后重试，不要求用户机械判断。

CLI：`python -m cadkin match-templates outputs/target.json --template-ids gas_lift_bar_stool bench_vise --output outputs/matches.json`。
