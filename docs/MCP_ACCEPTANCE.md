# 当前版本 MCP 实机验收

目标：在安装 SolidWorks 的 Windows 电脑，通过 OpenCode 实际调用全部 17 个工具，核对返回值与 SolidWorks 窗口。离线测试及模拟后端不能作为实机通过证据。

## 准备与连接

1. 在仓库根目录执行 `git pull --ff-only`，按 README 安装或更新 `.[solidworks]`，退出并重启 OpenCode。无需提前启动 SolidWorks，先完成下面 0.4.0 的启动检查，再做模型操作。
2. 运行 `opencode mcp list`，确认 `solidworks` 已连接；进入 OpenCode，确认 MCP 工具目录包含当前 17 个工具。客户端可能给工具名添加服务器前缀。
3. 记录提交 SHA（`git rev-parse HEAD`）、Windows/Python/OpenCode/SolidWorks 版本。MCP 已连接仅代表协议可用，必须继续检查 `sw_session_status`。

用户最新反馈：在 SolidWorks 2025、STEP 导入装配的环境对旧版 15 个工具逐项调用，11 项 API 通过，2 项失败（辅助对象显示），2 项部分通过（组件隐藏实际生效但超时、空间清单小范围正确而全量超时）。原图报告 254 个组件、60 秒超时，未提供提交 SHA 或原始 JSON；该反馈不等于 0.5.0 已验收。0.4.0 起已有第 16 个启动工具、180 秒调用上限；本次修复不能仅靠调高超时宣称成功。先完成下面 0.5.0 复测。

## 0.5.0：修复与组件分组

### 更新与证据

```powershell
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install -e ".[solidworks]"
.\.venv\Scripts\python.exe -c "from importlib.metadata import version; print(version('3dmodel-rcgn'))"
```

应显示 0.5.0；退出并重新启动 OpenCode，检查 17 个 MCP 工具（新增 `cad_group_components`）。若仍为 15 个工具或仍报旧的 60 秒上限，先核对所用目录、解释器与 MCP 进程。使用已有打开的测试装配，记录 SHA、软件版本、PID、当前文档/配置/token，以及修改前的选择/显隐/dirty。不要为测试关闭有未保存工程的会话。

每次工具调用保存准确参数、原始返回、开始/结束时间与人工窗口结论到 `outputs/acceptance-0.5-<时间>/`。回读、耗时、窗口效果分别记录；没有窗口证据不填写视觉通过。

### 三个问题复测

| 项目 | 操作 | 通过标准 / 失败标准 |
| --- | --- | --- |
| 显示常量加载 | `sw_get_display_state({})`；然后用当前 token 调用 `sw_set_display_visibility`，target=planes、visible=false；再读状态；最后按记录恢复原类别值。 | 无不存在 LoadTypeLibEx 的错误；planes 回读 false，重复隐藏 changed=false、不会反向切换；返回 redraw_requested=false，其他类别不变。窗口核对辅助面是否隐藏。若总屏蔽影响恢复，记录 DISPLAY_BLOCKED，不擅自改变总开关。 |
| 组件显隐等待 | 从 `sw_component_tree` 取一个已解析叶实例完整路径，先读其显隐；调用 `sw_set_component_visibility` 改为 false，再 `sw_get_component_visibility`；恢复原状态。 | 设置工具本身正常返回，visible 回读匹配、saved=false、redraw_requested=false；当前选择与其他重复实例不被改写。记录实际耗时，不能仅凭之后查询已隐藏就判设置通过。若仍 TIMEOUT，则标部分/失败并记录实例、耗时、弹窗；不要重复执行直到检查现场。 |
| 单页读取 | 当前 token，`sw_spatial_inventory` 参数 page_size=5（max_components=5000、max_depth=64）。 | 本页最多 5 项；实际组件多于 5 时 has_more=true、next_offset=5、collection_complete=false；total_components 与范围内树数量一致。接续 offset=5、expected_inventory_signature=首个签名，其他参数不变。单页 GetBox 不跨全装配循环。 |
| 完整分页导出 | 用下方 CLI page-size=5 导出，整个过程不编辑/重建/切换配置。 | collection_complete=true、hierarchy_complete=true、truncated=false；组件路径集合与同配置完整树一致且无重复，数量以当次实读为准（截图 254 不是硬编码标准）；无字段错误时 complete=true。抽查至少 3 个实例与 `sw_component_spatial` 一致，按 0.3.0 表核对坐标/盒。任何页失败时保存部分数据且 collection_complete=false，不误报完整。 |
| 跳过包围盒 | 另用新文件，加 `--without-boxes` 导出。 | bounding_boxes_requested=false，所有 bounding_box=null、bounding_box_status=not_requested，变换仍保留。没有包围盒不能伪装零尺寸；此文件可用于初步角色候选，但没有近邻盒中心提示。 |
| 分页错误 | 后续 offset>0 故意不传签名；或传入 64 个零的签名。 | 分别 INVALID_ARGUMENTS、INVENTORY_CHANGED；服务仍可查询活动文档。不要为测试主动改动原模型；自然遇到层级/配置变化时保留真实错误。 |

