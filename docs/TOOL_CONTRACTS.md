# SolidWorks 工具接口

版本：0.12.0。以下 31 个工具已实现并注册；测试边界与用户 SolidWorks 2025 反馈见 `VALIDATION.md`。以 `cadkin/tools/solidworks.py` 的 JSON Schema 为参数依据。

| 工具 | 参数 | 作用及副作用 |
| --- | --- | --- |
| `sw_start_application` | 可选 `wait_seconds`（1–120，默认 120） | 启动或复用唯一 SolidWorks，会显示窗口并交给用户控制；等待启动完成，不打开文件 |
| `sw_session_status` | 无 | 连接已有进程，读取版本；未运行返回 `connected: false` |
| `sw_active_document` | 无 | 文档标题、路径、类型、配置、dirty 状态和 `document_token` |
| `sw_component_tree` | 可选 `max_components`、`max_depth` | 读取当前装配实例树；不自动解析轻化组件 |
| `sw_open_document` | `path` | 打开 STEP/SLDPRT/SLDASM/SLDDRW，并检查活动文档；不保存或关闭其他文档 |
| `sw_set_view` | `expected_document_token`，可选 `view`、`fit` | 切换标准视图，默认等轴测并缩放适合窗口 |
| `sw_select_component` | `expected_document_token`、`occurrence_path` | 替换当前选择为指定实例，读取选择结果核对 |
| `sw_clear_selection` | `expected_document_token` | 清空选择并核对计数 |
| `sw_rebuild` | `expected_document_token` | 重建活动模型；可能更新内存中的几何及 dirty 状态，不保存 |
| `sw_get_display_state` | 无 | 读取 6 类辅助对象的文档显示开关及“隐藏所有类型”总开关 |
| `sw_set_display_visibility` | `expected_document_token`、`target`、`visible` | 显式设置一个类别的显隐，回读核对；不盲目切换 |
| `sw_zoom_to_fit` | `expected_document_token` | 适合窗口，不请求切换当前方向；需核对画面 |
| `sw_get_component_visibility` | `expected_document_token`、`occurrence_path` | 读取指定实例自身显示状态、隐藏父路径及父级影响 |
| `sw_set_component_visibility` | `expected_document_token`、`occurrence_path`、`visible` | 设置指定实例显示状态并回读，不抑制、解析、移动或保存 |
| `sw_component_spatial` | `expected_document_token`、`occurrence_path` | 只读单实例的根/父变换、原点与近似包围盒，不选择或解析组件 |
| `sw_spatial_inventory` | `expected_document_token`，可选范围、分页、签名和包围盒开关（见下） | 只读一页空间清单；CLI spatial-export 收齐所有页 |
| `sw_component_constraints` | expected_document_token、occurrence_path；可选 max_mates、max_entities | 只读顶层固定标志与组件关联配合；不求解运动关系 |
| `sw_component_cylinders` | expected_document_token、occurrence_path；可选 max_bodies、max_faces、max_cylinders、include_face_references | 只读匹配配置的零件定义圆柱面；放置到实例根坐标，不含装配级切除 |
| `cad_group_components` | `inventory_path`、`output_path`，可选 `scope_occurrence_path`、`review_path` | 离线生成角色候选/应用人工复核，写 outputs 新 JSON，不调用 COM |
| `cad_component_relations` | inventory_path、cylinder_paths、output_path、distance_tolerance_mm、angle_tolerance_deg；可选 grouping_path、预算 | 离线生成同轴/平行几何候选，写 outputs 新 JSON，不连接 COM 或确认运动副 |
| `sw_mate_inventory` | expected_document_token；可选 max_features、max_mates、max_entities、max_depth | 只读根配合特征状态与已确认的引用实例，包含抑制记录，不含子装配内部配合 |
| `sw_match_mate_faces` | expected_document_token、inventory_path、cylinder_paths；可选面/比较/根配合遍历预算 | 在线核对持久面引用与根配合实体，返回来源绑定证据，不修改模型 |
| `cad_review_connections` | relations_path、mate_inventory_path、output_path | 离线关联几何候选与根配合；有面身份证据时细化到具体候选面，不确认运动副 |
| `cad_proximity_candidates` | inventory_path、output_path、max_box_gap_mm；可选 occurrence_paths、max_pairs、max_candidates | 离线近似包围盒筛选待测对，保留未知/预算；不证明接触 |
| `sw_component_distance` | expected_document_token、left_occurrence_path、right_occurrence_path | 只读两个零件实例的最小距离和最近点，不修改选择 |
| `cad_review_proximity` | proximity_path、distance_paths、output_path、contact_tolerance_mm | 离线整理距离候选，校验来源与位姿，不确认机械连接 |
| `sw_component_faces` | expected_document_token、occurrence_path；可选 max_bodies、max_faces | 只读有限面目录、描述符和持久引用，零件定义范围 |
| `sw_probe_face_pair` | expected_document_token、left、right、seed_points_root_mm；可选 max_iterations、convergence_tolerance_mm | 指定两面的局部测点间隙和法向，不证明全局最小距离 |
| `cad_review_face_contacts` | probe_paths、output_path、contact_tolerance_mm、angle_tolerance_deg | 离线校验/复核面探测来源，写 outputs 新文件，不确认接触 |
| `cad_build_chain_evidence` | inventory_path、occurrence_paths、chain_name、output_path；可选 grouping_path、grouping_review_path、evidence_paths | 离线汇总指定范围的角色/连接证据，保留未知和边界，不识别运动副 |
| `cad_apply_chain_review` | chain_path、review_path、output_path | 将明确人工意见绑定到清单哈希，写新文件，不把声明当CAD验证 |

`view` 支持 front/back/left/right/top/bottom/isometric/trimetric/dimetric。接口用枚举值访问视图，不依赖中英文界面的视图名称。

先读取文档或组件树，使用返回的 `document_token` 操作。该值关联进程、文档路径/标题及活动配置；目标不匹配返回 `DOCUMENT_CHANGED`，不会操作新目标。它不是不可变几何版本号；模型重建或编辑后重新读取组件清单。工具执行期间不要在界面切换文档、配置或修改模型，COM 读取不是事务快照。

## 0.12.0：机构链证据清单与人工声明

本轮两工具完全离线，不新建COM连接；CLI/MCP共用实现。输入仍限项目内JSON，输出为outputs下新文件，来源图最多256文件/128MiB。读取并重算原始派生结果，结束前复查文件哈希；不提供事务或作者身份认证。

### cad_build_chain_evidence

必填inventory_path、occurrence_paths（2–50个不同叶实例）、chain_name（1–100字符）、output_path。可选grouping_path、grouping_review_path、evidence_paths（最多20个不重复文件/内容）；不传时省略字段。空间清单必须完整分页/层级；几何缺失可以保留。

evidence_paths支持connection_review_schema_version=1、proximity_review_schema_version=1、face_contact_review_schema_version=1的结果文件。工具沿源路径/hash重算分组、轴线关系、连接复核、组件近接触与面探测判读；不能直接输入sw_*原始envelope或MCP摘要。面源上下文还需与本次空间清单的实例/配置/变换一致。

分组若有review_sha256，必须取得原始人工角色复核文件。新版cad_group_components额外保存review_path；旧文件需显式grouping_review_path。此字段只补充出处，不改变分组算法。角色manual_confirmed仍不等于刚体确认。

连接复核来源验证后，另把根配合中准确映射到两个实例但无轴线候选的对纳入；复用同一配合状态判读，geometric_candidate_indices=[]，不会伪造几何证据。源覆盖保存original_review_coverage及root_mate_source；多实例/未映射记录保持unmatched。

输出chain_dossier_schema_version=1、algorithm_version=1，保存parameters、inventory_source、input_files（完整来源路径/hash）、members、pairs、sources、boundary_evidence、outside_scope_records和coverage。范围是显式选择，不是自动识别链路；全部N(N−1)/2对保留。

每对有pair_id、occurrence_paths、evidence、review_flags、evidence_status（candidate_evidence/unknown/needs_reconciliation）、missing_evidence_families、review_state=pending。证据以kind区分connection/component_proximity/face_contact，保留源路径/hash、阈值、重放记录和evidence_id。replayed_pair_index定位重放结果，不当作跨文件CAD ID；原始细节沿source_path和来源绑定定位。只有未测/失败记录时仍为unknown。

| review_flags code | 解释 |
| --- | --- |
| DIFFERENT_DISTANCE_THRESHOLDS | 不同阈值导致分类不可直接比较 |
| DISTANCE_CLASSIFICATION_DISAGREEMENT | 同阈值的组件距离快照分类不同，需核对时间/几何 |
| GEOMETRY_SCOPE_REQUIRES_REVIEW | 组件上下文距离大于放置后定义面的某个测点间距，需核对装配切除/范围/时刻；不是自动矛盾裁决 |

