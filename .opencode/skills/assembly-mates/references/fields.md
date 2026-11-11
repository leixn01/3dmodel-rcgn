# 字段与范围

- mate_inventory_schema_version=1；scope=active_root_assembly，subassembly_internal_mates_included=false。只遍历当前文档 MateGroup 下的特征，不打开子装配定义。
- 每项保留 feature_id、feature_name、feature_type、type_code/type_name、entities、activity 和 errors。feature_id 是该文档特征 ID，不是全局 ID 或可直接选择的持久引用；来源文件哈希与文档一起标识证据。
- activity.state 为 suppressed、rolled_back、unsuppressed_feature_issue、unsuppressed_no_feature_error 或 unknown。feature_error_code 非零的 warning 也保留为问题；读取失败保持未知，不补 false。solver_validity=not_evaluated，不能改称“已求解有效配合”。
- entity_params_frame=root_assembly 仅因这些配合从根装配特征取得。保留原始米单位参数，不按组件 Transform2 再变换。ReferenceType2 是选择类别，不是圆柱/平面分类。
- reference_occurrence_path 仅在完整 Name2 命中当前树且 ISldWorks.IsSame 确认同一实例后给出。未映射、同名异对象或空引用保持未知，不按短名称猜实例。空引用可能是根基准，也可能不可用。
- component_contexts 保存已确认引用实例的文件、配置和根变换。引用可以是子装配容器或嵌套零件，但这些记录不包括子装配内部配合；也不展开成容器所有子件的连接。
- 当前读数不是事务快照，不证明模型期间完全未编辑；无配合也不证明自由运动。固定标志与 GetMates 原记录由独立 component-constraints 能力提供，不要求每次先加载它。
