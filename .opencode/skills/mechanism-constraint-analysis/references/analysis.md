# 参数与判读

MCP cad_analyze_constraints：target_graph_path、output_path、distance_tolerance_mm>0、0<angle_tolerance_deg<=5必填；max_pairs默认200，范围1–1225。CLI在仓库根目录运行：

```powershell
python -m cadkin analyze-constraints outputs/target.json --distance-tolerance-mm 0.1 --angle-tolerance-deg 0.1 --output outputs/constraints-0.22.json
```

0.1mm/0.1度只是示例，按已有测量精度明确选择，不为得到预期类型调阈值。返回output_path及报告；coverage区分available/returned/omitted。partial与未知结论不同：前者是来源/预算不完整，后者可发生在完整读取但无机械证据时。

当前规则：

| 目标局部约束 | 候选 |
|---|---|
| 干净活动、精确实例对的lock | fixed |
| 同心圆柱配合且已读取锁定旋转true | prismatic |
| 两条有间距的平行轴，各有同心配合 | prismatic |
| 同心配合、锁定旋转false、法向沿轴的重合平面配合 | revolute |
| 已阻止旋转，再加沿轴的重合平面配合 | fixed |

重复同一轴不算多条独立约束；沿轴的平面几何必须属于活动重合配合，单纯测到近接触不算轴向止动。未读LockRotation时不能推定false。其它活动配合、边界关系、读取错误或范围不完整会保留缺口，候选最多conditional。几何超公差保留conflicts，不将未支持的配合静默丢弃。

这些是局部候选规则，不是全局秩计算。没有在目标字段填入候选类型/DOF；limits、行程、运动可行性和子装配内部约束仍未知。报告不被旧draft/check自动消费；在结论中作为独立、可追溯的目标证据层展示。
