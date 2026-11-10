# SolidWorks 工具接口

版本：0.1.0。以下 8 个工具已实现并注册；已做离线和 stdio 协议测试，尚无本项目的 SolidWorks 实机验收。以 `cadkin/tools/solidworks.py` 的 JSON Schema 为参数依据。

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

`view` 支持 front/back/left/right/top/bottom/isometric/trimetric/dimetric。接口用枚举值访问视图，不依赖中英文界面的视图名称。

先读取文档或组件树，使用返回的 `document_token` 操作。该值关联进程、文档路径/标题及活动配置；目标不匹配返回 `DOCUMENT_CHANGED`，不会操作新目标。它不是不可变几何版本号；模型重建或编辑后重新读取组件清单。工具执行期间不要在界面切换文档、配置或修改模型，COM 读取不是事务快照。

## 结果

所有工具返回 `schema_version`、`status`（`ok` / `partial` / `error`）、`data` 和 `errors`。MCP 致命工具错误同时设置 `isError: true`；部分结果保留数据并标记 `partial`，不得当作完整验收。

组件节点包含 `occurrence_path`（完整 Name2）、父路径、名称、文件路径、引用配置、原始抑制状态枚举、是否抑制及读取状态。重复文件的不同实例分别保留，根装配单独存于 `document`，不计入 `component_count`。`complete: false` 表示遍历不完整；数量只代表实际读取的节点。

抑制/轻化/内部 ID 错误、读取异常、遍历深度或数量上限都会产生明确记录。缺失或重复实例名称使用 `@unreadable/...` 标记，不能用其选择组件。相同名称产生歧义时拒绝选择。

`sw_set_view` 的成功表示 API 调用完成；它不会把返回 void 的 API 当作视觉核对证据。`sw_rebuild` 检查重建返回值，不声称已全面检查配合或几何健康度。

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
- [GetRootComponent3](https://help.solidworks.com/2019/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IConfiguration~GetRootComponent3.html)
- [LoadFile4](https://help.solidworks.com/2015/English/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.ISldWorks~LoadFile4.html)
- [IComponent2.Select4（三参数）](https://help.solidworks.com/2020/english/api/sldworksapi/solidworks.interop.sldworks~solidworks.interop.sldworks.icomponent2~select4.html)
- [重建激活枚举](https://help.solidworks.com/2024/English/api/swconst/SOLIDWORKS.Interop.swconst~SOLIDWORKS.Interop.swconst.swRebuildOnActivation_e.html)
