# 参数与范围

sw_component_faces 必填 expected_document_token、occurrence_path；max_bodies 默认20/上限100，max_faces 默认200/上限1000，均至少1。一次只读一个已解析零件，子装配容器不支持；不自动改变在位编辑模式、配置或轻化状态。

保存完整原始 envelope。data.face_inventory_schema_version=1；target 包含完整实例/父路径/文件/配置/变换/源零件，faces 每行包含 body_index、face_index、descriptor、face_reference、errors。

- descriptor：surface_type=plane/cylinder/other、surface_parameters_part、area_part_m2、uv_bounds、body_type、face_in_surface_sense。
- 平面参数顺序为法向XYZ、平面点XYZ（米）；圆柱参数为轴点XYZ、轴方向XYZ、半径（米）。轴点不是有限面的中心。
- face_in_surface_sense=true 表示面法向与底层曲面法向相反；它不是“相同朝向”。body_type=0 为实体、1 为曲面体，曲面体不能据此推断实体外法向。
- UV 四值是 umin/umax/vmin/vmax，不能据此填满孔洞或把矩形范围当实际裁剪面。
- face_reference 在捕获时经过解析回读/身份比较；body/face 索引不是长期 CAD ID。

BODY_LIMIT/FACE_LIMIT 保留 partial/truncated；引用失败时仍保留几何，几何失败时仍保留面行及可用引用。other 仅目录记录，0.11.0 的探测不支持该表面类型。缺失不得写成空目录或零面积。

COMPONENT_CONFIGURATION_MISMATCH、COMPONENT_CHANGED、IN_CONTEXT_EDIT_ACTIVE 应先稳定真实模型再采集，不改 JSON 绕过。模型/配置在采集中保持不变；这是零件定义快照，不含装配级切除，且非事务快照。
