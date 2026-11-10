# 工具接口约定

以下 SolidWorks 接口是下一阶段的开发目标，尚未注册为可调用工具。实际能力以代码、Agent 工具列表和目标电脑测试为准。

## 已有离线工具

`cadkin/tools/intake.py` 提供 `inspect_path`、`inspect_step`、`fetch_asset`。CLI 仍为 `python -m cadkin inspect <path>` / `python -m cadkin fetch ...`。现有结果格式不变；指定模型已内置，日常不需要下载命令。

## 首批 SolidWorks 工具

| 工具名（服务内部） | 参数 | 成功结果的核心内容 |
| --- | --- | --- |
| `sw_session_status` | 无 | 是否找到现有会话、SolidWorks 版本；未运行是明确状态 |
| `sw_active_document` | 无 | 标题、路径、文档类型、活动配置；无文档与 API 错误分别表示 |
| `sw_component_tree` | 无 | 本次读取的文档/配置、组件实例列表、统计口径、完整性与读取错误 |

第一版仅处理已有会话的活动文档；多实例不能唯一确定目标时返回错误，不任意选择。每个结果都携带实际读取的文档上下文，Agent 应与任务目标核对。遍历期间使用同一文档/配置快照，检测到切换或失效时报告失败或部分结果，不拼接不同模型的数据。

工具只返回 JSON 可序列化值，不把原始 COM 对象或堆栈当作业务数据。建议统一包含 `schema_version`、`status`（`ok` / `partial` / `error`）、`data`、`errors`；致命工具错误在 MCP 层也应标记为错误，不能返回普通成功文本。

`sw_component_tree` 每个实例至少包含：

- `occurrence_path`：本次文档和配置中的完整实例路径，不宣称跨编辑永久稳定。
- `parent_occurrence_path`：父实例；根装配单独记录，不将其重复算作子组件。
- `name`、`file_path`、`referenced_configuration`：实例名称、可用文件路径、引用配置；未知使用 `null` 并记录原因。
- `suppression_state`、`read_status`：抑制/轻化/解析状态及读取状态；不按名称或文件路径合并重复实例。

明确报告实例统计是否包含子装配节点、抑制项和未解析项。某分支读取失败时保留节点及错误，返回 `partial`；顶层读取失败时返回 `error`。不得用空列表、零计数或猜测值掩盖错误。只统计本次确实读到的节点，不声称覆盖不可访问的子树。

首批工具不接收输出路径、不写模型文件；JSON 落盘由 CLI 或 Agent 文件工具负责，写入 `outputs/` 并避免覆盖。后续需要大型结果分页或专用导出工具时再扩展契约。

## API 实现注意事项

1. 连接已经运行的 SolidWorks，读取 `ActiveDoc` 及实际文档类型。不能以“新建了一个空实例”作为连接已有模型成功的证据。
2. 使用当前活动配置的 `GetRootComponent3(false)` 获取装配遍历入口，再用 `IComponent2.GetChildren` 递归。避免为读取而自动加载额外配置组件；未解析情况如实返回。
3. 配置根组件主要用作遍历入口，不能假设它支持普通组件的全部属性。根装配信息从文档/配置读取。
4. 以目标 SolidWorks 版本的 API 为准验证 COM 绑定、属性/方法返回形式及抑制状态枚举。使用进程外可调用接口；不要直接照抄仅供进程内使用的 `IGetChildren` 示例。
5. 单元测试覆盖无会话、无文档、零件输入、重复实例、轻化/抑制、部分失败；另外必须有 Windows 实测。mock 通过不能代替 COM 验收。

参考：[GetRootComponent3](https://help.solidworks.com/2019/english/api/sldworksapi/SOLIDWORKS.Interop.sldworks~SOLIDWORKS.Interop.sldworks.IConfiguration~GetRootComponent3.html)、[进程内/外遍历差异](https://help.solidworks.com/2023/english/api/sldworksapi/traverse_assembly_example_cplusplus_com.htm)。这两页用于确认接口语义，开发时还需按本机版本核对。
