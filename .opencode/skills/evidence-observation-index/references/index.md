# 索引细节

cad_index_evidence必填draft_check_path、execution_path、output_path；max_contexts默认200、范围1–2000，控制返回的关节上下文数，不截断已收录观测。工具不连接CAD；可用CLI：

```powershell
python -m cadkin index-evidence outputs/update-0.17-derived/check.json outputs/run-0.17.json --output outputs/index-0.18.json
```

原receipt必须execution_complete=true且guards_passed=true。工具重放计划、check、来源和原始envelope；当前check可来自回填后的草案，但文档token/path/title/type/configuration/dirty和全体实例身份/位姿/范围必须一致。变化则重新收集空间快照并重建依赖，不能替换旧哈希或token。

observations每条包含source、execution_source、task_id、family、occurrence_paths、state、codes、usable和details。仅完整且通过校验的观测usable=true。失败或partial保留为尝试，供规划阻止相同工具/实例范围自动重试；更改预算不绕过此规则。完整空结果也复用，不把没有配合/面当成没有机构。

单实例约束关联到该实例以及包含它的候选。reference_component_names只保留名称，reference_names_resolved_to_occurrences=false；不能据此判定另一个根实例或配合活动状态。固定标志是当前装配配置的约束。全部端点成员均有一致的顶层fixed=true时，运动假设附FIXED_MEMBERS_VS_MOVING_HYPOTHESIS提示，不自动删除候选；缺少成员或相互矛盾的固定记录保持未知。

面目录保留源文件绑定、body_index/face_index、面类型、是否保存引用；这些索引仅定位该份文件。pair_contexts和joint_contexts说明哪些端点具有目录，不选具体配对面、种子或接触关系。后续真实面身份与有限面测量交接独立能力。

新执行计划若引用已有索引，新索引会继承该来源链，并重新关联到当前候选。最多4轮自动补采；只有显式传入的链可知，不扫描outputs找其他历史。文件重放限制12层、512个来源文件和128MiB；循环/过深来源拒绝。始终保留原文件、模板曝光记录与失败尝试。

EXECUTION_NOT_COMPLETE/EXECUTION_GUARDS_FAILED禁止复用；EVIDENCE_MISMATCH禁止混合快照；ASSOCIATION_CONTEXT_LIMIT表示候选/发现关联不完整；OBSERVATIONS_NOT_REUSABLE保留失败/部分尝试；OUTPUT_EXISTS换新文件。记录限制与剩余不确定性，不以成功创建索引声称拆解完成。
