# SolidWorks 工具接口

版本：0.3.0。以下 15 个工具已实现并注册；已做离线和 stdio 协议测试。用户反馈已确认打开模型可用，其他工具尚未完成实机验收。以 `cadkin/tools/solidworks.py` 的 JSON Schema 为参数依据。

| 工具 | 参数 | 作用及副作用 |
| --- | --- | --- |
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
| `sw_spatial_inventory` | `expected_document_token`，可选 `max_components`、`max_depth` | 只读装配空间清单，保留缺失与部分数据，不修改模型 |

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

枚举名称从当前 SolidWorks 安装目录的 `swconst.tlb` 解析；只读取，不注册、不运行 makepy、不启动另一实例。无法加载时返回 `DISPLAY_CONSTANTS_UNAVAILABLE`，不猜数值。`DISPLAY_MISMATCH` 表示回读不匹配；`DISPLAY_READ_FAILED` 表示无法可靠读取。总屏蔽开启时，单类显示返回 `DISPLAY_BLOCKED`，不会擅自放开其他类别。

组件显隐使用完整 `occurrence_path`，通过 `IComponent2.Visible` 读写自身标志。返回 `visible`、`hidden_parent_paths` 和 `visible_with_parents`；这些不是像素可见性或遮挡检测。父级隐藏时显示子件返回 `PARENT_HIDDEN`；目标/父级抑制或轻化时返回 `UNRESOLVED_COMPONENT`。层级遍历不完整或实例名称不可靠时返回 `COMPONENT_LOOKUP_INCOMPLETE`，不据部分树猜测目标。重复文件的其他实例不受单实例工具直接修改；隐藏子装配会遮挡其子件。操作无需选择，不清空已有选择。

显示操作可能改变文档内存状态，工具均不保存。调用期间不要改变配置或显示状态；文档 token 不是几何或显示状态版本号。组件显隐不处理多实体零件中的独立实体。

## 空间工具（0.3.0）

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

MCP 返回真实 JSON，不直接写文件；由客户端文件工具保存完整返回，或使用同实现 CLI 的 `--output`。读取期间不要编辑模型或切换文档/配置，长调用受共同超时规则限制。逐项验收见 [0.3.0 清单](MCP_ACCEPTANCE.md#030组件空间信息)。

## 执行范围与失败处理

- 仅通过 `GetActiveObject` 连接已有 SolidWorks；不自动启动软件。当前只支持一个 SolidWorks 进程，多实例返回 `MULTIPLE_SESSIONS`。
- 所有 COM 创建、调用和释放在同一 STA 工作线程；CLI/MCP 共享工具层。运行时没有模拟成功的后端开关。
- 同时收到多个调用时返回 `BUSY`，不把操作排队留到稍后执行。客户端应逐个调用。
- 默认 60 秒超时。超时或取消不能中止已进入 SolidWorks 的 COM 调用；返回未知结果状态并停止接收新操作。先检查窗口/对话框和结果，再重启 MCP，避免重复执行。
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
