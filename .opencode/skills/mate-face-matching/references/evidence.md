# 参数与证据

调用 sw_match_mate_faces：expected_document_token、inventory_path、cylinder_paths（1–8 个原始 envelope 文件）。空间文件必须 collection_complete/hierarchy_complete=true 且无层级截断；圆柱文件必须由 include_face_references=true 采集。源文件应在当前项目内，MCP 输入是路径而非聊天摘要。

默认 max_candidate_faces=100（上限 500）、max_comparisons=2000（上限 20000）；根配合遍历默认 max_features=2000、max_mates=200、max_entities=16、max_depth=32。候选面按完整实例路径、body/face 排序取预算内记录，不保证扫描到某条指定配合。先选 2–5 个实际零件，预算耗尽保留 partial。

工具复用根配合读取，不需另先运行 sw_mate_inventory。它读取持久 ID 对应的当前零件面，复核配置、位姿和原始圆柱参数，经实例 GetCorrespondingEntity 转换后用 IsSame 比较配合引用。索引只定位哈希源文件中的记录；ID 字节相等、轴线相同或半径相同都不是这里的身份判据。

原始返回仍有 mate_inventory_schema_version=1，另含 face_matching 来源/预算/范围，各实体增加 face_match：

| status | 含义 |
| --- | --- |
| checked | 该实体的输入范围已比较；matches 可为空 |
| partial | 只完成一部分比较，已证明的 matches 仍保留 |
| unknown | 引用或上下文无法核对 |
| not_face | 已读取的引用类型不是面，不识别边/顶点/基准轴 |
| outside_scope | 引用实例不在提供的圆柱文件内 |

face_matching.unvisited_occurrences 是未进入面准备的实例；没有根配合时比较数为零，不能说持久引用的实机解析/匹配分支通过。complete 只描述本次范围和已执行读取，无关整机连接完整性。

保存完整 envelope（含 status/data/errors），不要只存 data。CLI 共用同一入口：python -m cadkin sw sw_match_mate_faces --arguments '<实际 JSON>' --output outputs/<新文件>.json；准确参数与调用顺序见验收文档。采集后由 connection-review 使用该文件作为 mate_inventory_path，其他工具无需新加参数。
