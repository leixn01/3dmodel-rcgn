# 输入与调用

cad_build_chain_evidence 必填 inventory_path、occurrence_paths（2–50个不同叶实例完整路径）、chain_name（1–100字符）、output_path（outputs 下新JSON）。可选 grouping_path、grouping_review_path、evidence_paths（最多20个不重复复核文件）。不传可选输入时省略字段，不传null。

支持的 evidence_paths 是已保存的结果文件：

- cad_review_connections 的 connection_review_schema_version=1 文件；同时回读根配合，补入已映射到两个实例但没有轴线候选的配合，几何候选索引保持空。
- cad_review_proximity 的 proximity_review_schema_version=1 文件。
- cad_review_face_contacts 的 face_contact_review_schema_version=1 文件。

不直接把 MCP 摘要、原始 sw_* envelope 或用户手写候选表当这些结果文件。缺哪类证据只记录缺口，必要时再调用该能力；无须为了启动本流程强制收齐所有类型。

空间清单须收齐分页/层级。只读项目内文件；来源图最多256文件/128 MiB。工具会回读原始来源、核对SHA256并重跑相应离线计算；绑定不同空间清单、配置或位姿时拒绝 EVIDENCE_MISMATCH。分组含人工复核时需要原始复核文件；新版分组保存review_path，旧版需传grouping_review_path，并核对review_sha256。不从manual_confirmed标签猜原始依据。

# 输出判读

- members：每个叶实例的角色/状态/来源，角色确认仍不等于刚体确认。
- pairs：所选范围所有两两组合（最多1225对），含稳定pair_id和分离保存的证据。范围不是运动链顺序；连接清单不是拆卸顺序。
- evidence_status：candidate_evidence / unknown / needs_reconciliation；review_state初始均pending。
- evidence_id：绑定来源哈希、类型与重放行；replayed_pair_index不是跨文件的CAD对象ID。找原始数据要沿source_path、来源绑定与记录中的feature/face索引定位。
- missing_evidence_families：该对缺少哪些类型，只是待补信息；不要求每个实际连接必须依赖全部类型。
- boundary_evidence：一端在范围内、另一端在外的已知记录；outside_scope_records保留两端都在范围外的统计。
- sources.coverage保留根配合范围、unmatched_mates、未排名组件和读取预算等限制。

DIFFERENT_DISTANCE_THRESHOLDS表示不能直接比较分类；DISTANCE_CLASSIFICATION_DISAGREEMENT表示相同阈值的组件测量快照分类不一致；GEOMETRY_SCOPE_REQUIRES_REVIEW表示组件上下文距离大于放置后零件定义的某个面测点间隙，需要检查装配切除/时刻/范围，不直接判谁错。

SOURCE_INCOMPLETE、UNASSESSED_CHAIN_PAIRS保留partial。complete只描述给定来源的汇总状态，compilation_complete不证明机构已识别；旧字段requires_review=true、mechanical_relation_confirmed=false保留兼容；它们表示尚缺机械关系证据，不要求人工介入。自动补充可获得的证据，无法补全就在结论保留未知和风险。

等价CLI：

```powershell
python -m cadkin chain-evidence outputs/spatial.json --occurrences "实例A" "实例B" --name "升降链候选1" --grouping outputs/groups.json --evidence outputs/connections.json outputs/proximity-review.json outputs/face-contacts.json --output outputs/chain.json
```

文件缺失时省略对应参数，不能补造结果。输入变化需重算新清单，不复用旧清单的人工意见。
