---
name: evidence-observation-index
description: 将已完成且前后校验通过的补采记录关联到当前组件、组件对、发现和关节候选，保存可复用观测与失败尝试。用于补采后整理上下文、继续规划前复用已有证据；只建离线索引，不采集CAD、不回填草案或确认机械关系。
---

# 关联已有补采证据

输入：原始执行receipt、当前draft check及全部来源。输出：outputs下新的evidence index。

1. 若刚完成兼容回填，使用成功回填的after_check_source.path；否则使用仍有效的原check。调用cad_index_evidence，传draft_check_path、execution_path和新的output_path。
2. 读取observations、node_observations、pair_contexts、finding_contexts、joint_contexts及summary。区分完整可复用观测、失败/部分尝试与尚无对应关系；报告来源、截断和风险。
3. 将当前check与索引路径交接evidence-task-plan；需要自动选面和生成有限面探测任务时交接face-probe-plan，要求规划时传evidence_index_path。仅当新计划明确collect才交接执行；stop时报告剩余风险，不反复扫描，也不删除索引绕过历史。
4. 需要准确参数、跨轮来源或关联边界时读[索引细节](references/index.md)。配合引用名称不猜成根实例ID；两个面目录不自动构成接触面。

索引不改变候选分数、不证明刚体/关节或问题解决，不要求人工复核。

索引中的face_probes保留具体面探测与样本量测；pair_contexts.face_pair_selected仅表示曾选定候选去尝试，不表示找到配合/接触面。完整可复用探测可交接face-contact-review解释；当前receipt的兼容探测交接evidence-reintegration更新草案，再重建绑定新check的索引。不能用catalog或failed记录替代，也不能把历史索引当当前receipt批量回填。
