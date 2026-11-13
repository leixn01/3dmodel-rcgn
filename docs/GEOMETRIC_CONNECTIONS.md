# 无配合模型的几何连接分析（0.28.0）

现在可从目标模型已有的轴线、局部面探测和距离证据，提出**有条件的连接解释**，列出验证缺口，并定向补采距离。新增cad_analyze_geometric_connections；总计52工具、45个解耦功能skill。无需匹配模板，不要求先有原生配合。

## 能看到的结果

| 目标证据 | 报告如何解释 | 仍缺少什么 |
| --- | --- | --- |
| 同轴圆柱候选 | 并列保留转动、滑动、圆柱副、固定及无直接关节等解释 | 有限孔轴啮合、轴向保持、防转与实际运动 |
| 多条偏置平行同轴线 | 可提出导向解释；转动冲突以多条导向同时啮合为条件 | 是否同时啮合、真实连接和其他约束 |
| 相向且接近的平面样点 | 保留平面运动、固定等解释 | 持续面接触、分离/倾斜约束、连接方式 |
| 只有平行轴或组件近距离 | 保留几何上下文，不分配特定运动类型 | 具体有限面和机构约束 |
| 没有几何依据 | insufficient_geometry/source_gap | 合法绑定的圆柱关系或面/距离来源 |

每条解释包含supporting_geometry_ids、required_unverified_conditions、conditional_conflicts。来源同轴还须通过当前报告的毫米/角度阈值，较宽来源判定不能绕过更严格阈值；放宽报告不能补回源扫描遗漏，也不会自动提升旧parallel分类。轴线偏移不是组件表面间隙。同一条轴的分割面不重复投票；不同源分别保留，不合并为约束方程。no_direct_joint和other_relationship保留，候选集不是穷尽。名称、模板和包围盒不用于确定运动类型。

目标类型仍unknown、DOF仍null。本报告不传入原生约束求解器，不自动编辑配合或覆盖草案/分组。候选术语参考[Modern Robotics关节定义](https://modernrobotics.northwestern.edu/nu-gm-book-resource/2-2-degrees-of-freedom-of-a-robot/)；几何解释规则是本项目的保守启发式，不是从外观恢复真实关节的证明。

## 输入与调用

复用cad_build_target_graph生成的target；无配合时可由空证据链加relation_paths接入已有圆柱关系，不需要伪造配合。已有采集历史必须传最新evidence_index_path，绑定同target的check。索引中的完整距离/面探测可直接被解释，不要求先有proximity/face review基线。孤立圆柱扫描仍需component-relations及目标图重建，不能直接当作已有轴线关系。

```json
{
  "target_graph_path": "outputs/target.json",
  "distance_tolerance_mm": 0.1,
  "angle_tolerance_deg": 0.1,
  "max_pairs": 100,
  "output_path": "outputs/geometric-connections.json"
}
```

路径与公差须来自实际任务；例值不是升降机标定结果。毫米公差范围(0,10]，角度(0,5]，max_pairs=1–200。调用cad_analyze_geometric_connections，或在项目根目录使用通用CLI `python -m cadkin sw cad_analyze_geometric_connections --arguments JSON`；优先MCP结构化参数以避免Windows命令行转义。

摘要仅返回analysis_source、coverage与历史信息，完整pairs按需读取。geometry_connection_schema_version=1绑定target、index与所有原始文件hash；旧target/schema/草案不改变。原target的来源错误和check发现仍保留，补充局部观测后报告也可能partial。

## 自动补采衔接

1. 报告有COMPONENT_DISTANCE_MISSING：cad_plan_evidence_tasks传draft_check_path、geometry_analysis_path、output_path及max_tasks。v6计划只补缺失实例对距离，完整前后文档/位姿保护计入预算。不可同时传constraint_analysis_path或initial_capture_profile。
2. sw_execute_evidence_batch执行原计划，按execution_source续跑；不是重做已执行步骤。完整且保护通过后cad_index_evidence使用同check+新receipt，保存失败/partial尝试。
3. 同target+最新index重算几何报告。已经测过大间隔、失败或partial的距离不会重采；旧报告不能搭配新index规划。共享4轮历史，不改变输出名绕过。
4. 已有近距离见证点却缺有限面样点：交cad_plan_face_probes，使用最新check/index和明确阈值/预算。先取缺失面目录、索引，再让原工具选择持久面引用和最近点种子；探测后再索引和重算。此分析可直接解释完整guarded probe；若需更新草案，另走原回填阈值/来源规则。

两实例只有一次距离任务时共7次内部工具调用（1次距离+6次保护），可由一次批次往返完成；时间预算可能导致拆批。合成完整流程用了3轮：距离→两个面目录→四个候选面探测；随后停止重采。该调用数不是实机耗时保证。

几何解释不自动接入chain-session；先取它返回的handoffs.target/index，再调用本分析。已有历史不得重新初始化。无配合模型若只有root_mates采集而没有几何，仍保持缺口，不能靠反复读取配合获得运动关系。

## 边界与验证

静态同轴/近距离不是物理连接。组件距离与零件定义面探测范围不同，差异会保留flags；局部接近不能证明接触、干涉或有限运动。PHYSICAL_ATTACHMENT_AND_FINITE_MOTION_UNVERIFIED是当前能力缺口，不通过重复静态扫描消除，不设置人工复核。

```powershell
python scripts/verify_geometric_connections.py --output outputs/verify-geometric-connections-0.28
```

预期passed=true、44项；重跑换新目录。使用明确合成CAD和生产工具流程，不代表升降机实测。详见[0.28实机验收](MCP_ACCEPTANCE.md#0280几何连接解释与定向补采)。
