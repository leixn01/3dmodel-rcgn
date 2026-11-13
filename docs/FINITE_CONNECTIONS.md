# 0.29.0 有限圆柱面范围

当前可读取指定圆柱面的解析边界，在共同根坐标轴下计算投影包络，区分轴向分离、重叠和端点公差附近。还可保留既有局部平面探测中与轴向平行的法向证据。所有结果仍是静态几何证据，物理关节、自由度、轴向保持和行程保持未知。

## 工具隔离

| 功能 | 接口 | 范围 |
| --- | --- | --- |
| 单面边界采集 | sw_read_face_boundary | 当前SolidWorks、原始面目录定位、持久面身份核对、解析边界回读 |
| 有限范围分析 | cad_analyze_finite_connections | 离线来源重放、投影包络、局部平面上下文；返回摘要与文件 |
| 补采规划 | cad_plan_evidence_tasks + finite_analysis_path | v7，仅补未尝试的指定圆柱面边界 |
| 执行与历史 | sw_execute_evidence_batch → cad_index_evidence | 复用原保护/receipt/共享四轮，不新增执行器 |

54个MCP工具，47个独立功能skill；新采集和分析各有自己的入口及按需references，程序不进入skill。chain-session仍是原首次基线编排，未自动包含此分支。

## 分析与补采

先有cad_analyze_geometric_connections的原始报告。来源需完整且无冲突的面目录；缺目录交原cad_plan_face_probes，缺距离则先走geometry分支。只有来自原target绑定来源或最新guarded index的目录可用，不扫描outputs。

```json
{
  "geometry_analysis_path": "outputs/geometry.json",
  "evidence_index_path": "outputs/latest-index.json",
  "output_path": "outputs/finite.json",
  "max_face_pairs": 20
}
```

调用cad_analyze_finite_connections。没有历史时可省略evidence_index_path；已有历史必须提供最新版本，省略只继承geometry报告原index。显式新index允许是原index的后继，但必须同target且包含原绑定，不接受无关历史。公差继承geometry报告。

候选来自原报告已有同轴解释的组件对，再匹配目录中的圆柱轴线。每目录最多20个圆柱面，max_face_pairs默认20/上限100。候选面不是已确认配合面，分割面可各有范围；不通过条数投票。coverage与inherited_geometry_coverage记录省略范围。

缺边界时调用cad_plan_evidence_tasks：

```json
{
  "draft_check_path": "outputs/check.json",
  "finite_analysis_path": "outputs/finite.json",
  "output_path": "outputs/boundary-plan.json",
  "max_tasks": 20
}
```

报告的index自动继承；显式替换index会拒绝，应先重算finite。finite参数与geometry/constraint/initial profile互斥。计划按原目录哈希和定位选面，同面去重，边数预算固定64；两实例各一面=2采集+6保护，共8次。预算不足不省保护；单面最少5次。优先批次执行，未完整时按execution_source续跑。完成且guard通过后用同check索引新receipt，再传原geometry报告及新index重新分析。

失败/partial也进入索引并阻止自动重试。距离、面目录、面探测和边界合计最多4轮；不能新建初始化链绕过。边界不走reintegrate伪装成原生配合，不直接改草案。

## 边界读取和数值含义

sw_read_face_boundary参数：expected_document_token、face对象（face_inventory_path/body_index/face_index），max_edges默认64、上限256。直线读取GetStartVertex/GetEndVertex的GetPoint；圆弧读取CircleParams。前后核对原面身份、描述和实例，并回读边界，改变则拒绝。读取完整≠原子拓扑快照。

| 返回状态 | 可解释内容 | 未证明内容 |
| --- | --- | --- |
| axially_separated_face_enclosures | 指定两张面的轴向包络有间隔 | 其它面或间接连接不存在 |
| axial_enclosures_overlap | 包络在轴向重叠 | 角向裁剪覆盖、互补轴孔、实际啮合 |
| axial_endpoint_near_tolerance | 包络端点在公差附近 | 止挡、行程端点或轴向保持 |
| finite_extent_unavailable | 边界缺失、失败、复杂或歧义 | 不用包围盒/UV/网格补猜结果 |

直线端点投影；圆弧用完整圆的保守投影包络，绝不当完整圆周。相对轴倾斜时包络可能扩大，circular_arc_enclosures显式记录。范围用根装配毫米坐标，旋转、镜像和统一尺度只变换一次。signed_interval_overlap_mm可为负；radius_difference_mm只是半径差，不是配合间隙。

axial_plane_observations沿用原有限面采样和独立来源，给出轴向位置、法向符号及是否接近某投影端点。与所选圆柱同实体/邻接未验证，不足以确认“端面止挡”，更不能拼成双向限位。

几何范围仍为零件定义，不含装配级切除。保留源冲突、截断、未测关系；target_joint_kind=unknown，target_degrees_of_freedom=null，motion_limits_mm=null。物理运动需更多目标证据与独立验证，不能将此报告送入原生约束求解器。

## 验证与API依据

```powershell
python scripts/verify_finite_connections.py --output outputs/verify-finite-connections-0.29
```

预期47项检查通过。合成CAD验证生产采集/规划/索引/重放，不代表实机或升降机识别率。完整实机入口见[MCP_ACCEPTANCE](MCP_ACCEPTANCE.md#0290有限圆柱边界与轴向范围)。

官方依据：[IFace2.GetEdges](https://help.solidworks.com/2024/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.iface2~getedges.html)、[ICurve.CircleParams](https://help.solidworks.com/2021/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ICurve~CircleParams.html)。圆曲线可以是圆弧；本项目不把底层整圆参数当角向覆盖。工具未调用GetTrimCurves2，避免其临时边缓冲区/周期裁剪参数语义混用。[GetBox](https://help.solidworks.com/2023/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IFace2~GetBox.html)是近似包围盒，未用于本轮有限范围计算。
