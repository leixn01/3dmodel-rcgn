# 结果边界

| 字段/状态 | 可以说明 | 不能说明 |
|---|---|---|
| modeled_local_snapshot | 已支持约束在当前姿态的线性系统已解；modeled_instantaneous_dof是零空间维数 | 目标机械关节已确认、完整机构DOF已解 |
| partial_constraint_model | known_constraint_nullity与motion_modes只针对已知支持的约束子集 | 缺失约束不会继续限制这些方向 |
| no_supported_constraint_model | 当前没有可建模的有效配合 | 自由刚体、6DOF、STEP里一定没有机械连接 |
| numerically_sensitive | 阈值×0.1/×10时秩改变；保留rank_range/nullity_range | 某个秩就是物理真值；未输出模式不表示锁死 |
| conflicting_source | 来源几何/配合相互冲突；数值矩阵仅诊断 | 根据诊断nullity认定运动方向 |
| dependent_linear_equations | 当前矩阵中线性相关的方程数量 | 同数量配合可删除或CAD必定过约束 |

坐标：以排序后的第一个实例为相对运动参考，并不声明它被固定/接地。方向采用根装配坐标；velocity_origin_root_m是所选参考面点的均值，仅lock时为根原点，不是质心/转轴枢轴。

scaled_twist顺序[vx/L,vy/L,vz/L,wx,wy,wz]。linear_velocity_at_origin_m_per_unit_time和angular_velocity_rad_per_unit_time是任意单位参数下的同一个基向量，幅值不是电机速度。旋转可伴随原点平移，不把两个分量拆成两个关节。pure_translation_directions_root仅表示omega=0时仍满足方程的纯平移方向，不能用全部模式的平移投影代替。

局部矩阵把原公差内的一对面理想化成参考实例的精确重合轴/平面；measured_pair_residuals与analysis_parameters同时保留。第一阶零空间不能证明有限行程，奇异位形可能出现额外瞬时方向。闭环、其它组件对、子装配内部配合、碰撞与物理接触不在本轮范围。

pattern_gaps_addressed只说明矩阵方法覆盖旧组合规则的缺口；source_missing_evidence仍保存原始记录。几何来源不足、边界联系、未知锁转、预算截断继续留在unresolved_evidence，不能因为旧规则已覆盖就删除风险。
