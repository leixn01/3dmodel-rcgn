# Skill、工具与 SolidWorks 的边界

## 当前目录

| 位置 | 职责 | 当前状态 |
| --- | --- | --- |
| `.opencode/skills/<name>/SKILL.md` | 可按需加载的工作流程、判断规则与验收步骤 | 三个独立 skill 已提供 |
| `AGENTS.md` | 全项目约定及功能导航 | 已提供 |
| `cadkin/tools/intake.py` | STEP/ZIP 文本检查与校验下载 | 已实现 |
| `cadkin/__main__.py` | 命令行参数与结果输出 | 已实现，原命令保持可用 |
| `docs/TOOL_CONTRACTS.md` | SolidWorks 工具接口与错误约定 | 设计约定，未实现 |
| `examples/`、`configs/`、`tests/` | 测试模型、来源配置、工具测试 | 已提供 |

后续实现时再创建 `cadkin/adapters/solidworks.py`（COM 访问）、`cadkin/tools/solidworks.py`（工具功能）和 `cadkin/mcp_server.py`（MCP 注册与协议处理）。本次不放假实现，也不配置不存在的 MCP 服务。

## 联动方式

建议在用户的 Windows 电脑运行 OpenCode 和本地 stdio MCP 服务，由服务通过 SolidWorks COM API 访问已经打开的模型。SolidWorks 官方提供 COM API 和独立进程应用方式，不必先开发 SolidWorks 插件。

调用顺序为：OpenCode Agent 根据 skill 选择工具，MCP 接收结构化参数，工具调用 COM 适配器，适配器访问 SolidWorks。结果沿相反方向返回。skill 不负责启动服务，不持有 COM 对象，也不直接实现 API 调用。

MCP 不是 SolidWorks 能力本身。第一步先通过 CLI 验证同一套 Python 工具的 COM 读取，再加一层薄 MCP 接口供 Agent 稳定调用。这样既能独立排查工具问题，也能接入其他支持 MCP 的 Agent。CLI 与 MCP 不各写一份业务逻辑。

当前方案选择 Python 原型：仓库已有 Python 工具，后续仅按需要添加 Windows COM 依赖和 MCP SDK。若实际 API 的类型绑定或事件处理需要 C#，只替换适配层，保留上层工具契约与 skill。

## 隔离规则

- **Skill 层**只描述何时用、按什么顺序用、如何判断结果；本项目的 skill 目录不存可执行程序、COM 代码或 MCP 配置。
- **工具层**实现输入校验、具体操作与结构化结果；不读取 SKILL.md，不依赖 OpenCode，不调用 LLM 做事实填充。
- **适配层**封装 SolidWorks COM 对象及调用；COM 对象不跨协议传输，转成普通 JSON 数据后再返回。
- **MCP 层**注册工具、校验协议输入和传递错误；不承载装配遍历算法或机械推断规则。
- **CLI 层**负责命令行参数和本地文件输出；复用工具层。离线体检不依赖 Windows、SolidWorks 或 MCP。

这里的隔离是代码依赖与职责隔离；SKILL.md 不是执行权限沙箱。操作范围必须由工具实现和 Agent 客户端权限配置共同控制，不能只靠提示词约束。

一个 MCP 服务可以提供多个原子工具，多个 skill 可以复用同一个工具。无需每个 skill 启动一个服务，也不在 `.opencode/tools/` 复制一套同功能实现。

## 按功能拆分 skill

| Skill | 输入 | 交付 | 边界 |
| --- | --- | --- | --- |
| `cad-intake` | STEP/ZIP 文件 | 文本体检与来源核对 | 当前可运行；不连接 SolidWorks |
| `solidworks-connect` | 本机已有会话 | 会话及活动文档信息 | 流程已定义，工具待实现；不遍历装配 |
| `assembly-inventory` | 活动装配 | 组件实例树 | 流程已定义，工具待实现；不推断运动 |

以后确有功能时再新增几何提取、配合提取、运动关系推断、结果验证等独立 skill。通过明确的数据契约交接，不把全部功能合进一个总 skill，也不预先创建大量空目录。

## 运行边界

- MCP 服务运行在安装 SolidWorks 的 Windows 主机、当前用户桌面会话中。部署到云端的 Agent 不能仅凭仓库访问该电脑的 COM。
- 起步用本地 stdio，无需开放网络端口。若 OpenCode 在 WSL/容器中，应单独验证如何启动 Windows 进程，不假设 Linux Python 可以直接访问 Windows COM。
- 第一版只读。打开文件、组件移动、修改配合和保存模型作为后续独立写入工具设计，明确目标文档与副作用；不暴露任意 Python、VBA 或任意 API 名称执行入口。
- COM 调用须串行并正确管理线程初始化/对象生命周期；不能把绑定线程的 COM 对象直接交给任意 MCP 工作线程。具体实现须在目标电脑验证。

## 官方依据

核查日期：2026-11-10。架构分层及 Python 选型是本项目方案。

- [OpenCode skill 默认发现规则](https://opencode.ai/docs/skills/)
- [OpenCode 本地 MCP](https://opencode.ai/docs/mcp-servers/)
- [OpenCode V1 → V2 配置说明](https://opencode.ai/docs/migrate-v1/)
- [SolidWorks COM API 概览](https://help.solidworks.com/2026/english/SolidWorks/sldworks/c_solidworks_api.htm?id=3.26)
- [独立应用与插件](https://help.solidworks.com/2025/english/api/sldworksapiprogguide/GettingStarted/SolidWorks_API_Standalone_and_Add-in_Applications_Overview.htm?id=1.2.2.0)
