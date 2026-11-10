# OpenCode + SolidWorks 使用与排错

## 首次安装

在已安装 SolidWorks 的 Windows 电脑，取得仓库后进入根目录。使用 Python 3.10+：

```powershell
git clone https://github.com/leixn01/3dmodel-rcgn.git
cd 3dmodel-rcgn
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[solidworks]"
```

已有仓库先 `git pull --ff-only`；STEP 已随仓库提供，无需解压。依赖为官方 MCP SDK 1.29.0、Windows 上的 pywin32 及 SDK 依赖；离线体检无需安装这些依赖。不要把第三方上游仓库也注册成同名 MCP，以免调用到另一套工具。

## 连接与实际操作

1. 启动一个 SolidWorks 实例，完成启动/许可弹窗。
2. 在仓库根目录运行 `opencode mcp list`，确认 `solidworks` 已连接，再运行 `opencode`。MCP 已连接只表示协议服务可用；还需调用会话工具验证 SolidWorks。
3. 告诉 Agent：

```text
加载 solidworks-connect，检查 SolidWorks 会话。
加载 solidworks-document，打开 examples/three_servo_lift/3X Lift Assembly.STEP。
报告实际文档类型；如果是装配，加载 assembly-inventory，保存组件树到 outputs/solidworks_inventory.json。
然后加载 solidworks-view，将模型切到等轴测并缩放适合窗口。
```

4. 检查 SolidWorks 窗口及 JSON。需要突出某个实例时，加载 `component-selection`，提供组件树中的完整 `occurrence_path`；Agent 应先读取当前文档 token，再选择和核对。
5. 需要重建时明确要求“加载 solidworks-document，重建当前文档”；该操作不保存。工具目前不负责移动零件、添加配合或自动推断运动关系。

用户也可以先手动打开 STEP，再从组件读取开始。若导入为多实体零件，组件树工具会返回 `NOT_ASSEMBLY`，不生成空装配结果。

## 配置

根目录 `opencode.json` 使用 V1 格式，V2 官方兼容说明支持该格式；无需为了加载 skill 迁移配置。服务启动命令为 `.venv/Scripts/python.exe -m cadkin.mcp_server`，必须在仓库根目录启动 OpenCode。

若本机使用 V2 原生配置，可将同一个服务对象置于 `mcp.servers.solidworks`，使用 `disabled: false`，并把超时写为 `timeout: {"catalog": 70000, "execution": 70000}`。不要同时维护两份冲突的同名服务定义。全局个人凭据不应提交到项目。

需要从其他目录启动或有特殊路径时，将 command 第一项改为本机虚拟环境 Python 的绝对路径，并在命令参数中添加 `--root` 与仓库绝对路径。默认按项目工作目录解析相对模型路径。

Skill 位于 `.opencode/skills/<名称>/SKILL.md`，按默认规则发现；不需要额外配置 skills 路径或把所有正文塞进 instructions。

## 排错

| 现象 | 处理 |
| --- | --- |
| MCP 无法启动 | 确认 `.venv/Scripts/python.exe` 存在，并重新执行安装命令；从仓库根目录启动 |
| `UNSUPPORTED_PLATFORM` | 使用 SolidWorks 所在电脑的 Windows Python；Linux/WSL Python 不能直接访问 COM |
| `connected: false` / `NOT_RUNNING` | 手动启动 SolidWorks；服务不会自动创建空实例 |
| `CONNECT_FAILED` | 确认同一 Windows 用户、相同权限级别，结束启动弹窗；不要把云端服务当作本机连接 |
| `MULTIPLE_SESSIONS` | 当前版本需要保留一个目标 SolidWorks 进程；不要自动关闭用户工程 |
| `NO_ACTIVE_DOCUMENT` | 用打开工具或手动打开模型 |
| `DOCUMENT_CHANGED` | 重新读取活动文档和 token，确认目标后再操作 |
| `TIMEOUT` / `OUTCOME_UNKNOWN` | 检查 SolidWorks 弹窗和操作结果，结束阻塞后重启 MCP；不可直接重试可能已执行的操作 |
| 组件树为 `partial` | 检查 errors，记录未解析节点或上限；如需解析组件，由用户明确操作后重读 |

诊断命令：`.\.venv\Scripts\python.exe -m cadkin sw sw_session_status`。结果输出到终端，不会开启 MCP 协议会话。运行产物留在 `outputs/`。

本项目尚未在目标 SolidWorks 版本实测。请按 [8 个工具验收清单](MCP_ACCEPTANCE.md) 记录首次联调结果；后续任务见 [开发计划](DEVELOPMENT_PLAN.md)。

官方说明：[Skills](https://opencode.ai/docs/skills/)、[MCP](https://opencode.ai/docs/mcp-servers/)、[V1/V2 兼容](https://opencode.ai/docs/migrate-v1/)。