compilation_complete=true表示清单成功形成；complete=false可由SOURCE_INCOMPLETE或UNASSESSED_CHAIN_PAIRS产生。缺少某证据类别只是缺口，不强迫每个真实连接具备所有类型。始终requires_review=true、mechanical_relation_confirmed=false、solidworks_modified=false。

主要拒绝码：INVALID_CHAIN_SCOPE、DUPLICATE_CHAIN_SOURCE、GROUPING_REVIEW_SOURCE_REQUIRED、EVIDENCE_MISMATCH、INVALID_CHAIN_SOURCE、CHAIN_SOURCE_LIMIT。拒绝不会写成功文件；缺失输入可省略，但已提供且损坏的输入不能静默忽略。

### cad_apply_chain_review

必填chain_path、review_path、output_path。基础文件必须为原chain dossier，工具按其parameters重新生成并核对；不把已复核结果继续当基础，也不按索引迁移决定。

人工输入chain_review_input_schema_version=1、chain_sha256、reviewer（非空，最多200字符）、reviewed_at（ISO带时区）、decisions。每条决定含pair_id、decision、relation_type、reason（非空，最多4000字符）、evidence_ids，以及可选acknowledged_flags。未提到的对保持pending；evidence_id必须属于该对，不重复。

confirmed仅接受rigid_connection/revolute_joint/prismatic_joint/other_connection；rejected/pending/conflict的relation_type为null。confirmed/rejected必须确认该对所有review_flags code已处理，理由由实际人工判断提供。工具验证格式和来源，不认证复核人，也不代替其判断。

输出chain_review_schema_version=1，保留基础清单/复核输入路径hash、成员、证据、边界和来源错误。human_review记录basis=human_declaration、人员/时间/理由、human_confirmed；cad_verified=false、motion_parameters_verified=false、mechanical_relation_confirmed=false。rejected表示人工不接受该候选，不等于已证明不存在连接。

human_review_complete只统计是否仍有pending/conflict，和来源complete独立；来源partial仍保留且requires_review=true。没有经过CAD/求解验证的轴线、限位、行程、刚体或运动副不会被创建。输出始终solidworks_modified=false。

INVALID_CHAIN_REVIEW表示哈希、归属、时间、决定或引用不合法；UNACKNOWLEDGED_CHAIN_FLAGS表示最终声明未处理全部提示；EVIDENCE_MISMATCH表示清单/源文件变动。所有旧意见必须对新清单重新核对，不能改哈希绕过。

## 0.11.0：面目录、局部面探测与候选复核

三项工具与配合、圆柱轴线、组件距离独立；不要求先执行这些链路。面目录/探测的原始 envelope 由调用方保存到新文件；复核工具直接写 outputs 新文件。全部保持模型只读，离线工具不连接 CAD。

### sw_component_faces

必填 expected_document_token、occurrence_path；max_bodies 默认20/范围1–100，max_faces 默认200/范围1–1000。只读取已解析、已加载且配置匹配的叶零件；在位编辑拒绝 IN_CONTEXT_EDIT_ACTIVE，不自动修改状态。

data.face_inventory_schema_version=1，geometry_scope=referenced_part_definition，assembly_instance_features_evaluated=false。target 保存完整实例/父路径/源文件/引用配置/源零件/根变换。faces 每行保存 body_index、face_index、descriptor、face_reference、errors；face_count、reported_body_count、inspected_body_count、complete/truncated 描述实际覆盖。BODY_LIMIT/FACE_LIMIT 及逐面失败保留 partial。

descriptor 包含 surface_type（plane/cylinder/other）、surface_parameters_part（平面6值/圆柱7值/其他null）、area_part_m2、uv_bounds（umin,umax,vmin,vmax）、body_type（0实体/1曲面体）、face_in_surface_sense（true表示与底层法向相反）。UV范围不是裁剪轮廓；描述符不是完整拓扑哈希。面持久引用经过 GetPersistReference3 → GetObjectByPersistReference3 → IsSame 回读；仅用于解析真实对象，不把 ID 字节相等当跨上下文身份结论。

### sw_probe_face_pair

必填 expected_document_token、left、right、seed_points_root_mm。left/right 各为 {face_inventory_path,body_index,face_index}，从原始面目录中选记录；两面必须属于不同实例。种子为1–8个根装配毫米坐标[x,y,z]，无默认值；需保存用户指定或读取的模型位置来源。max_iterations 默认20/范围1–50，convergence_tolerance_mm 默认0.001/范围(0,1]，仅作数值稳定阈值。

只支持解析平面/圆柱；other 返回 UNSUPPORTED_FACE_SURFACE。读取来源文件哈希，检查同一文档/配置、当前实例上下文与持久面描述符。源几何不含装配级切除。每次将根点逆变换到零件坐标，调用 **IFace2.GetClosestPointOn**（返回XYZ+UV）在实际有限面查询，再正变换一次；交替查询左右面，保留每个种子的结果。对最终点做同面回读核对，误差超过1e-8 m拒绝 FACE_POINT_NOT_ON_FACE；此数值一致性检查不是工程公差。

法向由 ISurface.EvaluateAtPoint 返回11值中的前三值取得；FaceInSurfaceSense=true 时翻转，再按实例变换的逆转置方向归一化。保存原始评价数组和根单位法向。法向失败仍可保留点距；点失败 metrics=null；不得写成零间隙。曲面体法向不解释为实体外法向。

data.face_probe_schema_version=1；method=bounded_alternating_IFace2.GetClosestPointOn；geometry_scope=placed_part_definition_faces。sources 绑定两个目录及SHA256、实例和面记录，parameters 保留种子/预算，samples 每项包括 seed_index、iterations、converged、left/right 的 part_m/UV/root_m、normal_left/right、metrics 和 errors。metrics 包括根坐标点、gap_m/mm、根法向、opposition_error_deg（相反方向误差）和 gap_alignment_error_deg（两法向朝向点差的误差；零间隙为null）。best_seed_index 选有效种子结果中的最小测点间距；无有效点时null，measurement_status=unavailable，否则sampled。

- FACE_PROBE_ITERATION_LIMIT：保留已验证的点，整体partial。稳定迭代不证明最小值，也不代表全面检查。
- EVIDENCE_MISMATCH、FACE_GEOMETRY_MISMATCH、FACE_REFERENCE_UNRESOLVED：来源/当前几何不匹配，先核对重采。
- INVALID_FACE_POINT、INVALID_FACE_NORMAL：保留错误与可用字段，不补造。
- COMPONENT_CHANGED、DOCUMENT_CHANGED、GEOMETRY_CHANGED：检测到上下文/面变化，拒绝整次混合结果。
- API查询均在同一STA中串行，COM对象不返回客户端；单次调用仍可能阻塞。

### cad_review_face_contacts

必填 probe_paths（1–100个不重复原始探测 envelope 文件）、output_path、contact_tolerance_mm（有限非负）、angle_tolerance_deg（0–90）。阈值须显式给出并说明工程依据或探索用途。每个来源绑定面对应只取一个快照，反序仍判重复。源目录必须仍存在且哈希一致；工具重算点坐标、法向翻转和测点间距，拒绝派生值被改写。

| review_state | 精确范围 |
| --- | --- |
| near_face_contact_candidate | 有阈值内测点对；实体面的局部法向相反，非零点差方向也与两端外法向相向，仅为候选 |
| near_points_orientation_unconfirmed | 测点接近，但法向失败/方向不满足或属于曲面体 |
| sample_gap_above_tolerance | 当前测点间隙高于阈值；不能证明整面分离 |
| unresolved | 所有种子均无有效点对 |

输出 face_contact_review_schema_version=1、scope=provided_local_face_probes_only、pairs、counts、complete/errors；每对包含原始文件哈希、具体面、最佳测点、局部法向和converged状态。原始 partial 继续保留；EVIDENCE_MISMATCH、INVALID_FACE_PROBE_SOURCE、DUPLICATE_FACE_PROBE 拒绝写成功结果。

所有结果保持 requires_review=true、global_minimum_proven=false、contact_confirmed=false、mechanical_relation_confirmed=false。**局部大间隙不能排除其他区域接触；小间隙和相向法向不能确认接触区域、干涉、包含、孔轴配合、刚体或运动副。** 法向是面边界/接缝处的局部曲面方向，不是接触拓扑分析。工具不会自动并入配合面或同轴候选结论。