```powershell
.\.venv\Scripts\python.exe -m cadkin spatial-export --page-size 5 --output outputs/spatial-0.5.json
.\.venv\Scripts\python.exe -m cadkin spatial-export --page-size 5 --without-boxes --output outputs/spatial-fast-0.5.json
```

已存在文件需改名，不能覆盖。完整导出可能超过 180 秒，这是多个独立页的累计时间；调用 CLI 的终端/Agent 需允许足够的命令执行时间。单页仍超时时先核对现场、重启 MCP，再用 page-size=1 或 without-boxes 和新文件复测；也可能是单个组件 API 阻塞，不能承诺分页一定消除所有卡顿。

### 新增分组与修正

```powershell
.\.venv\Scripts\python.exe -m cadkin group outputs/spatial-0.5.json --output outputs/groups-0.5.json
```

MCP 等价调用：`cad_group_components({"inventory_path":"outputs/spatial-0.5.json","output_path":"outputs/groups-mcp-0.5.json"})`。详细 JSON 已写入文件，返回精简摘要；不要求从聊天输出重建文件。

| 项目 | 操作 | 通过标准 / 失败标准 |
| --- | --- | --- |
| 候选覆盖与证据 | 读 groups JSON 与源清单，检查每个 role/members/evidence；抽查固定/移动/传动候选或待确认实例。 | 四类计数之和等于 coverage.scoped_leaf_occurrences；每个叶实例出现一次，子装配容器另计，同文件重复实例未合并。自动结果仅 candidate/pending，manual_confirmed_count=0；数值/路径来自输入。匿名或冲突名字可以全部 pending，不以“猜出多少类”评估成功。 |
| 范围选择 | 从真实树中选定一个子装配路径，CLI 加 `--scope "实际路径"`，输出换新文件。 | 只有该实例的叶子后代（若本身是叶则仅该实例）被分配，未混入其他升降链；范围不存在时报 COMPONENT_NOT_FOUND。不要仅靠名称假定此范围就是某条运动链。 |
| 几何辅助 | 抽查成员的 spatial_context 和 nearest_box_centers。 | 源变换/盒字段保持一致，距离为近似盒中心距离；缺盒无近邻提示，不把原点当中心，不把接近认定接触/碰撞/同刚体。 |
| 人工确认/纠正 | 在窗口按完整路径选中一个实例核对；用户明确确认后，按 TOOL_CONTRACTS 格式写 review JSON，再用同一源/范围加 `--review` 和新输出文件。 | 只有指定叶实例变为 manual_confirmed 或显式 pending，reason 保留实际依据；其他候选不变。inventory_sha256 与原始源文件一致；源变了则拒绝 INVALID_REVIEW。确认角色不改变 rigid_body_confirmed=false。 |
| 不完整输入 | 将单页原始返回保存新 JSON，再调用分组工具。 | GROUPING_REQUIRES_COMPLETE_INVENTORY，且没有写出分组文件；单页不能冒充整机。单独缺失几何、层级完整的输入可产生 partial 分组并保留 source_errors。 |
| 文件与模型保护 | 对相同 output_path 再次调用；查询 CAD 状态，并核对原输入哈希。 | OUTPUT_EXISTS，原输出和输入不变；分组本身不选择、不显隐、不移动、不改 dirty 或保存 CAD，也不创建新 SolidWorks 进程。 |

可直接交给 OpenCode：

> 按 docs/MCP_ACCEPTANCE.md 的 0.5.0 清单验证本次修复和组件分组。使用当前测试装配，记录显示与组件原状态，复测隐藏并恢复；按每页 5 个组件导出全部空间清单，核对实际实例路径集合，然后生成角色候选并报告待确认项。保存准确参数、原始 JSON 和耗时到 outputs 新目录，窗口效果与 API 回读分别列出。不要自动确认分组、编辑几何或保存覆盖原模型；超时先检查现场，不连续重试。

## 0.4.0：自动启动 SolidWorks

新增第 16 个工具 `sw_start_application`，默认参数 `{}`，可选 `wait_seconds=120`。仅维护 Windows；CI 只保留 Windows / Python 3.10、3.12。启动操作与打开模型分开，按下面顺序核对：

