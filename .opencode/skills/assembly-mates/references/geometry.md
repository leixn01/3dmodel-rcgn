# 增强配合采集

sw_mate_inventory增加include_reference_geometry布尔参数，默认false。只有需要具体引用面及旋转锁定状态才设true。其它max_features/max_mates/max_entities/max_depth预算不变，保持token及模型上下文。

新增原始字段：
- data.reference_geometry_capture：scope=direct_root_mate_face_references，root_assembly坐标，identity_rechecked；不是目录面匹配或完整几何版本证明。
- mates[].entities[].reference_geometry：status、surface_type、EntityParams原值、root点/方向/半径、根装配persistent_reference。非面/未映射/非解析面保留unknown或unsupported；不猜目录索引。
- mates[].constraint_options.concentric_lock_rotation：只从同心配合GetDefinition/LockRotation读取布尔值；其它配合not_applicable。unavailable=null不能解释成未锁定。

采集仅只读；不AccessSelections、不修改配合、不重建。真实返回保存到outputs新文件。partial要保留错误；MATE_STATE_CHANGED/GEOMETRY_CHANGED/COMPONENT_CHANGED/DOCUMENT_CHANGED后丢弃混合快照，重新采集一致上下文。读取失败时先检查错误，不无限重试。

新文件须重新经过connection-review→chain-evidence→mechanism-target-graph，再给mechanism-constraint-analysis。不要替换旧文件内容；旧执行计划/索引的来源与轮数继续保留。增强采集暂未加入自动补采规划器，不绕过其停止状态自动执行新一轮。
