# 参数与判读

cad_review_face_contacts 必填 probe_paths（1–100个不同原始 envelope 路径）、output_path（outputs 下新 JSON）、contact_tolerance_mm（有限非负）、angle_tolerance_deg（0–90°）。每个来源绑定面对应只给一个探测文件，反序仍为同一对。只复核给定记录，没有全装配覆盖含义。

| review_state | 含义 |
| --- | --- |
| near_face_contact_candidate | 存在阈值内的测点对；两端均为实体面，法向近似相反，非零点差方向也与两端外法向相向；仍是候选 |
| near_points_orientation_unconfirmed | 测点间隙在阈值内，但法向缺失/方向不符或包含曲面体，不能解释为相向实体面 |
| sample_gap_above_tolerance | 这些测点的间隙较大；**不能证明整对面分离或无机械关系** |
| unresolved | 所有种子均未获得有效点对，不写成零 |

零间隙没有方向向量，只核对局部相反法向；不能据此区分接触、穿透或包含。面边界/接缝处法向是曲面局部极限，不是接触区域法向。converged 只说明迭代点稳定。

输入来源会重读并核对 SHA256、文档/配置/位姿/面描述符；坐标、法向翻转与间隙从原始数值重算。EVIDENCE_MISMATCH、INVALID_FACE_PROBE_SOURCE、DUPLICATE_FACE_PROBE 均拒绝写成功文件。原始 partial、法向错误、迭代预算未完成继续保留；致命 data=null 文件只作错误记录，不伪装成可复核探测。

不把局部点对自动合并到圆柱同轴关系或已匹配的配合面清单。源定义不含装配级切除；哈希/描述符不是完整几何版本或不变性证明。

等价离线 CLI（0.1 mm/5°仅为示例探索值）：

```powershell
python -m cadkin review-face-contacts --probes outputs/face-probe.json --contact-tolerance-mm 0.1 --angle-tolerance-deg 5 --output outputs/face-contact-review.json
```
