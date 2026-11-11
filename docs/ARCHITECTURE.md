# Skill、工具、MCP 与 SolidWorks

| 层 | 实现位置 | 职责 |
| --- | --- | --- |
| Skill | `.opencode/skills/<名称>/SKILL.md` | 任务流程、工具选择与结果判断 |
| 工具 | `cadkin/tools/solidworks.py` | 固定工具目录、参数 Schema、统一错误 |
| 分页汇总/分组 | `cadkin/tools/spatial.py`、`grouping.py` | 逐页采集和离线角色候选；分组不创建 COM 对象 |
| MCP | `cadkin/mcp_server.py` | 官方 SDK 的 stdio 协议、工具注册与结构化返回 |
| CLI | `cadkin/__main__.py` | 调用同一工具层、将 JSON 保存到新文件 |
| COM 适配 | `cadkin/adapters/solidworks.py`、`display.py`、`spatial.py`、`session.py`、`constraints.py`、`cylinders.py` | 会话/文档/组件 API；显示、空间读取和显式启动独立模块，通过同一 STA 执行 |
| 空间计算 | `cadkin/geometry.py` | 无 COM 依赖的矩阵、单位与近似包围盒转换 |
| STA 调度 | `cadkin/adapters/sta.py` | 单线程串行调用、超时及取消后的状态处理 |
| 开源兼容片段 | `cadkin/_vendor/sw_mcp.py` | 从固定 SW_MCP 版本提取并修改的 COM 成员访问逻辑 |

Agent 按 skill 选择 MCP 工具，MCP 调用工具层，工具在 STA 线程内调用 COM 适配器。CLI 也走同一工具层。输入体检 `cadkin/tools/intake.py` 保持独立，无 Windows/MCP 依赖。

当前采用 Python + pywin32 + 官方 MCP Python SDK 1.29.0。本地 stdio 服务由 OpenCode 启动，无需开放网络端口或注册 SolidWorks 插件。MCP/COM 进程必须运行在安装 SolidWorks 的 Windows 电脑上；使用已激活 Conda 环境中的 Python；CI 在 Windows 上创建 Conda 的 Python 3.10/3.12 环境。

## 隔离

- Skill 不包含执行代码、COM 对象、MCP 注册或客户端配置；默认按需发现，不互相强制加载完整流程。
- 工具不读取 SKILL.md，不依赖 OpenCode，也不调用 LLM 补造 API 结果。
- MCP 只处理协议；组件遍历和具体操作在适配层，不在协议入口复制。
- COM 对象不离开 STA 线程；输出只含 JSON 数据。失败时传递普通错误数据，不将持有 COM 引用的原异常 traceback 交到外部线程。
- Skill 是流程说明，不是权限沙箱。工具目录限制可调用动作；当前没有任意脚本、保存覆盖、关闭文档、修改配合或移动组件入口。

多个 skill 可复用原子工具，一个 MCP 服务提供多个工具，无需为每个 skill 启动一个服务器。

## 功能拆分

| Skill | 职责 |
| --- | --- |
| `cad-intake` | 离线 STEP/ZIP 体检 |
| `solidworks-start` | 独立启动/复用会话、可见性及就绪检查，不打开模型 |
| `solidworks-connect` | 会话与活动文档检查、连接诊断 |
| `assembly-inventory` | 装配组件树、部分结果核对与清单导出 |
| `component-spatial` | 单实例/分页空间信息、单位与近似边界说明、完整 JSON 导出 |
| `component-grouping` | 叶实例角色候选、范围选择、人工复核与修正，不修改 CAD |
| `component-constraints` | 指定组件固定标志、原始配合/引用参数及上下文限制 |
| `component-cylinders` | 匹配配置零件定义的圆柱面轴线/半径候选 |
| `solidworks-document` | 明确请求的打开/导入、重建操作 |
| `solidworks-view` | 标准视图和缩放 |
| `solidworks-display` | 基准面等类别显示过滤与总开关 |
| `component-visibility` | 单个装配实例显隐与隐藏父级核对 |
| `component-selection` | 按完整实例路径选择或清空选择 |

软件启动、文档操作、空间读取与显示操作相互独立；后续详细几何、配合提取、运动关系推断继续独立增加。

## 验证边界

代码、CLI 和 MCP 已实现；单元测试使用显式测试替身验证逻辑，stdio 测试实际进行握手及工具调用。它们不证明某个 SolidWorks 版本的 COM 兼容性。用户最新 SolidWorks 2025 旧版 15 工具反馈为 11 项 API 通过、2 项失败、2 项部分通过；0.5.0 修复/分组及 0.6.0 新证据读取仍需按验收文档在用户电脑复测。

只保留一个 SolidWorks 进程。调用串行，不排队叠加动作。超时不能撤回已经进入 SolidWorks 的操作，客户端要核对现场并重启 MCP。当前版本使用严格的 late binding；遇到无法标记为方法的成员会返回错误，不尝试无参数误调用。

## 来源

[代码复用与许可](../THIRD_PARTY_NOTICES.md)记录精确来源、提交、复用范围及修改。

官方说明：[SolidWorks COM API](https://help.solidworks.com/2026/english/SolidWorks/sldworks/c_solidworks_api.htm?id=3.26)、[MCP SDK 1.x](https://py.sdk.modelcontextprotocol.io/v1/)、[OpenCode MCP](https://opencode.ai/docs/mcp-servers/)、[Skills](https://opencode.ai/docs/skills/)。
