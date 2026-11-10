# 统一机电模型契约草案 v0.1

这是后续运动结构的设计契约。当前已有输入体检与基础 SolidWorks 工具，尚未实现这里的完整 schema 验证器；已实现的 MCP 结果格式见 TOOL_CONTRACTS.md。

| 对象 | 必备字段或规则 |
| --- | --- |
| Asset | source_uri、revision、sha256、format、文件内路径、导入器版本 |
| CadOccurrence | source_asset_id、occurrence_path、definition_id、实例 ID、配置、父实例、局部与全局变换、单位、几何引用 |
| Frame | 唯一 ID、所属对象、父参考系、4×4 变换、原始单位、转换记录 |
| RigidBody | 成员实例 ID、组内相对变换、工程固定状态、分组依据、确认状态 |
| Constraint/Joint | 两端刚体、类型、轴线/原点/参考系/正方向、原始约束引用、剩余自由度、状态 |
| Coupling | 输入/输出关节、耦合形式、传动比/导程/偏置及证据；支持闭环图 |
| Parameter | value、unit、source/evidence_ids、status；未知值为 null，不使用默认行程 |
| SignalBinding | PLC 工程版本、变量/任务/FB/IO、电气对象、CAD 实例、轴/传感器、端口类型、方向、产生方 |
| Evidence | 类型、源文件/实体/行号、工具与规则版本、测量值、人工记录、时间 |
| Decision | 候选、已确认、冲突、未知；人工修正历史和被替代版本 |

实例 ID 在固定源版本内由资产标识＋完整出现路径稳定生成；不能只用文件名、显示名或遍历下标。跨 CAD 修订的身份迁移单独记录映射，不承诺 STEP 实体编号跨导出稳定。

内部规范单位建议 m/rad/s，入口保留毫米等原单位与明确换算。变换约定为列向量，`p_parent = T_parent_child @ p_child`；组合、逆变换、轴向符号必须测试。当前资产报告尚未生成这些变换。

以下参数分开保存：geometric_feasible_range、mechanical_hard_limits、controller_soft_limits、process_target_positions。碰撞扫掠仅为几何可行性证据；程序位置与超时不能自动成为机械行程与运动时间。

规范模型保留完整约束图。URDF 等树形输出必须附带未表达闭环、耦合与参数的损失报告；不得静默删除约束。工艺级简化必须记录折叠的内部运动和用途边界。

字段确认状态与证据来源分开：来自 CAD 的事实未必代表真实机构；高置信候选不自动等于已确认。没有完成校准前，规则评分不能称为概率。