官方依据：[IFace2.GetClosestPointOn](https://help.solidworks.com/2025/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IFace2~GetClosestPointOn.html)、[FaceInSurfaceSense](https://help.solidworks.com/2025/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IFace2~FaceInSurfaceSense.html)、[EvaluateAtPoint](https://help.solidworks.com/2024/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.isurface~evaluateatpoint.html)、[GetUVBounds](https://help.solidworks.com/2025/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IFace2~GetUVBounds.html)、[PlaneParams](https://help.solidworks.com/2026/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISurface~PlaneParams.html)。

## 0.10.0：邻近工作清单、距离与离线复核

三项工具相互独立；距离读取不要求存在配合/圆柱，离线工具不连接 COM。输入 JSON 必须在项目内，输出是 outputs 下新文件；MCP 与 CLI 共用工具实现。

### cad_proximity_candidates

必填 inventory_path、output_path、max_box_gap_mm（有限非负毫米数，无默认工程值）。空间来源必须为完整分页/层级的原始 envelope，单位 m/mm；几何缺失可保留，但不能用一页或缺父节点的清单代替。可选 occurrence_paths：2–200 个不同完整叶路径；不传时最多支持 5000 个叶实例。max_pairs 默认 20000、范围 1–200000；max_candidates 默认 200、范围 1–2000。

输出文件 proximity_schema_version=1、algorithm_version=1，绑定 inventory_path/SHA256/document/parameters。候选包含 occurrence_paths、box_gap_hint_mm、basis=approximate_root_aabb、measurement_required=true；保留 scope_occurrence_paths、unranked_occurrences、coverage、pair_scan_complete、complete/truncated/errors。

近似盒间距只用于安排测量。按路径顺序在预算内检查，再按已检查对的盒间距排序；不是全局最近邻。SOURCE_INCOMPLETE、UNRANKED_OCCURRENCES、PROXIMITY_PAIR_LIMIT、PROXIMITY_CANDIDATE_LIMIT 均保留 partial；不在清单内的对仍未知。盒重叠不是接触/碰撞证据。

### sw_component_distance

必填 expected_document_token、left_occurrence_path、right_occurrence_path；一次一对不同、已解析叶零件。检查源零件已加载且配置一致；子装配容器、在位编辑不支持，不自动解析/切配置/退出编辑。调用根装配文档 IModelDoc2.ClosestDistance，传入两个 IComponent2；多实体零件可作为目标，具体几何支持需实机核对。

返回原始 envelope：component_distance_schema_version=1、scope=two_resolved_part_occurrences、geometry_scope=assembly_component_context、document、targets、captured_at_utc、snapshot_atomic=false、measurement_status、measurement、complete。targets 绑定实例/父级/文件/引用配置/根变换和源零件上下文。

measurement 包括 distance_m/mm、point_left_m/mm、point_right_m/mm、point_separation_m、frame=root_assembly。最近点按左右输入顺序，已是模型根装配坐标，不再乘组件变换；未读取爆炸/演示显示位置，也未返回持久面 ID 或接触区域。数值自检采用 1e-8 m 绝对/1e-7 相对误差核对点间距与返回标量，仅为 API 返回一致性检查，不是工程接触公差。

- 返回 -1：DISTANCE_NO_SOLUTION；负值/空点/非有限数：INVALID_DISTANCE_RESULT；点间距不符：DISTANCE_POINT_MISMATCH。保留 measurement=null、measurement_status=unavailable 和 partial，不补零或盒间距。
- 同实例：INVALID_ARGUMENTS；未知路径：COMPONENT_NOT_FOUND；未解析：UNRESOLVED_COMPONENT；子装配：NOT_PART_COMPONENT；配置不匹配：COMPONENT_CONFIGURATION_MISMATCH；在位编辑：IN_CONTEXT_EDIT_ACTIVE。
- 目标查找不完整拒绝 COMPONENT_LOOKUP_INCOMPLETE；文档或已检测的目标上下文改变拒绝 DOCUMENT_CHANGED/COMPONENT_CHANGED，不保留混合证据。几何读取不是事务，token 不是几何版本号。
- 不改变选择、显示、位姿、配合或文档；不强制重绘。单次 COM 调用仍可能阻塞，超时不代表取消。

### cad_review_proximity

必填 proximity_path、distance_paths（1–200 个原始 envelope 文件，不重复路径）、output_path、contact_tolerance_mm（有限非负毫米数，无默认工程值）。输入工作清单保留空间源路径/哈希；工具从原空间重算筛选和范围以拒绝被改写的候选。每对只允许一个距离快照，反序仍为同一对。

核对文档/配置、完整实例、来源位姿、单位、测量类型以及米/毫米/最近点一致性。混用源文件或修改工作清单返回 EVIDENCE_MISMATCH；反序重复为 DUPLICATE_DISTANCE_SOURCE，范围外为 DISTANCE_OUTSIDE_SCOPE，格式错误为 INVALID_DISTANCE_SOURCE。致命 envelope data=null 不作为可用距离源，保留在独立错误记录中。

| review_state | 含义 |
| --- | --- |
| near_contact_candidate | API 距离 ≤ 明确阈值，仅近接触候选 |
| separated_at_measurement | API 距离 > 阈值，不证明无机械连接 |
| unresolved | 已尝试但 API 无有效值，保留错误与 null |
| unmeasured | 待测清单中未提供距离证据 |

复核文件 proximity_review_schema_version=1；保存 pairs、counts、distance_sources、sources、unranked_occurrences、worklist_coverage、complete/errors。每对关联原始哈希、测量和按实例归属的 point_by_occurrence_mm。未测或部分来源导致 partial；输出始终 requires_review=true、contact_confirmed=false、mechanical_relation_confirmed=false。小/零距离不能区分接触、穿透或包含；组件最近点不证明具体圆柱面接触，不自动合并到连接/配合面复核。

官方 API 依据：[ClosestDistance](https://help.solidworks.com/2025/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDoc2~ClosestDistance.html)、[IsEditingSelf](https://help.solidworks.com/2024/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDoc2~IsEditingSelf.html)、[GetBox 近似值限制](https://help.solidworks.com/2018/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IComponent2~GetBox.html)。ClosestDistance 的圆柱面输入存在轴线语义；本工具传组件对象，不传候选圆柱面，不将该结果解释为特定面间隙。

## 结果

所有工具返回 `schema_version`、`status`（`ok` / `partial` / `error`）、`data` 和 `errors`。MCP 致命工具错误同时设置 `isError: true`；部分结果保留数据并标记 `partial`，不得当作完整验收。

组件节点包含 `occurrence_path`（完整 Name2）、父路径、名称、文件路径、引用配置、原始抑制状态枚举、是否抑制及读取状态。重复文件的不同实例分别保留，根装配单独存于 `document`，不计入 `component_count`。`complete: false` 表示遍历不完整；数量只代表实际读取的节点。

抑制/轻化/内部 ID 错误、读取异常、遍历深度或数量上限都会产生明确记录。缺失或重复实例名称使用 `@unreadable/...` 标记，不能用其选择组件。相同名称产生歧义时拒绝选择。

`sw_set_view` 的成功表示 API 调用完成；它不会把返回 void 的 API 当作视觉核对证据。`sw_rebuild` 检查重建返回值，不声称已全面检查配合或几何健康度。

## 显示工具

`sw_set_display_visibility` 用 `visible: false` 隐藏，`true` 显示。`target` 取值：

| target | 对象 |
| --- | --- |
| `planes` | 基准面 |
| `axes` | 基准轴 |
| `temporary_axes` | 临时轴 |
| `sketches` | 草图 |
| `origins` | 原点 |
| `coordinate_systems` | 坐标系 |
| `all_reference_geometry` | “隐藏所有类型”总开关，范围还包括注解等对象；visible=true 仅解除总屏蔽 |

这些是当前零件/装配的类别过滤器，不是单个特征的显示属性。隐藏“基准面”不会删除或抑制特征；显示类别不会强制显示已单独隐藏的基准面。工程图暂不支持这组辅助对象工具。

查询返回 `visibility`（各类别开关）、`hide_all_reference_geometry`（总屏蔽）和 `display_allowed`（类别开关且未被总屏蔽）；不声称画面上一定存在该类对象。设置返回 `previous_visible`、`visible`、`changed` 和 `saved: false`。重复设置同一状态不会反向切换。调用 `IModelDocExtension.Get/SetUserPreferenceToggle`，以回读状态判断成功，不能把设置隐藏时的 false 返回直接当作失败。

0.5.0 使用实际存在的 `pythoncom.LoadTypeLib(完整绝对路径)`，从当前 SolidWorks 安装目录的 `swconst.tlb` 解析枚举；只读取，不注册、不运行 makepy、不启动另一实例。无法加载时返回 `DISPLAY_CONSTANTS_UNAVAILABLE`，不猜数值。`DISPLAY_MISMATCH` 表示回读不匹配；`DISPLAY_READ_FAILED` 表示无法可靠读取。总屏蔽开启时，单类显示返回 `DISPLAY_BLOCKED`，不会擅自放开其他类别。

组件显隐使用完整 `occurrence_path`，通过 `IComponent2.Visible` 读写自身标志。返回 `visible`、`hidden_parent_paths` 和 `visible_with_parents`；这些不是像素可见性或遮挡检测。父级隐藏时显示子件返回 `PARENT_HIDDEN`；目标/父级抑制或轻化时返回 `UNRESOLVED_COMPONENT`。层级遍历不完整或实例名称不可靠时返回 `COMPONENT_LOOKUP_INCOMPLETE`，不据部分树猜测目标。重复文件的其他实例不受单实例工具直接修改；隐藏子装配会遮挡其子件。操作无需选择，不清空已有选择。

0.5.0 两个显隐设置工具返回 `redraw_requested=false`：以 API 回读验证，不再调用强制整机 `GraphicsRedraw2`；组件设置仅遍历一次，回读原目标和父实例。正常窗口刷新交给 SolidWorks，画面仍需人工核对。设置 API 自身仍可能阻塞，不能保证任何模型均不超时。

显示操作可能改变文档内存状态，工具均不保存。调用期间不要改变配置或显示状态；文档 token 不是几何或显示状态版本号。组件显隐不处理多实体零件中的独立实体。

## 空间字段（0.3.0 起，0.5.0 改为分页）

两者仅支持装配。`sw_component_spatial` 从组件树取得完整 `occurrence_path`；返回 `data.component`。`sw_spatial_inventory` 返回 `data.components`；默认 `max_components=500`、`max_depth=64`，范围分别为 1–5000、1–128。单实例查询为确认目标唯一性，最多遍历 20000 个节点、128 层；不能确定唯一目标时拒绝猜测。

公共元数据包括 `spatial_schema_version=1`、文档/配置/token、UTC 采集时间、SolidWorks revision、单位、矩阵约定、`snapshot_atomic=false`、实际读取数量、成功数量、`complete` 和 `truncated`。根装配不计入组件数量，子装配和未解析节点计入；同文件实例分别记录。单件查询的 `component_count` 为 1。实例路径不承诺跨重命名/修订稳定；token 不是几何版本号。

每个空间节点继承组件树字段，并增加：

| 字段 | 含义 |
| --- | --- |
| `transform.raw_array` | SolidWorks 原始 16 元素 Transform2.ArrayData，未改写 |
| `transform.to_root` / `to_parent` | 4×4 列向量矩阵：组件→整机根 / 组件→父组件，含缩放，平移单位 m |
| `transform.origin_root_m` / `_mm` | 组件原点在整机坐标中的位置，非包围盒中心/质心 |
| `transform.origin_parent_m` / `_mm` | 组件原点在父组件坐标中的位置；顶层与整机位置相同 |
| `bounding_box` | GetBox(false,false) 原始 6 元素 `raw_array_m`，整机轴对齐的 min/max/size/center，分别带 `_m` / `_mm`；`approximate=true` |
| `spatial_status` / `spatial_errors` | ok / partial / unavailable，以及字段级错误；缺失字段保留 null |

**坐标约定：** Transform2 已相对当前根装配，包括嵌套组件；不要再叠加父变换得到根坐标。原始数组前 9 项按行存轴方向，9–11 项是平移，12 项是缩放。规范矩阵将轴矩阵转置并乘缩放，平移不乘缩放。`to_parent_child = inverse(to_root_parent) @ to_root_child`；反向验证 `to_root_parent @ to_parent_child = to_root_child`。未包含临时 presentation transform，因此爆炸/展示位姿不能直接当作模型坐标。

**边界含义：** GetBox 返回近似包围盒，排除参考平面和草图；坐标按根装配解释，不再用组件变换二次转换。尺寸沿整机坐标轴，旋转时会改变；中心仅为盒中心。它不保证最小紧包围，不可用作精密尺寸、质心、行程或碰撞证据，重建后可能变化。显示隐藏不等于抑制，隐藏但已解析组件仍可读取。

只读取已解析实例，不自动解除抑制、轻化或加载缺失组件，不改变选择/显隐、重建或保存。`TRANSFORM_UNAVAILABLE` / `BOUNDING_BOX_UNAVAILABLE` 表示 API 无数据，`INVALID_TRANSFORM` / `INVALID_BOUNDING_BOX` 表示数组非有限、格式不符或变换无效；不补单位矩阵或零尺寸。子件根变换可用但父变换缺失时，局部矩阵为 null 并返回 `PARENT_TRANSFORM_UNAVAILABLE`，根变换与包围盒仍保留。

数量/深度限制返回 `partial`、`truncated=true`；其他读取失败也可产生 `partial`，检查 `errors`，不能只看 MCP `isError`。单实例查询仍保留全树遍历错误，目标字段可用不意味着整树完整。完整树中缺失目标返回 `COMPONENT_NOT_FOUND`；重复名称返回 `AMBIGUOUS_COMPONENT`；无法确认完整层级/唯一名称返回 `COMPONENT_LOOKUP_INCOMPLETE`。切换文档或配置返回 `DOCUMENT_CHANGED`，丢弃本次不一致结果。

空间 MCP 工具返回真实 JSON，不直接写文件；完整导出使用下述 spatial-export。读取期间不要编辑模型或切换文档/配置，长调用受共同超时规则限制。坐标含义的验收仍见 [0.3.0 清单](MCP_ACCEPTANCE.md#030组件空间信息)，分页与完整性见 0.5.0。

## 分页与完整导出（0.5.0）

`sw_spatial_inventory` 新增参数：

| 参数 | 默认/范围 | 含义 |
| --- | --- | --- |
| `offset` | 0 / 0–5000 | 按完整实例路径排序后的起始序号 |
| `page_size` | 20 / 1–100 | 本次最多读取多少个组件的变换/包围盒；慢机器建议 5 |
| `include_bounding_boxes` | true | false 跳过 GetBox，保留 transform；bounding_box=null、bounding_box_status=not_requested，不补零 |
| `expected_inventory_signature` | 首次可省略 | 后续页必填首个结果的 64 字符 inventory_signature |

`max_components` 限制整次树遍历（默认 500），不是页大小；`max_depth` 同样约束整树。每页先遍历实例元数据校验范围，只为本页读取空间字段（父变换按需读取），GetBox 不跨页批量调用。签名绑定文档 token、排序后的实例元数据、范围和包围盒开关；后续页保留相同参数。签名不同返回 `INVENTORY_CHANGED`，缺少续页签名返回 `INVALID_ARGUMENTS`，无效 offset 返回 `PAGE_OUT_OF_RANGE`。签名不是几何版本号，无法检测所有原地几何变化；读取期间不要编辑/重建，`snapshot_atomic=false`。

返回 `pagination={offset,page_size,has_more,next_offset,total_components}`。has_more=true 时继续下一页。`component_count` 为本页数量；`page_complete` 表示该页字段及遍历无错误；`hierarchy_complete` 表示未截断且层级可读，未解析节点也会使其为 false。`collection_complete` 只有单次覆盖全范围时为 true；最后一页 offset>0 仍为 false。`complete` 同时要求完整集合且无错误；一页 status=ok 不代表读完整机。`truncated` 指遍历数量/深度截断，与正常分页 has_more 区分。

推荐在仓库根目录执行：

```powershell
python -m cadkin spatial-export --page-size 5 --output outputs/spatial.json
```

CLI 先读当前 token，再在同一 STA 会话逐页采集、核对签名/连续序号/唯一实例；默认范围 5000、64 层，可用 `--max-components` / `--max-depth` 调整。每页使用 180 秒的调用上限，整个多页导出可以超过 180 秒；调用此 CLI 的客户端外层时限也应允许完整导出。`--without-boxes` 可跳过较慢的 GetBox。写新文件，存在则拒绝；导出前预检路径，保存原始 envelope 和字段级错误。全部页收齐后移除单页 pagination，增加 `pages_collected`、`total_components` 和 `next_offset`；collection_complete=true 不代表层级没有截断或几何全部可读，仍要检查 hierarchy_complete/complete/errors。

中途失败时保留已经收集的组件和实际错误，`collection_complete=false`，`next_offset` 为已读数量。不要将此文件用于分组；TIMEOUT 仍需检查现场、重启 MCP，之后选新文件重采。单页即使很小，某一个 COM 调用也可能阻塞；分页减少每次工作量，不承诺取消 COM 或固定耗时。

## 角色候选分组（0.5.0）

`cad_group_components` 的输入/复核文件必须为项目内 JSON（最大 64 MiB），输出必须为 `outputs/` 下尚不存在的 JSON；不使用 `CADKIN_ALLOWED_ROOTS` 扩展此离线工具的输入范围。CLI `group` 与 MCP 共用 `cadkin/tools/grouping.py`，无需 SolidWorks 运行，也不会启动软件。MCP 返回精简摘要和文件路径，详细结果已写入文件。

```powershell
python -m cadkin group outputs/spatial.json --output outputs/groups.json
# 如需仅分析一个真实子装配：追加 --scope "组件树里的完整实例路径"
```

输入必须是实际空间结果 envelope：spatial_schema_version=1、collection_complete=true、hierarchy_complete=true、truncated=false，实例路径唯一、父链完整无环、数量一致。兼容旧版 complete=true 的全量结果。单页/截断/未解析层级返回 `GROUPING_REQUIRES_COMPLETE_INVENTORY`，错误结构返回 `INVALID_INVENTORY`。空间字段单独不可读可保留，source_errors 传递且结果摘要为 partial；不补造几何。

四种 role：`fixed_base`、`moving_platform`、`transmission_related`、`pending`。只分配所选范围内的叶实例，子装配容器单列数量；同文件多实例不合并。V1 根据实例末级名称的明确关键词给出候选；父装配名称不继承到子件。未命中/多角色冲突保持 pending，规则不能保证准确识别匿名 STEP。最近三个近似包围盒中心（毫米距离）仅辅助人工核对；不使用组件原点代替缺失盒中心，超过 2000 个叶实例不计算近邻，可缩小 scope。

输出文件为 `grouping_schema_version=1`，含 source（原文件 SHA256、文档/配置/采集时间）、scope、groups、counts、coverage、source_errors 和 limitations。每个 member 保留 occurrence_path、父路径、引用文件/配置、角色状态、evidence、原空间字段与邻近提示。自动状态仅 candidate/pending，`rigid_body_confirmed=false`；分类不是固定约束、刚体或运动副证据。coverage 的 scoped_leaf_occurrences 与各组数量和必须一致；assigned_once=true。requires_review=true 表示仍有未人工确认实例；零实例输入是空结果，不补造组件。

用户明确确认后，创建复核 JSON（以下路径/哈希为格式占位，必须替换为实际值）：

```json
{
  "inventory_sha256": "来自分组摘要的原始清单SHA256",
  "assignments": [
    {"occurrence_path": "实际完整叶实例路径", "role": "moving_platform", "decision": "confirmed", "reason": "用户实际确认的依据"}
  ]
}
```

用同一输入/范围调用工具并传 `review_path`，或 CLI 加 `--review outputs/review.json`，输出换新文件。暂缓项使用 role=pending、decision=pending、明确 reason；确认项 decision=confirmed、role 为前三类。哈希/路径/范围/重复项/角色/理由错误返回 `INVALID_REVIEW`；未列出的实例保持自动候选。manual_confirmed 表示应用了复核文件中的声明，工具不验证声明者身份，Agent 不得编造人工确认。

输入不存在或 JSON 无效返回 `INVALID_INPUT`，路径越界返回 `INVALID_PATH`，输出已有文件返回 `OUTPUT_EXISTS`，都不能写成成功。工具不创建 SolidWorks 特征树文件夹、不改显隐、不移动组件、不保存 CAD。

## 根配合状态与连接复核（0.8.0）

### sw_mate_inventory

必填 expected_document_token；可选 max_features=2000（1–20000）、max_mates=200（1–1000）、max_entities=16（1–64）、max_depth=32（1–64）。max_features 包含根特征及已进入 MateGroup 的子特征访问，max_depth 限制其子树深度；只遍历活动根装配 MateGroup，不打开子装配定义或遍历组件特征内部。组件身份映射另以完整实例树校验，结构不完整时拒绝。

从 IFeature.GetSpecificFeature2 读取 mate；抑制状态为 IsSuppressed2(swThisConfiguration=1, VT_EMPTY) 的单元素 Boolean 数组，读取 GetErrorCode2(out VARIANT_BOOL) 和 IsRolledBack。保留 feature_id/name/type，特征 ID 只在对应文档内使用。重复特征 ID 停止该分支并报告 FEATURE_REVISIT，不陷入循环或重复计数。IMateInPlace 等无法按当前字段读取的记录保留 partial，不丢弃。

结果 mate_inventory_schema_version=1，scope=active_root_assembly，subassembly_internal_mates_included=false；mates、mate_count、root_mate_groups、scanned_feature_count、component_contexts、complete/truncated、参数预算和错误均保留。没有 MateGroup/无配合且遍历正常时可为空；入口读取失败为 error，途中失败为 partial，不能冒充完整空列表。

| activity 字段/状态 | 含义 |
| --- | --- |
| suppressed / rolled_back | 当前配置中读取的抑制/回滚标志；状态读取失败为 null |
| feature_error_code / error_is_warning | 原始特征错误码；code=0 时 warning 不解释，保留 null；非零警告也作为问题记录 |
| state=suppressed / rolled_back | 相应特征状态 |
| state=unsuppressed_feature_issue | 未抑制、未回滚，但有非零特征错误/警告 |
| state=unsuppressed_no_feature_error | 未抑制、未回滚且没有报告特征错误；不是求解成功或有效独立约束证明 |
| state=unknown | 状态未能可靠读取；不补 false |
| solver_validity=not_evaluated | 本工具没有求解或验证自由度/冗余/实际运动 |

引用组件必须先按完整 Name2 命中当前树，再经 ISldWorks.IsSame 返回 swObjectSame=1 确认，才填写 reference_occurrence_path / verified_root_occurrence。0（不同）、2（不支持）或失败均不按同名猜测；空引用保留 root_or_unavailable。component_contexts 包含已确认实例的文件/引用配置/父级/根变换；引用到嵌套零件仍属于根配合记录，不说明已读子装配内部配合。

这些配合实体参数的所属装配已定位到根装配，entity_params_frame=root_assembly；继续保留原始 EntityParams，不解释选择类型为圆柱或直接构造运动轴。没有逐实体表面身份/形状对应。采集结束复读已知配合状态和引用实例变换；变动报 MATE_STATE_CHANGED/COMPONENT_CHANGED，配置/文档切换报 DOCUMENT_CHANGED，整次丢弃。不能检测所有几何编辑，snapshot_atomic=false，需保持模型不变。

预算错误 FEATURE_LIMIT/FEATURE_DEPTH_LIMIT/MATE_LIMIT/MATE_ENTITY_LIMIT 保留部分结果。MATE_STATE_UNAVAILABLE、MATE_INTERFACE_UNAVAILABLE、MATE_REFERENCE_UNRESOLVED 及原始 API 失败保留未知/错误；COMPONENT_LOOKUP_INCOMPLETE 不输出猜测映射。只读，不重建、不切换配置、不修改配合、不保存。

### cad_review_connections

必填 relations_path（0.7.0 关系结果数据对象）、mate_inventory_path（上述工具原始 envelope）、output_path（outputs 下新 JSON）。输入限项目内，输出独占新建，不覆盖。离线、不连接 COM；CLI 共用实现：

```powershell
python -m cadkin review-connections outputs/relations.json outputs/mates.json --output outputs/connections.json
```

要求关系文件引用的原始空间和圆柱文件仍存在：核对空间/圆柱 SHA256，文档/配置，已映射配合实例的完整路径、源文件、引用配置、父级和根变换。不同位姿不能仅凭相同 token 拼接。失败 EVIDENCE_MISMATCH，错误格式 INVALID_CONNECTION_SOURCE/INVALID_INVENTORY；错误时不创建结果。源哈希用于追溯，不验证作者或几何快照真实性。

按完整实例对归并几何候选索引；配合恰有两个不同的已验证引用实例时才关联到该对。另有根/未知引用时不会升级为无问题证据；多组件或没有候选对的配合保留 unmatched_mates。不把子装配容器配合展开成所有子件连接。

| review_state | 判定口径 |
| --- | --- |
| has_unsuppressed_mate_evidence | 至少一条记录所有引用已映射、配合字段读取无错误、未抑制/未回滚且 code=0；额外面核对失败单独保留 |
| unresolved_mate_evidence | 无上述记录，但有关联记录的引用或状态未知/读取不完整 |
| only_suppressed_or_feature_issue | 关联记录只有抑制、回滚或特征错误/警告 |
| geometry_only | 提供的根配合记录没有可关联到该实例对的证据 |

汇总状态有上述优先级，但所有记录都保留；其中的抑制或报错记录不会消失。relation 文件的每个面候选由 geometric_candidate_indices 回指，配合由 feature_id 回指原始 mates 文件。普通 sw_mate_inventory 输入的 association_level=occurrence_pair_only、face_match_confirmed=false：同一实例对的配合可能作用于其他面。0.9.0 面身份输入的升级条件见下节。

结果文件 connection_review_schema_version=1，含 pairs、counts、unmatched_mates、coverage、sources 路径/哈希、errors。覆盖范围为提供的几何候选和活动根配合；输入部分/错误导致 SOURCE_INCOMPLETE 与 partial/complete=false。完整仅表示此范围输入/处理完整，不表示工程连接模型完整或配合健康。无候选/无配合均不能推出无连接或自由运动。

保持 requires_review=true、mechanical_relation_confirmed=false、solidworks_modified=false。不能确认运动副、刚体、接触、行程或导程；旧 sw_component_constraints 的 GetMates 结果不能替代本工具所需的根配合清单。

## 配合面身份核对（0.9.0）

### 圆柱持久引用

sw_component_cylinders 新增 include_face_references（布尔，默认 false）；请求时每条圆柱增加 face_reference：encoding=base64、scope=referenced_part_definition、id。以 IModelDocExtension.GetPersistReference3 捕获，GetObjectByPersistReference3 解析回读并用 IsSame 核对。引用失败保留几何和 null 引用，errors/partial，不把原有轴线读取变成全空。结果 face_references_requested 记录选项；schema_version 保持向后兼容的可选字段扩展。

引用是零件文档内的对象定位信息；base64 字节不直接用于判断两个对象是否相同，body/face 索引仍仅定位一份哈希源文件中的记录。默认 false 不增加相关 COM 调用。

### sw_match_mate_faces

必填 expected_document_token、inventory_path、cylinder_paths（1–8 个项目内原始圆柱 envelope，来自 include_face_references=true）。清单必须收齐层级/分页；复用关系工具的文档、配置、单位、位姿和派生几何校验。空间/圆柱 SHA256 保留；同实例不接受重复来源。文件验证在工具层，只有普通数据交给 STA。

| 可选参数 | 默认 | 范围 |
| --- | --- | --- |
| max_candidate_faces | 100 | 1–500 |
| max_comparisons | 2000 | 1–20000 |
| max_features | 2000 | 1–20000 |
| max_mates | 200 | 1–1000 |
| max_entities | 16 | 1–64 |
| max_depth | 32 | 1–64 |

按完整实例路径、体/面索引确定预算内候选。复用根 MateGroup 遍历；对已验证实例、ReferenceType2=swSelFACES 的实体，延迟解析该实例对应的持久面 ID。持久状态必须 swPersistReferencedObject_Ok=0；当前零件配置/实例变换必须与来源一致，解析面必须仍为原始 CylinderParams（保守逐值核对，重新参数化也要求重采）。再用 IComponent2.GetCorrespondingEntity 转到该实例上下文，以 ISldWorks.IsSame 与 IMateEntity2.Reference 比较。只有返回 1 才匹配，0 为不同对象，其他值/异常为未知；不按几何近似兜底。

结束前重查实际比较的面身份/圆柱参数、实例映射和配合引用。检测到 GEOMETRY_CHANGED、MATE_REFERENCE_CHANGED、DOCUMENT_CHANGED、COMPONENT_CHANGED、COMPONENT_CONFIGURATION_MISMATCH 时拒绝混合结果。仍不是事务快照，不证明并发编辑从未发生；请求期间保持模型稳定。

返回为可直接给 cad_review_connections 的原始 envelope：mate_inventory_schema_version=1，新增 face_matching 元数据和每实体 face_match。face_match.status 为 checked、partial、unknown、not_face、outside_scope；matches 每条含完整实例、体/面源索引、source_path/source_sha256、identity_check。compared_faces 记录已完成的身份比较；空 matches 不能推断无连接。

face_matching 包括来源空间/圆柱路径与哈希、requested_faces、resolved_faces、comparisons、预算、unvisited_occurrences、complete/truncated。没有配合、非面或范围外引用时可能不解析任何候选；范围完整不代表输入面全部被解析。CANDIDATE_FACE_LIMIT/FACE_COMPARISON_LIMIT 保留 partial/truncated；引用失效、对应失败或不支持身份比较保留对应错误与已取得证据。旧文件未请求引用返回 FACE_REFERENCE_UNAVAILABLE，不能自动生成 ID。

### 离线复核扩展

cad_review_connections 无需新参数：mate_inventory_path 可传 sw_match_mate_faces 原始 envelope。校验 face_matching 的空间哈希及圆柱来源与关系文件完全对应；只有恰好两个实体分别命中某条几何候选的两端准确面，才给该配合 association_level=candidate_face_pair、face_match_confirmed=true，并在 candidate_face_matches 列出 geometric_candidate_index、left_entity_index、right_entity_index。其他记录仍是实例对关联；多实体配合不降成两面关系。

配合抑制/错误和身份结果独立保留；face_matching_errors 不将已知配合状态变成未知，但整体 partial 来源不升级为完整。新增 coverage.face_matched_mate_records 仅统计有面证据的配合记录，不是机械连接数。来源错误为 INVALID_FACE_MATCH_SOURCE；重采圆柱后必须重算关系。只读采集和离线复核都不确认有限面接触、装配切除形状、求解有效性、运动副或自由度。

## 离线组件关系候选（0.7.0）

`cad_component_relations` 不连接 SolidWorks。输入必须为项目内 JSON，输出为 outputs 内未使用的 JSON 文件。共享 CLI：

```powershell
python -m cadkin relations outputs/spatial.json --cylinders outputs/cylinder-a.json outputs/cylinder-b.json --distance-tolerance-mm 0.1 --angle-tolerance-deg 0.1 --output outputs/relations.json
```

上述 0.1 mm、0.1° 仅为探索示例，不是机械精度要求；必须以实际任务明确的公差为准。

| 参数 | 约束 |
| --- | --- |
| inventory_path | spatial-export 的原始完整返回；collection_complete/hierarchy_complete 为 true，不能是单页或截断树；选中实例必须有根变换且已解析 |
| cylinder_paths | 2–32 个 sw_component_cylinders 原始返回文件；每个完整 occurrence_path 一份，每份最多 1000 面。允许 partial，但部分状态/错误保留 |
| output_path | outputs 下新 JSON；不覆盖源文件或已有结果 |
| distance_tolerance_mm | 必填有限正数，毫米；没有工具默认值 |
| angle_tolerance_deg | 必填有限正数且不大于 5°；没有工具默认值 |
| max_pairs | 默认 10000，1–100000，跨实例圆柱面配对的计算上限 |
| max_candidates | 默认 1000，1–5000，输出候选面配对上限 |
| grouping_path | 可选 cad_group_components 生成的结果文件；source.inventory_sha256 必须与输入清单原始字节一致，仅复制角色上下文 |

校验 document token/标题/路径/配置/类型、实例路径、引用配置、根变换原始数组与完整空间基准一致。根变换必须数值相等；原始圆柱参数重新转换，冗余的根坐标/方向/半径用绝对 1e-9、相对 1e-12 的数值一致性阈值核对，**该阈值不是用户几何判断公差**。不额外乘父变换、不修补源 JSON。绑定失败为 EVIDENCE_MISMATCH，格式/单位/范围不符为 INVALID_RELATION_SOURCE，非法原始矩阵/圆柱参数也可能返回 INVALID_TRANSFORM/INVALID_CYLINDER，截断清单为 INCOMPLETE_INVENTORY；参数错误为 INVALID_ARGUMENTS，路径/覆盖沿用 INVALID_PATH/OUTPUT_EXISTS。输入错误不创建输出文件。

算法按完整实例路径、body_index/face_index 排序后，逐对比较不同实例的解析圆柱面。设单位轴向 u、v，夹角为 `atan2(|u×v|, |u·v|)`（转换为度），因此反向轴等价。取两组件根原点的中点 r，分别投影到两条无限轴线上得到 q1、q2，偏移为 `|q1-q2|`。严格平行时等于通常轴间距；近似平行时表示参考点附近的偏移，不是所有位置或有限面长度内的最大偏移。轴点沿自身方向移动不会改变这个几何定义；未使用远处相交导致为零的无限线最短距冒充同轴。

- `coaxial_candidate`：角度不超过角度阈值，且参考偏移不超过距离阈值。
- `parallel_candidate`：角度不超过阈值，但参考偏移超过距离阈值。没有接近距离筛选，远距离平行件也可能出现。
- 其他方向仅计入 coverage.nonparallel_pairs，不输出关系结论。相同半径不是筛选条件，不将半径差解释为配合间隙。

文件为 relation_schema_version=1 的数据对象：document、parameters、metric、sources、candidates、counts、coverage、errors。sources 保留每份文件路径/哈希/时间/完整性/源错误/零件配置与轴线数据，可选 role_context；candidates 含左右完整实例、快照内 body/face 索引、根轴线/半径、angle_deg、axis_offset_at_reference_mm、reference_root_mm。哈希绑定原始文件字节，不是来源真实性认证。

`comparison_complete` 只说明**所提供文件中已读取的面**是否全部配对；`complete` 还要求输入无部分状态/错误。输入 partial 导致 SOURCE_INCOMPLETE，即使已比较完仍不能说分析完整；计算/输出预算不足导致 RELATION_LIMIT、truncated=true，coverage 保留总配对数和实际计算数。候选为零、零圆柱或未提供的实例不证明无连接。工具返回简短成功/部分 envelope 和输出路径，完整结果在文件中。预算限制无断点续跑；缩小实例范围或增大预算后写新文件。

只分析 referenced_part_definition，仍不包含装配级切除；无限轴不提供有限面重叠、接触、孔轴类别或间隙证据。分割面不去重，计数是候选面配对数而非独立机械连接数。相同文件的不同实例保留独立身份。snapshot_atomic=false；一致文档/变换不证明采集期间几何未改，需在不编辑、不重建的同一会话采集。

结果总保留 requires_review=true、mechanical_relation_confirmed=false、solidworks_modified=false；不调用 LLM、解析 MateEntity 坐标、改变角色确认记录、合并刚体、判定运动副、行程或导程。

## Conda 与只读证据（0.6.0）

项目 MCP command 为 `["python","-m","cadkin.mcp_server"]`，从已激活 Conda 的终端启动 OpenCode。`sw_session_status` 额外返回 `data.runtime={python_executable,python_version,python_prefix,conda_prefix,matches_conda_prefix}`，软件未运行的 connected=false 结果也包含它。路径比较用于诊断当前解释器是否属于已声明的 Conda 前缀；无 CONDA_PREFIX 时匹配值为 null，不创建环境或修改 PATH。使用方法见 OPENCODE_START.md。

### 指定组件的约束

`sw_component_constraints` 必填 `expected_document_token` 与 `occurrence_path`；可选 `max_mates=100`（1–500）、`max_entities=16`（1–64）。只遍历目标组件的 GetMates，不扫描全部组件配合；不选择、解析、激活文档/配置、重建、保存或更改配合。

结果包含 constraint_schema_version=1、文档/实例/父路径、采集时间、snapshot_atomic=false、fixed_state、mates、reported_mate_count、read_mate_count、complete、truncated 和 errors。

- fixed_state.value 仅对根装配顶层实例调用 IsFixed，表示 API 的固定/浮动标志；false 不证明没有约束，true 不代表机械角色必为固定基体。嵌套实例为 null，scope=unavailable_nested_context，并返回 FIXED_STATE_CONTEXT_UNAVAILABLE，不能把根上下文的结果用作子装配内部状态。
- mates=[] / reported_mate_count=0 表示本次 GetMates 未返回配合；调用失败则 mates=null、count=null 并 partial，不能解释成没有配合。GetMates 可能含 IMateInPlace，无法读取的记录保留部分信息和错误。
- 每项保留快照内 mate_index、type_code（swMateType_e）、已知 type_name、alignment_code（swMateAlign_e）、entity_count、entities、read_status/errors。未知 type_code 原样保留、type_name=null；名称映射只解释枚举，不控制 CAD。未读取配合抑制或求解状态，constraint_activity 明示 unknown。
- 每个 entity 保留 ReferenceType2（swSelectType_e）的 reference_type_code、原 API 上下文 reference_component_name/reference_status、entity_params_raw。ReferenceComponent=null 时为 root_or_unavailable，不猜是地面件或指定组件。名称未经上下文校验，不自动映射为根装配 occurrence_path。
- EntityParams 根据 GetEntityParamsSize 验证数组长度和有限数值，保留原数组。参数点/半径为米，向量保持原值；所属坐标是“该配合所在装配”，未确定就不转换为根坐标。ReferenceType2 是选择类型，不是 swMateEntity_e 的几何种类；不能仅凭面类别将参数向量判为圆柱轴。
- 数量限制分别返回 MATE_LIMIT / MATE_ENTITY_LIMIT 和 truncated=true。字段失败保留其他可读字段；文档/实例/配置改变时返回 error 并丢弃本次混合结果。

### 指定零件的圆柱面

`sw_component_cylinders` 必填 token 与 occurrence_path；可选 max_bodies=50（1–200）、max_faces=500（1–5000）、max_cylinders=100（1–1000）。仅支持已解析零件实例，子装配返回 NOT_PART_COMPONENT。GetModelDoc2 未加载时 COMPONENT_MODEL_UNAVAILABLE；零件活动配置与实例 ReferencedConfiguration 不一致时 COMPONENT_CONFIGURATION_MISMATCH，不自动打开、解析或切换。

从匹配配置的 IPartDoc.GetBodies2(-1,false) 获取实体/曲面体（包括隐藏体），逐面 GetSurface/IsCylinder。只对解析圆柱面读取 CylinderParams，原数组为轴上一点 xyz、轴向 xyz、半径，长度量为米。按组件 Transform2 转换一次到根装配，轴向归一化，半径乘缩放绝对值。原点含平移，向量不含平移；负缩放不产生负半径。

返回 cylinder_schema_version=1、源装配/实例、source_part（文档/configuration/dirty）、引用配置、变换、geometry_scope=referenced_part_definition、assembly_instance_features_evaluated=false、cylinders、计数/错误/截断和单位。每条包含 body_index/face_index、raw_array、origin_part_m、axis_part_unit、radius_part_m、origin_root_m/mm、axis_root_unit、radius_root_m/mm、axis_is_unoriented=true、candidate_status=geometry_only。

这些是零件定义的解析曲面参数，未计入装配级切除等实例特有几何变化；即使配置匹配也需核对装配实际几何。零件定义可能是已打开文档的当前状态或其已加载保存状态。当前不拟合 NURBS/网格、不提取基准轴、不区分圆柱是孔还是轴；轴点不是端点或中心，不返回长度、导程、行程、接触或运动副结论。

max_faces 和 max_cylinders 是全调用预算，达到且仍有面未检查时返回 FACE_LIMIT/CYLINDER_LIMIT；超过体上限为 BODY_LIMIT。保留已经读取的结果，partial/truncated 不等于全量。逐体及每 20 面核对文档/配置，结束时核对实例变换；仍为非原子读取，调用期间不要编辑。逐面失败保留其他轴线；source/config/token/transform 变化时丢弃结果。cylinders=[] 仅表示读取范围内未得到解析圆柱面，不证明没有轴孔。分割面可产生同轴多记录，不做自动合并；索引可能随重建变化，不作为持久选择 ID。

两种工具均可通过 `python -m cadkin sw <工具名> --arguments '<实际JSON>' --output outputs/<新文件>.json` 保存真实 envelope。先取得实际 token 和实例路径，不复制占位值。上限减少总工作量，但不能取消单次阻塞 COM；仍沿用 TIMEOUT/OUTCOME_UNKNOWN 规则。角色分组继续独立运行，不会自动将这些证据写成人工确认。

## 软件启动（0.4.0）

`sw_start_application` 是独立的有副作用工具。通过固定 ProgID `SldWorks.Application` 的 Windows 本地 COM 注册启动桌面版软件；不接受 exe 路径、脚本或远程主机。没有进程时创建一个；已有单个进程时只连接并复用；已有进程连接失败或多进程时明确报错，不通过新建实例绕过。

启动成功返回 `connected=true`、`started`、`reused_existing`、`process_id`、`revision`、`startup_completed=true`、`visible=true`、`user_control=true` 和 `has_active_document`。后者可以为 false，启动不创建空白模型。检查 `ISldWorks.StartupProcessCompleted`（2015+），不把出现进程等同于启动完成；显示窗口后赋予用户控制，使正常成功启动的会话在 CLI/OpenCode 退出后保持运行。使用已有会话时不切换或保存当前文档，可能将原本隐藏的应用显示出来。

新创建的 COM 对象保留在同一 STA；后续调用先核对进程 PID 再复用，不强求刚启动的应用已经注册到运行对象表。启动前后重复核对进程；其他程序同时启动可能导致竞争，此时报告多实例，不擅自结束任一进程。不要从多个客户端同时发启动请求。

`APPLICATION_NOT_REGISTERED` 表示无法解析安装注册；`STARTUP_READ_FAILED` / `STARTUP_STATE_MISMATCH` 表示启动、可见性或控制状态无法确认。`STARTUP_PENDING` 表示等待期内启动尚未完成，检查许可/恢复/插件弹窗后可再次调用启动工具复用已有进程。`START_FAILED` 可能发生在进程已创建之后；不能据此断言软件未启动。激活结果不明且未检测到进程时，下一次启动返回 `START_OUTCOME_UNKNOWN`，要求先检查现场再重启 MCP；不会连续重复激活。阻塞 COM 调用超时仍按通用 `TIMEOUT` / `OUTCOME_UNKNOWN` 处理。

`wait_seconds` 只约束可返回控制权的就绪轮询；COM 激活或属性调用自身阻塞时，外层超时负责向客户端报告结果未知，不能撤销启动。不会自动处理许可、登录或恢复文件弹窗，不保证绕过本机首次启动配置。默认使用系统注册版本，实际版本以返回 revision 为准。

## 执行范围与失败处理

- 只面向 Windows。只读工具连接已有 SolidWorks；只有显式 `sw_start_application` 可以创建会话。当前只支持一个 SolidWorks 进程，多实例返回 `MULTIPLE_SESSIONS`。
- 分组是离线文件操作；所有 COM 创建、调用和释放在同一 STA 工作线程；CLI/MCP 共享工具层。运行时没有模拟成功的后端开关。
- 同时收到多个调用时返回 `BUSY`，不把操作排队留到稍后执行。客户端应逐个调用。
- MCP/CLI 默认 180 秒调用超时，项目 OpenCode 配置为 190000 ms。超时或取消不能中止已进入 SolidWorks 的 COM 调用；返回未知结果状态并停止接收新操作。先检查窗口/对话框和结果，再重启 MCP，避免重复执行。
- 打开路径默认限制在项目目录；额外输入目录可通过 Windows 环境变量 `CADKIN_ALLOWED_ROOTS` 配置，以分号分隔。这限制的是显式打开路径，不是文件系统沙箱，也不限制 SolidWorks 自行加载装配依赖。
- STEP 使用 `GetImportFileData` / `LoadFile4(..., "r", ...)`，保留用户导入设置，不强行改成装配。若实机版本/3D Interconnect 导入不兼容，可手动打开 STEP 后继续读取；错误必须如实记录。
- 第一版没有保存、覆盖、关闭文档、任意 Python/VBA 执行、修改配合或移动组件工具。

## CLI

`python -m cadkin sw <工具名> --arguments '<JSON对象>'` 与 MCP 调用相同实现。无参数工具不需要 `--arguments`。可加 `--output outputs/result.json` 保存到新文件；文件已存在则拒绝覆盖。成功/部分结果退出码 0，错误退出码 2；部分结果仍需检查 `status`。

原有 `python -m cadkin inspect <STEP或ZIP>` 保持不变，不依赖 Windows 或 MCP。

## 参考

- [开源代码来源与修改范围](../THIRD_PARTY_NOTICES.md)
- [显示类别与 API 对照](https://help.solidworks.com/2019/English/api/swconst/ViewHideShow.htm)
- [SetUserPreferenceToggle](https://help.solidworks.com/2025/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IModelDocExtension~SetUserPreferenceToggle.html)
- [SolidWorks 类型库位置](https://help.solidworks.com/2023/English/api/sldworksapiprogguide/Overview/Type_Libraries.htm)
- [IComponent2.Visible](https://help.solidworks.com/2019/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IComponent2~Visible.html)
- [组件显隐枚举](https://help.solidworks.com/2026/English/api/swconst/SOLIDWORKS.Interop.swconst~SOLIDWORKS.Interop.swconst.swComponentVisibilityState_e.html)
- [GetRootComponent3](https://help.solidworks.com/2019/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IConfiguration~GetRootComponent3.html)
- [LoadFile4](https://help.solidworks.com/2015/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISldWorks~LoadFile4.html)
- [IComponent2.Select4（三参数）](https://help.solidworks.com/2020/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.icomponent2~select4.html)
- [重建激活枚举](https://help.solidworks.com/2024/English/api/swconst/SOLIDWORKS.Interop.swconst~SOLIDWORKS.Interop.swconst.swRebuildOnActivation_e.html)

- [Transform2：相对根装配](https://help.solidworks.com/2018/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IComponent2~Transform2.html)
- [IMathTransform：16 元素布局](https://help.solidworks.com/2023/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IMathTransform.html)
- [MultiplyTransform：先旋转、缩放，再平移](https://help.solidworks.com/2017/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IMathPoint~MultiplyTransform.html)
- [GetBox：近似边界与限制](https://help.solidworks.com/2019/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IComponent2~GetBox.html)
- [按组件汇总装配包围盒的官方示例](https://help.solidworks.com/2023/english/api/sldworksapi/Get_Assembly_Bounding_Box_using_Components_Example_VB.htm)

- [UserControl：前台运行并在自动化程序退出后保留软件](https://help.solidworks.com/2024/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.ISldWorks~UserControl.html)
- [StartupProcessCompleted：包括启动插件的就绪状态](https://help.solidworks.com/2025/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISldWorks~StartupProcessCompleted.html)
- [pywin32 COM 创建接口](https://github.com/mhammond/pywin32/blob/main/com/win32com/src/PythonCOM.cpp)
- [pywin32 ProgID→IID 转换用法](https://github.com/mhammond/pywin32/blob/main/com/win32com/client/gencache.py)

- [LoadTypeLib 完整路径不注册类型库](https://learn.microsoft.com/en-us/windows/win32/api/oleauto/nf-oleauto-loadtypelib)

- [IsFixed：仅对顶层组件直接解释](https://help.solidworks.com/2022/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IComponent2~IsFixed.html)
- [GetMates：IMate2 或 IMateInPlace](https://help.solidworks.com/2019/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IComponent2~GetMates.html)
- [MateEntity 与索引](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IMate2~MateEntity.html)
- [EntityParams 与所属装配坐标](https://help.solidworks.com/2026/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IMateEntity2~EntityParams.html)
- [ReferenceType2：swSelectType_e](https://help.solidworks.com/2025/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IMateEntity2~ReferenceType2.html)
- [swMateType_e 名称映射](https://help.solidworks.com/2026/english/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swMateType_e.html)
- [GetModelDoc2 的定义/实例差别及配置限制](https://help.solidworks.com/2024/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.icomponent2~getmodeldoc2.html)
- [IPartDoc.GetBodies2](https://help.solidworks.com/2024/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.ipartdoc~getbodies2.html)
- [swAllBodies=-1](https://help.solidworks.com/2024/English/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swBodyType_e.html)
- [CylinderParams：7 元素与米制单位](https://help.solidworks.com/2022/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISurface~CylinderParams.html)

0.8.0 官方接口核对：

- [Mate2 所属 MateGroup 与特征访问](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IMate2.html?id=2.2.1.210)
- [IsSuppressed2 的数组返回](https://help.solidworks.com/2018/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IFeature~IsSuppressed2.html)
- [swThisConfiguration=1](https://help.solidworks.com/2025/English/api/swconst/SOLIDWORKS.Interop.swconst~SOLIDWORKS.Interop.swconst.swInConfigurationOpts_e.html)
- [GetErrorCode2 与 warning 输出](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IFeature~GetErrorCode2.html)
- [IsSame 身份核对](https://help.solidworks.com/2021/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISldWorks~IsSame.html)
- [swObjectSame=1，Unsupported=2](https://help.solidworks.com/2024/english/api/swconst/SOLIDWORKS.Interop.swconst~SOLIDWORKS.Interop.swconst.swObjectEquality.html)
- [GetID 的文档内身份](https://help.solidworks.com/2022/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.ifeature~getid.html)
- [EntityParams 所属装配坐标](https://help.solidworks.com/2026/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IMateEntity2~EntityParams.html)

0.9.0 官方接口核对：

- [GetPersistReference3：文档作用域与内部表示变化](https://help.solidworks.com/2023/english/api/sldworksapi/SolidWorks.interop.sldworks~SolidWorks.interop.sldworks.IModelDocExtension~GetPersistReference3.html)
- [GetObjectByPersistReference3：解析与输出状态](https://help.solidworks.com/2023/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IModelDocExtension~GetObjectByPersistReference3.html)
- [持久引用状态位掩码](https://help.solidworks.com/2026/english/api/swconst/SolidWorks.Interop.swconst~SolidWorks.Interop.swconst.swPersistReferencedObjectStates_e.html?id=2.10.1.596)
- [GetCorrespondingEntity：零件实体到指定组件上下文](https://help.solidworks.com/2025/English/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IComponent2~GetCorrespondingEntity.html)
- [IMateEntity2.Reference](https://help.solidworks.com/2026/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IMateEntity2~Reference.html)
- [对象身份与持久引用比较官方示例](https://help.solidworks.com/2023/English/api/sldworksapi/Compare_Selected_Objects_and_Their_Persistent_Reference_IDs_Example_CSharp.htm)
