# 局部瞬时约束求解（0.24.0）

该模块回答：在当前姿态、同一份根装配配合快照内，已支持的两实例约束允许哪些相对微小运动？它不确认机械关节、不修改CAD，也不求解整机闭环。

## 输入与分层

`cad_solve_local_constraints`重放原`cad_analyze_constraints`报告及全部来源，从直接引用且身份准确的配合面建立方程。纯数学在`cadkin/constraints/linear.py`、`motion.py`；文件/来源边界在`cadkin/tools/local_motion.py`；MCP/CLI共用工具。工作流独立为mechanism-local-motion，按需读取参数和判读说明。

仅有效显式lock、同心轴与重合平面参与。名字、模板关节、近接触、纯几何相似、IsFixed、抑制/错误配合不提供方程。不同快照各自求解，不跨源组合；继承原分析公差、覆盖与索引/check/轮数。离线求解不消耗或重置采集轮数。

## 坐标和方程

排序后的第一个实例仅作为相对静止参考，不等于它已接地。根装配坐标轴下，速度原点o为所选参考实例面点的均值；仅lock时采用根原点。特征长度L以米计，由调用者显式传毫米参数。

未知量采用 **x = [v_o/L, omega]**。点p的速度是 **v(p) = v_o + omega × (p−o)**。令r=(p−o)/L，方向d的两个单位正交切向量为t1、t2，平面单位法向为n。

| 支持约束 | 齐次线性方程 | 单独约束的最大独立行数 |
|---|---|---|
| 相对位姿lock | x的6个分量为0 | 6 |
| 同心轴 | t1·omega=t2·omega=0；ti·(v_o/L + omega×r)=0 | 4 |
| 同心且明确LockRotation=true | 同心轴方程加d·omega=0 | 5 |
| 重合平面 | t1·omega=t2·omega=0；n·(v_o/L + omega×r)=0 | 3 |

速度行的系数为 **[n, r×n]**（轴横向行用ti代n）。每行除以其欧氏范数，组成J并求解Jx=0。不同位置平行轴、多条非平行轴、多个平面和斜面组合通过矩阵共同约束，不靠再增加类型匹配规则。重复方程不增加独立约束秩。

原配合分析允许的几何公差内，两端面被理想化为参考实例的精确重合轴/平面。这不是几何拟合或纠正CAD：保留`measured_pair_residuals`及原公差。几何不一致的源仍标冲突，不能拿诊断矩阵的零空间当可运动模式。

## 数值解与可重放性

NumPy SVD求秩和零空间；不足6行补零，长矩阵使用reduced SVD，不创建m×m大矩阵。阈值为max(relative_rank_tolerance×最大奇异值, 浮点精度下限)。默认相对阈值1e-8，并同时计算阈值×0.1和×10的秩；改变则报告`rank_range/nullity_range`，不输出确定维数或运动模式。

零空间投影矩阵生成确定性正交基，并核对J乘基向量的残差与正交误差。基只是子空间的一组参数，不是独立物理关节；旋转常伴随速度原点平移，不能把两个分量算为两个DOF。`pure_translation_directions_root`另外求omega=0切片，不能拿耦合模式的平移投影充当纯滑动方向。

L控制平移/角速度数值权重，与模型几何毫米/角度公差不同。尺寸跨度悬殊、接近奇异配置时秩可能敏感；阈值稳定只说明本次数值检查稳定，不证明物理模型准确。不要反复调整L/阈值挑选希望得到的运动类型。

重放重新计算全部来源与方程。只有已计算的`linear_solution`、`motion_modes`、`pure_translation_directions_root`中浮点值容许rel=1e-9、abs=1e-10的LAPACK舍入差异；秩、状态、长度、原点、系数、参数、输入路径/哈希等仍精确核对。输出独占新建，原始输入不改。

## 输出与边界

- `modeled_instantaneous_dof`只对完整、无冲突且数值稳定的**已建模局部快照**给出值；`constraint_system_solved`也仅指这个线性系统。目标`target_joint_kind=unknown`、`target_degrees_of_freedom=null`不变。
- 缺失、预算截断或不支持配合时只保留`known_constraint_nullity`和已知子集模式，`modeled_instantaneous_dof=null`。无可建模约束为未知，不能宣布6DOF。
- 敏感或冲突时`motion_modes=[]`；`linear_solution`中的投影/基仅为诊断。空模式不等于锁死，需结合status。
- `dependent_linear_equations`是矩阵相关行数，不是可删除的配合数，不证明SolidWorks过约束。未发现矛盾也不证明完整非线性装配可解。
- `pattern_gaps_addressed`记录已覆盖的旧组合规则缺口，原missing记录仍保留；几何不足、未知锁转、跨边界连接、源partial继续是缺口。
- 其它组件对、整机回路、子装配内部配合、距离/角度/限位/齿轮/螺旋/路径配合、碰撞/接触不在本轮支持范围。
- 第一阶零空间只描述当前姿态；奇异位形的瞬时方向可能没有有限运动路径。不会自动生成限位、枢轴、螺距、动力学参数或拆卸顺序。

补采仍用原constraint analysis和同target的check，不能把本报告传入`constraint_analysis_path`替代原分析。保留最新索引与4轮上限；无需人工复核前置。

## 方法参考

- [Modern Robotics 8.7: Constrained Dynamics](https://modernrobotics.northwestern.edu/nu-gm-book-resource/8-7-constrained-dynamics/)：配置约束微分后的Pfaffian速度约束。这里仅使用其速度约束思想，不实现动力学。
- [Modern Robotics 3.3.2: Twists](https://modernrobotics.northwestern.edu/nu-gm-book-resource/3-3-2-twists-part-1-of-2/)：刚体角/线速度及表达原点。本项目分量顺序显式采用线速度在前。
- [NumPy SVD](https://numpy.org/doc/stable/reference/generated/numpy.linalg.svd.html)、[matrix_rank 1.26](https://numpy.org/doc/1.26/reference/generated/numpy.linalg.matrix_rank.html)：奇异值分解、秩阈值与数值误差。项目自行增加尺度、阈值敏感性及来源重放。

本页公式与实现为本项目的受限局部模型；上述资料不为用户STEP的约束完整性或运动可行性背书。
