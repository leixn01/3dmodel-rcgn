---
name: joint-draft-compare
description: 重放并比较补采前后的关节草案检查，说明候选、发现及覆盖范围的变化。用于评估新证据带来的影响；区分仍存在、新出现和本次未再观察到，不把条目消失当机械问题解决。
---

# 比较前后草案

输入：两个原始draft check及全部绑定来源。输出：新的比较报告。

1. 调用cad_compare_draft_checks，传before_check_path、after_check_path、output_path。缺少补采后的检查时交接evidence-reintegration。
2. 先核对settings_equal、occurrence_scope_equal和coverage，再解释findings/candidates变化；同名实例的身份与位姿变化会被拒绝。
3. 报告newly_observed、still_observed、no_longer_observed和changed；解释具体项时读取before_findings/after_findings及before_candidates/after_candidates。
4. 不声称风险已经解决或识别率提高。比较细节按需读[差异解释](references/comparison.md)，结论保留未确定项。
