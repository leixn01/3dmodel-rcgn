# 单面采样契约

sw_sample_cylinder_face必填expected_document_token、boundary_path、query_points_root_mm（1–32个三维点，根坐标毫米）、membership_tolerance_mm（大于0且不超过0.1mm）。boundary_path必须指向原始完整sw_read_face_boundary envelope；持久引用、catalog哈希、实例配置/变换、解析边界在读取前后核对。

每点用有限面GetClosestPointOn投影，再同面重投影核查；读取EvaluateAtPoint原始11值，以FaceInSurfaceSense定向。结果保留原点、返回点、法向、距离、错误。solid body才解释inner/outer；薄片只能给定向法向。不能用采样比例估算圆周/面积覆盖。

来源变化或未知执行结果立即遵循现有停止策略；不换容差、点数、新目录或初始链重试。一次工具有界处理一面全部点；不要拆成每点一次MCP调用。报告COM耗时，不把合成测试速度称为实机加速。