| 场景 | 操作 | 通过标准 |
| --- | --- | --- |
| 冷启动 | 软件原本未运行时，先调用 `sw_session_status`，再调用 `sw_start_application`；不要为制造场景关闭有未保存内容的工程。 | 状态查询返回 connected=false 且不启动；启动返回 started=true、startup_completed/visible/user_control=true，窗口真实出现，任务管理器只有一个目标 SLDWORKS.exe，PID 与返回一致。 |
| 打开模型 | 在同一会话调用 `sw_open_document` 打开仓库 STEP，再读取活动文档及组件树。 | 模型显示，目标文档正确；实际导入类型如实记录，没有要求用户先手动启动。 |
| 重复调用/已有会话 | 记下 PID、文档、选择及 dirty，连续再调用两次启动工具。也可在原本已运行的会话直接测试。 | started=false、reused_existing=true，PID 不变且无新增实例；当前文档、选择、dirty 不因启动工具变化。应用窗口可能被显示。 |
| 退出客户端 | 在上述成功启动后退出 OpenCode，检查 SolidWorks；再进入 OpenCode 查询。 | SolidWorks 和当前模型仍保留，再次连接返回同一 PID；未执行关闭或保存。 |
| 启动阻塞 | 若实际遇到许可/恢复/插件弹窗，保存原始错误和窗口现象。 | 未完成不得记成功；STARTUP_PENDING 处理弹窗后复用已有进程；TIMEOUT/OUTCOME_UNKNOWN 先检查现场并重启 MCP，不反复新建。未遇到则此项记未测试。 |

保存到 `outputs/acceptance-0.4-<时间>/`：提交 SHA、Windows/Python/OpenCode/SolidWorks 版本、每次参数与原始返回、PID 和人工窗口结论。不要通过自动关闭现有工程来制造冷启动场景；有未保存模型时先验证复用，冷启动项目留待合适时机。

可直接交给 OpenCode：

> 按 docs/MCP_ACCEPTANCE.md 的 0.4.0 清单验证启动功能。如果 SolidWorks 尚未运行，使用 sw_start_application 启动；已有会话就复用。打开仓库的测试 STEP，记录 PID 和活动文档，然后再调用启动工具确认不会重复开进程。把原始结果保存到 outputs 的新目录，列出需要我核对的窗口和退出客户端后的保留状态。不要关闭或保存我的其他工程。

## 原有 8 个工具逐项检查

按表中顺序串行执行。对视图、选择、清空和重建，先调用 `sw_active_document`，把返回的 `document_token` 原样传为 `expected_document_token`；不要编造 token，也不要在调用中切换文档或配置。

| 顺序 | 工具 | 实机通过标准 |
| --- | --- | --- |
| 1 | `sw_session_status` | `status: ok`、`connected: true`；`process_id` 与目标 SolidWorks 进程相符，`revision` 有效。只有协议连接或 `connected: false` 不算通过。 |
| 2 | `sw_open_document` | 输入 `examples/three_servo_lift/3X Lift Assembly.STEP`；模型确实显示且成为活动文档，返回的 `source_path`、`document` 与窗口一致。记录实际导入为装配还是零件，不根据扩展名推断。 |
| 3 | `sw_active_document` | 标题、路径、文档类型、配置及 dirty 状态与当前模型相符，返回 24 字符 `document_token`。导入时路径以 SolidWorks 实际报告为准，并与打开工具返回值核对。 |
| 4 | `sw_component_tree` | 装配输入返回 `status: ok`、`complete: true`；实例路径和父子层级正确，同文件的重复实例分别保留，根装配不计入 `component_count`。与特征树核对至少 3 个实例，尽可能覆盖重复实例与子装配。 |
| 5 | `sw_set_view` | 用 `view: "isometric"`、`fit: true` 调用成功，窗口确实切到等轴测并完整显示模型。仅有 API 完成消息不足以确认视觉结果；起始视角相同时先切到 `front` 再验证。 |
| 6 | `sw_select_component` | 从组件树选一个可读取、未抑制实例的完整 `occurrence_path`；返回路径一致、`selected_count: 1`，窗口/特征树选中的是该实例。不能只按零件文件名选择。 |
| 7 | `sw_clear_selection` | 紧接选择操作调用；`selected_count: 0`，窗口与特征树中的选中状态清除。 |
| 8 | `sw_rebuild` | 在工作副本上执行，返回 `rebuilt: true`、`saved: false`，活动目标仍正确；记录重建后的 dirty 状态及窗口中的错误提示。dirty 不一定变成 true。API 返回成功不代表所有配合与几何均健康。 |

