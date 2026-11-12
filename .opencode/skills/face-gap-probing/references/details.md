# 准确参数

sw_probe_face_pair 必填 expected_document_token、left、right、seed_points_root_mm。left/right 各为 {face_inventory_path, body_index, face_index}，路径必须为项目内原始 sw_component_faces envelope；选择两个不同实例。种子是1–8个 [x,y,z]，单位毫米、根装配模型坐标；没有默认种子。

max_iterations 默认20，范围1–50；convergence_tolerance_mm 默认0.001，范围(0,1]。这是点位置迭代稳定阈值，**不是工程接触公差**。max_iterations=1 通常不能验证稳定，应保留 partial。

先解析持久面 ID 并核对文档/配置/实例变换/描述符，再将根种子逆变换到零件坐标，调用 IFace2.GetClosestPointOn（实际有限面），将返回XYZ正变换一次到根坐标；不使用无限曲面的 GetClosestPointOn，也不使用圆柱轴线距离代替面点距离。每步左右交替；多种子只扩大局部探测范围，不保证全局最优。

用 ISurface.EvaluateAtPoint 读取点处底层法向，根据 FaceInSurfaceSense 翻转，再变换/归一化。surface 参数、点投影在零件定义中计算，不包含装配级切除；不要将结果描述成装配最终布尔几何。

# 输出与失败

face_probe_schema_version=1；sources 绑定两原始目录/哈希及实例；samples 保留每个种子的测点、UV、法向原始数据、间隙与 errors；best_seed_index 是有效种子结果中测点间隙最小的一条。measurement_status=sampled/unavailable；complete 仅表示请求范围的读取状态。**converged=true 也不是最小值证明。**

- 法向失败时仍保留间隙；几何点失败时 metrics=null，不能补零。
- FACE_PROBE_ITERATION_LIMIT 保留有效测点和 partial；FACE_POINT_NOT_ON_FACE 表示测点自查询核对失败。
- FACE_REFERENCE_UNRESOLVED、FACE_GEOMETRY_MISMATCH、EVIDENCE_MISMATCH 应重新核对/采集来源，不改 ID、参数或哈希绕过。
- UNSUPPORTED_FACE_SURFACE：本轮只支持解析平面/圆柱，其他表面不能假设为平面。
- GEOMETRY_CHANGED/COMPONENT_CHANGED/DOCUMENT_CHANGED：丢弃混合结果，保持模型稳定后重采。
- 小间隙/相反法向只提供候选，不能判接触面积、干涉/包含、孔轴配合、刚体或运动副。曲面体朝向和边界/接缝处局部法向需人工解释。

一次只测少量面；单次 COM 仍可能阻塞，超时后核对现场再重启 MCP，不盲重试。实机验证读 docs/MCP_ACCEPTANCE.md 的0.11.0章节。
