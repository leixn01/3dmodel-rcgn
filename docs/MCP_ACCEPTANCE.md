# 当前版本 MCP 实机验收

目标：在安装 SolidWorks 的 Windows 电脑，通过 OpenCode 实际调用全部 15 个工具，核对返回值与 SolidWorks 窗口。离线测试及模拟后端不能作为实机通过证据。

## 准备与连接

1. 在仓库根目录执行 `git pull --ff-only`，按 README 安装或更新 `.[solidworks]`，启动一个 SolidWorks 实例并完成启动弹窗。
2. 运行 `opencode mcp list`，确认 `solidworks` 已连接；进入 OpenCode，确认 MCP 工具目录包含下面 15 个工具。客户端可能给工具名添加服务器前缀。
3. 记录提交 SHA（`git rev-parse HEAD`）、Windows/Python/OpenCode/SolidWorks 版本。MCP 已连接仅代表协议可用，必须继续检查 `sw_session_status`。

用户反馈（2026-11-10）：已确认打开模型可用；其余原有 7 个工具未验证。反馈未附具体 SolidWorks 版本与原始调用记录。0.2.0 新增 5 个、0.3.0 新增 2 个工具也待实机验证，不能据此标为全部通过。

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

在 `outputs/` 的新目录保存验收记录、每次实际参数和原始 MCP 返回；视图与选择另附人工窗口核对结果。每项标记“通过 / 失败 / 部分通过 / 阻塞 / 未测试”，写明原因。只有 15 项都满足标准，才能说本版本基础能力实机验收通过。

可直接告诉 OpenCode：

> 按 docs/MCP_ACCEPTANCE.md，在当前 Windows 和 SolidWorks 上逐项验收 15 个 MCP 工具。测试模型已在 examples/three_servo_lift/3X Lift Assembly.STEP。串行调用，记录真实参数、原始返回和需要我核对的窗口现象；重建使用 outputs 下的新工作副本，不保存覆盖原始输入。将结果存入 outputs 的新目录，不把模拟测试、协议连通或部分结果写成实机全部通过。

当前仓库已验证离线逻辑和真实 stdio 协议；用户已反馈打开模型可用，剩余功能的目标 SolidWorks 与 OpenCode 客户端实测仍待执行。零件移动、配合编辑、CAD 文件保存/导出及运动关系识别不在当前 15 个工具范围内；空间结果 JSON 可由客户端或 CLI 保存。

后续每次功能变更都在此追加对应版本的操作、预期返回、人工核对和失败标准。每条记录注明提交 SHA、工具参数、原始返回文件、窗口核对者与结论；没有证据不沿用上版“通过”。