重建工作副本可在 PowerShell 中创建，再通过 `sw_open_document` 打开并重新取得 token。目标已存在时使用已有副本或另选文件名，不覆盖：

```powershell
New-Item -ItemType Directory -Force outputs | Out-Null
if (Test-Path 'outputs/acceptance_model.STEP') { throw '工作副本已存在，请复用或改名' }
Copy-Item -LiteralPath 'examples/three_servo_lift/3X Lift Assembly.STEP' -Destination 'outputs/acceptance_model.STEP'
```

如果 STEP 导入为多实体零件，打开和活动文档检查仍可通过；组件树应报告 `NOT_ASSEMBLY`，组件树/组件选择验收记为“阻塞”，先确认本机导入方式。树返回 `partial` 或 `complete: false` 时保留 errors，记为“部分通过”，不能宣称完整读取。手动打开后读取成功可以证明读取功能，但不能替代打开工具本身的验收。

## 0.2.0：显示控制（5 个工具）

已打开模型时，先记下当前状态，按以下顺序验收，不必为了测试重复打开模型。

| 顺序 | 工具 | 实机通过标准 |
| --- | --- | --- |
| 9 | `sw_get_display_state` | 返回基准面等 6 类开关和总屏蔽值，与界面“隐藏/显示”菜单一致；只读取，不改变画面。 |
| 10 | `sw_set_display_visibility` | 新取 token，`target="planes", visible=false` 后回读为 false，窗口中的基准面隐藏；重复隐藏保持隐藏。恢复记录的原值；其他类别开关不被改动。基准面原本不可见时，仅回读不能替代视觉验证。 |
| 11 | `sw_zoom_to_fit` | 当前非标准或用户选择的视角保持不变，模型缩放适合窗口。 |
| 12 | `sw_get_component_visibility` | 指定完整实例路径，返回自身显隐与隐藏父路径；与装配树中的状态一致。 |
| 13 | `sw_set_component_visibility` | 隐藏一个可解析组件，回读 false 且窗口消失；同文件的其他实例保留。重复隐藏不反向显示，按原值恢复。选择状态不因工具被清空。 |

基准面测试支持 STEP 导入后的零件或装配；组件显隐仅支持装配。测试“显示”时若总开关或父级仍隐藏，应明确报阻塞，不自动显示其他对象。想验证其他辅助类别时对相应 target 重复第 10 项；单个已隐藏特征不会被类别开关强制显示。

## 0.3.0：组件空间信息

本次新增 2 个只读工具。前提：先完成会话/活动文档检查，实际类型为 assembly；读取过程中不操作界面。先记录 dirty、选择及显隐状态。获得当前 token 后串行调用，所有记录存入 `outputs/acceptance-0.3-<时间>/` 新目录。

| 编号 / 新能力 | 怎么调用与核对 | 通过标准 |
| --- | --- | --- |
| 14 单实例空间查询 | 从 `sw_component_tree` 取完整路径；调用 `sw_component_spatial`，传当前 token 与该 `occurrence_path`。至少抽查 3 个实例，尽量包含同文件重复实例及嵌套子件。 | 返回目标和父路径与特征树相符；原点、变换及近似包围盒字段可读。已解析样本应为 `spatial_status=ok`，异常不得补成零值。 |
| 15 整机空间清单 | 调用 `sw_spatial_inventory`，传当前 token；保存完整原始返回为 `inventory.json`。再单独查询第 14 项三个实例，与批量记录对照。 | 正常完整输入 `status=ok`、`complete=true`、`truncated=false`；`component_count` 等于数组长度，根不计数、子装配计数，重复实例不合并。稳定模型下两种查询的对应字段一致；不能只比较数量。 |
| 坐标与单位 | 在 SolidWorks 中显示并定位被查组件的原点，以根装配坐标检查位置；核对已知基准点/方向。对嵌套子件计算父根矩阵 × 子局部矩阵。 | `_mm = 1000 × _m`，矩阵平移为 m；组合得到子件根矩阵（计算误差阈值 1e-8，仅用于矩阵一致性）。原点位置/方向还需独立人工核对，不能只靠矩阵互验。 |
| 近似包围盒 | 查看 `min_mm`、`max_mm`、`size_mm`，检查整机轴方向、位置与数量级，核对显著的 1000 倍单位错误或重复变换。 | `size=max-min`、非负有限，标为 approximate；不把它与零件局部长宽高或精密测量强行相等。无法核对边界准确性时单独标待验证。 |
| 不完整与缺失数据 | 对至少含 2 个实例的装配，用 `max_components=1` 调用整机工具，保存 `inventory-limited.json`；本机若已有轻化/抑制实例，再记录其字段。 | 限制案例应 `status=partial`、`truncated=true`、`complete=false`，保留节点和 `COMPONENT_LIMIT`；不可读字段为 null 并带错误，不自动解析。无轻化案例则该子项记未测试。 |
| 只读行为与错误 | 对照调用前后 dirty、选择、显隐、位姿；传入不同的 24 字符 token；以 `max_components=0` 调用；再做一次正常查询。 | 状态不因空间工具改变；错误依次为 `DOCUMENT_CHANGED`、`INVALID_ARGUMENTS`，随后服务仍可用。零件类型应 `NOT_ASSEMBLY`，空间验收记阻塞。 |

