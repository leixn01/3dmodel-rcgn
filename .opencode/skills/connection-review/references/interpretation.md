# 判读与失败分支

| review_state | 解释 |
| --- | --- |
| has_unsuppressed_mate_evidence | 该实例对有引用均映射成功、未抑制/未回滚且没有报告特征错误的配合记录；不是求解有效性或运动副确认 |
| only_suppressed_or_feature_issue | 关联配合只有抑制、回滚或特征错误/警告记录，不能作为有效连接依据 |
| unresolved_mate_evidence | 有关联线索，但引用映射、字段或活动状态不完整 |
| geometry_only | 提供的根配合清单中没有可关联到这一实例对的证据；不是“无连接”或“可自由移动” |

面核对错误另保留在 face_matching_errors，不把已读到的配合状态改成未知；整体仍保留 partial。优先级只用于汇总显示；同一个实例对的所有关联配合状态仍保留，不删除被抑制/报错记录。几何的多个圆柱面配对归于一个 occurrence_paths 实例对，geometric_candidate_indices 回指原关系文件；不能拿面配对数当机械连接数。

关联仅发生在恰有两个经确认引用实例的配合与对应候选对之间。含根/未知引用的记录不能升级为无问题配合；多组件配合保留在 unmatched_mates，不猜成多条两件连接。根装配配合可以引用嵌套零件，但不代表子装配内部配合已覆盖。

完整来源哈希在 sources；关系文件还绑定原空间/圆柱文件，文件须仍存在。匹配根变换不证明几何期间未变，仍需稳定会话采集。普通根配合输入只给 association_level=occurrence_pair_only、face_match_confirmed=false。若输入 sw_match_mate_faces，只有两个实体分别核对到候选的准确面且源哈希一致时，才给 candidate_face_pair/face_match_confirmed=true；candidate_face_matches 逐条列出几何候选索引和左右实体索引。多个实体的配合不降成两面对应；配合抑制/错误状态仍独立保留。

- SOURCE_INCOMPLETE：保留原错误；即使某对有清楚记录，总体仍为 partial，不能推广到缺失范围。
- EVIDENCE_MISMATCH：来源被改、文档/配置/位姿/坐标范围不符。核对真实记录并重新采集，不能手工改哈希或变换。
- INVALID_CONNECTION_SOURCE / INVALID_INVENTORY：文件格式/范围错误；不要将组件 GetMates 返回冒充根配合清单。
- INVALID_FACE_MATCH_SOURCE：面证据缺少有效来源，或圆柱文件与关系文件不一致；核对并重采/重算，不改写 ID、索引或哈希。
- OUTPUT_EXISTS / INVALID_PATH：选择 outputs 内新文件，不覆盖或写出项目。

CLI 与 MCP 共用实现：python -m cadkin review-connections <relations.json> <mates.json> --output outputs/<新名称>.json。不要在 skill 中重写关联算法；缺少实体级几何、求解或接触证据时只列下一步待核对项。
