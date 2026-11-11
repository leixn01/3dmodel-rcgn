# SolidWorks 工具接口

版本：0.6.0。以下 19 个工具已实现并注册；测试边界与用户 SolidWorks 2025 反馈见 `VALIDATION.md`。以 `cadkin/tools/solidworks.py` 的 JSON Schema 为参数依据。

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
| `sw_component_cylinders` | expected_document_token、occurrence_path；可选 max_bodies、max_faces、max_cylinders | 只读匹配配置的零件定义圆柱面；放置到实例根坐标，不含装配级切除 |
| `cad_group_components` | `inventory_path`、`output_path`，可选 `scope_occurrence_path`、`review_path` | 离线生成角色候选/应用人工复核，写 outputs 新 JSON，不调用 COM |

`view` 支持 front/back/left/right/top/bottom/isometric/trimetric/dimetric。接口用枚举值访问视图，不依赖中英文界面的视图名称。

先读取文档或组件树，使用返回的 `document_token` 操作。该值关联进程、文档路径/标题及活动配置；目标不匹配返回 `DOCUMENT_CHANGED`，不会操作新目标。它不是不可变几何版本号；模型重建或编辑后重新读取组件清单。工具执行期间不要在界面切换文档、配置或修改模型，COM 读取不是事务快照。

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
