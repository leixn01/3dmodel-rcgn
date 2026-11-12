# 面候选与任务计划

## 参数

cad_plan_face_probes必需draft_check_path、evidence_index_path、output_path、max_component_gap_mm、surface_tolerance_mm。前两者必须是原始check及绑定该check的最新索引；输出在outputs下新建。

- max_component_gap_mm：已测组件距离的筛选阈值，不是接触判定。
- surface_tolerance_mm：最近点到无限解析平面/圆柱的残差阈值，使用根坐标毫米；不判断trim内外、接触斑或机械关系。
- max_component_pairs=20（1–200）：按已测组件距离、实例路径取前若干对。
- max_face_candidates=20（1–100）：每个端点按残差、body/face定位符保留候选；同分截断必须报告。
- max_face_pairs=100（1–2000）：所检范围内按最大/合计残差、组件距离及稳定定位符排序，保留未尝试面配对。
- max_tasks=20（3–200）：包含前后文档与实例位姿检查。两个实例的1次探测至少7次调用。
- max_iterations=20（1–50）、convergence_tolerance_mm=0.001（>0且≤1）：有限面交替投影预算/稳定阈值，不是几何接触公差。

任务请求没有明确阈值时，根据已有项目配置或已有测量的单位/尺度给出有说明的工作假设，并在结论保留阈值敏感性；不等待人工复核，不把参考模板数值复制成目标公差。示例的30mm/.1mm仅用于模拟验收，不能自动作为升降机真值。

CLI同一实现：

```powershell
python -m cadkin plan-face-probes outputs/check.json --evidence-index outputs/index.json --max-component-gap-mm 30 --surface-tolerance-mm 0.1 --output outputs/face-plan.json
python -m cadkin execute-evidence outputs/face-plan.json --output outputs/face-run.json
python -m cadkin index-evidence outputs/check.json outputs/face-run.json --output outputs/face-index.json
```

## 来源、结果与交接

工具重放check与索引，只读取目标图来源及索引中的完整观测。没有完整组件距离时返回NO_COMPLETE_DISTANCE_WITNESS；交接已有组件距离/补采能力，不能拿包围盒或无限轴线点补作实际最近点。

有有效距离但缺面目录时安排单实例目录采集；完成并索引后才能知道面并生成探测参数。相同目标的多个目录/距离快照若冲突，保留CONFLICTING_FACE_CATALOGS或CONFLICTING_DISTANCE_SNAPSHOTS，不能任取最后一份。新建空间快照及一致来源后重算。

计划schema_version=1、algorithm_version=3、plan_kind=witness_guided_face_probes。face_candidates保留两端源哈希/记录定位、残差、原始距离来源、实际端点/中点种子。live_face_identity_verified=false、finite_face_membership_tested=false；这些在离线计划阶段尚未验证。

sw_execute_evidence_task仍每次最多一个CAD调用。sw_probe_face_pair解析持久引用并核对描述符，查询有限面GetClosestPointOn；执行器再验证来源、参数、单位变换、测点与法向派生量。保存原始envelope和新receipt。独立face-contact-review负责候选分类，不由规划器或索引替代。0.20.0起交接evidence-reintegration回填兼容面证据；新组件对可传明确复核依据，旧组件对仍沿用原参数。重算成功交接joint-draft-compare，再基于after_check_source.path和同一receipt建立索引；后续计划的check/index须一致。

失败/partial尝试也进入索引；面配对去重包含两端实例、零件配置和保存引用键，反向顺序、换种子或增加迭代次数不绕过已尝试记录。此键用于防重复，不以字节相同宣称CAD实体相同。已有来源中的面探测也阻止自动重复。

每次续轮传最新索引；与通用补采共享4轮上限，不删除索引重新计数。预算不足或无新任务时tasks=[]，不能调用执行器。stop仅结束本次有界采集；剩余findings、未检面、未知运动参数继续报告。

## 失败与范围

- EVIDENCE_MISMATCH：来源、check绑定、位姿或派生内容改变；不修改旧哈希/token凑通过。
- OUTPUT_EXISTS：换新输出名；已执行/占用路径不得删后重试。
- NO_CAPTURE_TASKS：停止计划无CAD调用；查看continuation与coverage。
- FACE_PLAN_LIMIT：组件对、端点候选、配对、调用或check覆盖受限；不自动扩预算。
- 执行中超时或身份/几何变化：停止，不把旧上下文中的采集回填；保留诊断。

零件定义面不包含装配级切除。无解析匹配可能是裁剪/切除、曲面种类或来源限制，不能推为无连接。小间隙不区分接触、穿透/包含；大局部间隙也不证明整面分离。
