# 3DModel-RCGN

工业数模自动拆解项目。MCP 0.5.0 提供 17 个工具：SolidWorks 启动、文档/组件树、选择/显隐、分页空间读取，以及可复核的组件分组。STEP 测试模型已在 examples 中。

## 在 Windows 上使用

在仓库根目录的 PowerShell 中执行（已有仓库先 `git pull --ff-only`）：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[solidworks]"
```

仅面向 Windows + 桌面版 SolidWorks，Python 3.10+。无需提前启动 SolidWorks；STEP 已在 examples 下，无需解压。在仓库根目录运行：

```powershell
opencode mcp list
opencode
```

项目 `opencode.json` 已配置本地 MCP。升级后退出并重新启动 OpenCode，让 MCP 加载新工具。告诉 Agent：

> 启动或复用 SolidWorks，打开仓库测试 STEP；按 docs/MCP_ACCEPTANCE.md 的 0.5.0 清单复测显示和组件隐藏，分页导出空间清单，再生成组件分组候选。保存原始结果，列出待确认实例，不自动确认刚体或运动关系。

## 导出与分组

打开模型后，在仓库根目录执行（文件名需未被使用）：

```powershell
.\.venv\Scripts\python.exe -m cadkin spatial-export --page-size 5 --output outputs/spatial.json
.\.venv\Scripts\python.exe -m cadkin group outputs/spatial.json --output outputs/groups.json
```

第一条自动读完所有页；若包围盒较慢，可另取文件名加 `--without-boxes`。第二条离线生成固定基体、移动平台、传动/导向相关件和待确认四类候选，保留依据；子装配容器不重复分组，未知名称不强行识别。复核方法见验收清单。

Skill 在 `.opencode/skills/`，工具在 `cadkin/tools/`，COM 在 `cadkin/adapters/`。当前不含零件移动、配合编辑或自动运动关系识别。

[下一步](docs/DEVELOPMENT_PLAN.md) · [实机验收清单](docs/MCP_ACCEPTANCE.md) · [使用与排错](docs/OPENCODE_START.md) · [工具接口](docs/TOOL_CONTRACTS.md) · [分层](docs/ARCHITECTURE.md) · [开源来源](THIRD_PARTY_NOTICES.md)
