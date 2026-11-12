# 字段与失败分支

参数仅三个必填：当前 expected_document_token、left_occurrence_path、right_occurrence_path。路径来自当前实例树；同文件的不同实例可以测量，不能把文件路径当实例路径。多实体零件允许，子装配容器不允许；嵌套零件传完整路径。

工具调用活动根文档 ClosestDistance，输入组件对象。返回 measurement.distance_m/mm、point_left_m/mm、point_right_m/mm；最近点对应左右输入顺序，frame=root_assembly。工具验证两点间距与 API 距离的一致性，这是数值自检，不是实机测量验证；API 可能无法处理某些几何。

measurement_status=unavailable 时 measurement=null，原始 errors 保留、envelope 为 partial。成功距离与最近点才可用于阈值筛选。距零无法区分贴合、交叠、包含或 API 数值误差；不提供接触面、穿透量、干涉体积或孔轴配合结论。

- NOT_PART_COMPONENT / UNRESOLVED_COMPONENT / COMPONENT_MODEL_UNAVAILABLE：换成真实已解析叶零件或交用户处理模型状态，不自动展开为全子件测量。
- COMPONENT_CONFIGURATION_MISMATCH：当前零件定义配置与引用配置不符，保持错误；不自动切配置。
- IN_CONTEXT_EDIT_ACTIVE：当前正在上下文编辑组件，提示用户结束后重试，不自动切编辑目标。
- DISTANCE_NO_SOLUTION / INVALID_DISTANCE_RESULT / DISTANCE_POINT_MISMATCH / API 读取错误：保留不可用和错误，不用包围盒/原点距离替代 API 测量。
- DOCUMENT_CHANGED / COMPONENT_CHANGED：丢弃整次混合结果，重新采集稳定来源。token 不是几何版本，期间不可编辑。
- TIMEOUT / OUTCOME_UNKNOWN：单次 CAD API 仍可能阻塞，先核对现场，再重启 MCP；不盲目叠加重试。

普通已知实例对可直接测量，无需先生成候选、配合或圆柱文件。多个候选逐次调用，单独保存每对结果；不要一个工具调用包下全部 254 组件。CLI 共用 sw 入口的 --arguments / --output，保存完整 status/data/errors。
