---
name: joint-draft-check
description: 重放关节草案及来源，检查实例归属、关节两端、锁定与运动假设冲突、轴向差异和竞争解释。用于草案一致性检查与定位风险；不采集CAD、不生成补采计划、不确认运动学。
---

# 草案一致性检查

输入：cad_draft_joints原始落盘文件和全部可回读来源。输出：outputs下新的draft check文件。

1. 调用cad_check_joint_draft，传joint_draft_path、output_path；缺少草案交接mechanism-joint-draft，默认不加载模板。旧algorithm_version=1可按旧规则重放；如要消除模板类型继承，应从同一rigid source生成新版目标证据基线。
2. 分开报告structural_checks_passed与physical_consistency_verified；结构检查通过不代表刚体/运动可行。区分evidence_conflict、uncertainty、coverage与structural_error。
3. 报告findings的来源实例对、candidate_refs、summary与output_truncated。TARGET_JOINT_TYPE_UNDETERMINED是目标类型未知，模板未启用不是错误。可选参考类型之间的差异只是竞争解释，不能当目标约束；锁定与参考运动类型冲突也不是求解器结论。
4. 需要补采计划时只将原始check路径交接evidence-task-plan。无法消除的风险保留在结论，继续可独立处理部分，不等待人工复核。

字段、截断和失败分支按需读[检查细节](references/checks.md)。