组件原点不是外形中心或质心；STEP 重复实例可能共用整机原点，不能据“位置为零/相同”判失败。若测试模型缺少可独立核对的嵌套旋转/平移，可另用本机坐标已知的小装配验证，并在记录中标明模型；不伪称已在升降机中覆盖。例如已知父级绕 Z 轴 90°、原点 (1000,2000,0) mm，子件相对父级位移 (200,0,0) mm，则子件整机原点应为 (1000,2200,0) mm。这是验算示例，不是升降机实测数据。

出现 null/partial 时先保存原始错误，区分“真实输入不完整”与“正常已解析组件读取失败”；后者记失败并反馈版本、实例路径、参数及错误码。`isError=false` 或 CLI 退出码 0 不等于数据完整。爆炸/临时展示位姿与基础模型坐标不同，需单独说明；这版不读取运动轨迹。

可直接交给 OpenCode：

```text
按 docs/MCP_ACCEPTANCE.md 中 0.3.0 的清单验证本次新增功能。
先检查当前 SolidWorks 会话、文档类型和 token；若尚未打开，打开仓库里的测试 STEP。
加载 component-spatial，调用 sw_spatial_inventory，保存完整原始返回。
从树里选至少 3 个实例，尽量包括重复实例和子装配中的子件，分别调用 sw_component_spatial。
对照批量/单件结果、单位和父子矩阵，再测试 max_components=1 的部分结果及错误 token。
把实际参数、原始返回和逐项结论保存在 outputs/acceptance-0.3-时间/。
列出需要我在 SolidWorks 窗口核对的位置、方向与近似包围盒；未经我核对的项目记待验证。
不要移动、重建、解析或保存覆盖模型；不要把部分结果、模拟测试或协议连通记成实机全部通过。
```

## 错误处理也要验证

- 给视图工具传入与当前值不同的 24 字符 token，应返回 `DOCUMENT_CHANGED`，窗口不应被切换。
- 用 `max_depth: 0` 调用组件树，应返回 `INVALID_ARGUMENTS`，MCP 保持可用；随后正常会话检查仍能成功。
- 条件具备时检查无活动文档的 `NO_ACTIVE_DOCUMENT`、零件输入的 `NOT_ASSEMBLY`。不要为测试关闭有未保存修改的文档。
- 如发生 `TIMEOUT` / `OUTCOME_UNKNOWN`，先核对窗口、弹窗及实际结果，结束阻塞后重启 MCP；不将超时当作操作已取消，也不盲目重复操作。

## 记录与结论

在 `outputs/` 的新目录保存验收记录、每次实际参数和原始 MCP 返回；视图与选择另附人工窗口核对结果。每项标记“通过 / 失败 / 部分通过 / 阻塞 / 未测试”，写明原因。只有 17 项都满足标准，才能说本版本基础能力实机验收通过。

可直接告诉 OpenCode：

> 按 docs/MCP_ACCEPTANCE.md，在当前 Windows 和 SolidWorks 上逐项验收 17 个 MCP 工具。测试模型已在 examples/three_servo_lift/3X Lift Assembly.STEP。串行调用，记录真实参数、原始返回和需要我核对的窗口现象；重建使用 outputs 下的新工作副本，不保存覆盖原始输入。将结果存入 outputs 的新目录，不把模拟测试、协议连通或部分结果写成实机全部通过。

当前仓库已验证离线逻辑和真实 stdio 协议；用户已反馈旧版 15 个工具的实测状态，本次修复和新增分组仍需目标 SolidWorks 与 OpenCode 客户端验证。零件移动、配合编辑、CAD 文件保存/导出及运动关系识别不在当前 17 个工具范围内；空间结果 JSON 可由客户端或 CLI 保存。

后续每次功能变更都在此追加对应版本的操作、预期返回、人工核对和失败标准。每条记录注明提交 SHA、工具参数、原始返回文件、窗口核对者与结论；没有证据不沿用上版“通过”。
