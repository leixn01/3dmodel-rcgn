# 失败分支

- FACE_REFERENCE_UNAVAILABLE：旧文件未采集持久引用，或某面引用获取失败。交给圆柱采集能力用 include_face_references=true 补取；生成新关系文件与新匹配文件，不改原有哈希。
- FACE_REFERENCE_UNRESOLVED / INVALID_FACE_REFERENCE：引用无效、已删除、被抑制或格式异常。保留错误；不能用 body/face 遍历编号或几何近似替代身份。
- FACE_CORRESPONDENCE_UNAVAILABLE / FACE_IDENTITY_UNAVAILABLE / MATE_FACE_UNAVAILABLE：无法映射实例面、API 不支持比较或配合引用为空，保持未知，不自动修改/解析模型。
- FACE_GEOMETRY_MISMATCH：解析出的面已不再为原圆柱参数；即使只是参数化变化也保守要求重新采集来源，不能继续用旧关系数值。
- CANDIDATE_FACE_LIMIT / FACE_COMPARISON_LIMIT / MATE_LIMIT 等：保留 partial/truncated 与实际比较数量；缩小实例范围或在稳定会话另取合理预算，不宣称已覆盖未读范围。
- DOCUMENT_CHANGED / COMPONENT_CHANGED / COMPONENT_CONFIGURATION_MISMATCH / GEOMETRY_CHANGED / MATE_REFERENCE_CHANGED：上下文改变或无法最终复核，整次错误结果不能拼接使用。核对后重新采集一致来源；不自动切配置或重建。
- TIMEOUT / OUTCOME_UNKNOWN：COM 可能仍在执行，先核对 SolidWorks，再重启 MCP，不叠加重试。

只覆盖活动根装配配合；子装配内部配合仍缺失。面身份确认不等于接触、求解成功、特征健康或机械运动副；未抑制/无错误的状态与已匹配面证据仍分开报告。
