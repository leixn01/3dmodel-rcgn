# 判读与来源

cad_review_proximity 必填 proximity_path、distance_paths（1–200 个原始 envelope 文件）、output_path、contact_tolerance_mm（毫米，非负）。阈值不能从包围盒筛选阈值推断；没有工程公差时，可明确标记 0.1 mm 为探索值，结果保留探索公差风险，后续自动补证，不等待人工复核。

| review_state | 解释 |
| --- | --- |
| near_contact_candidate | 成功的 API 距离在显式阈值内，待核对接触/间隙/交叠 |
| separated_at_measurement | 测量时 API 距离大于阈值，不代表机械上无关联 |
| unresolved | 已提供该对测量但没有有效距离，保留源错误 |
| unmeasured | 工作清单中该对没有测量文件 |

工具重算工作清单核对其空间哈希/参数/范围，核对距离的根文档、配置、完整实例、父级、源文件、位姿、米/毫米及最近点一致性。原空间清单可带显式几何错误，整体保持 partial。一个实例对只接受一个距离文件，交换左右仍是同一对，不任意挑某个快照。

- EVIDENCE_MISMATCH：空间/文档/配置/位姿或工作清单不一致，重新采集来源；哈希相同也不证明采集间几何未变。
- DISTANCE_OUTSIDE_SCOPE：提供了不在该工作清单内的测量。单独报告该原始测量，或明确扩大筛选范围生成新清单再复核；不修改清单插入一对。
- DUPLICATE_DISTANCE_SOURCE：选择同一次稳定采集的一份原始结果，不能自动按数值大小挑选。
- INVALID_DISTANCE_SOURCE：输入不是可用原始 envelope 或字段不一致。致命错误 envelope 无目标上下文，保留到验收错误记录，不冒充可复核距离。
- SOURCE_INCOMPLETE / UNMEASURED_CANDIDATES：保留已知值及未知范围，即使某对证据完整，整体仍为 partial。

CLI：python -m cadkin review-proximity <proximity.json> --distances <distance-a.json> <distance-b.json> --contact-tolerance-mm 0.1 --output outputs/<新文件>.json。文件仍需在项目内，输出独占新建。
