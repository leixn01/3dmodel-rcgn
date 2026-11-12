---
name: face-contact-review
description: 离线复核已有面探测文件，按明确间隙与角度阈值整理近接触候选，保留局部范围和未知项。用于“整理面级接触证据”；不启动 CAD，不把局部大间隙当全局分离，不确认机械连接。
---

# 面接触候选复核

输入：原始面探测 envelope 及其源面目录、明确毫米/角度阈值。输出：新的离线复核 JSON。

1. 调用 cad_review_face_contacts，传 probe_paths、output_path、contact_tolerance_mm、angle_tolerance_deg；已有文件时不连接 SolidWorks。
2. 阈值必须有工程依据或明确标注为探索值；来源不符先核对后重采，不手改文件/哈希骗过检查。
3. 按实例和具体面报告测点间隙、法向、分类、源哈希及 partial；没有测到的面和区域保持未知。
4. 保持 requires_review=true、global_minimum_proven=false、contact_confirmed=false、mechanical_relation_confirmed=false，不自动修改配合/刚体分组。

分类、参数或失败不清楚时读 [复核细节](references/details.md)；只缺哪项输入才请求对应采集，不强制加载完整链。
