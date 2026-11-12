# 差异解释

cad_compare_draft_checks必填before_check_path、after_check_path、output_path。输出draft_comparison_schema_version=1。CLI：`python -m cadkin compare-checks outputs/check.json outputs/updated-derived/check.json --output outputs/comparison.json`。

两份check及其完整draft/rigid/target/chain来源重新计算；修改派生状态或来源会被拒绝。文档、配置或共有实例的文件/父级/位姿不同，不能作为仅补证据的更新比较。允许不同分析范围但报告COMPARISON_SCOPE_CHANGED，不将变化归因于补采。

候选按template_id及“参考body → 实际成员列表”的局部映射标识；跨分组相同局部映射在比较中合并，完整方案仍在原草案。changed包含分数、轴线或来源引用等变化；不是自动判定更准确。原始候选及发现内容随报告保存，避免只有无法定位的摘要ID。

参数、公差、模板、分组预算相同，也不保证证据改变后遍历到同一候选空间。检查截断报COMPARISON_FINDINGS_LIMIT；搜索/输出覆盖和旧新计数一起解释。no_longer_observed只能表述本次返回范围没有再观察到，不能写“已经解决”。resolved_findings_asserted与mechanically_verified始终false。

没有自动开始下一轮补采，不因为不确定项仍存在反复调用相同扫描。运动、副类型、行程、自由度、碰撞和拆卸可行性仍需对应后续能力。
