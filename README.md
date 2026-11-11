# 3DModel-RCGN

工业数模自动拆解项目。MCP 0.6.0 提供 19 个工具：SolidWorks 启动、文档/组件树、选择/显隐、分页空间读取，可复核的组件分组，以及配合/圆柱轴线证据读取。STEP 测试模型已在 examples 中。

## 在 Windows 上使用

在仓库根目录的 PowerShell 中激活你已有的 Conda 环境（替换下面的环境名；已有仓库先 `git pull --ff-only`）：

```powershell
conda activate 你的环境名
python -m pip install -e ".[solidworks]"
```

仅面向 Windows + 桌面版 SolidWorks，Python 3.10+。无需提前启动 SolidWorks；STEP 已在 examples 下，无需解压。保持该 Conda 环境激活，在同一终端运行：

```powershell
opencode mcp list
opencode
```

项目 `opencode.json` 使用当前环境的 `python` 启动 MCP，不绑定机器路径。升级后退出并重新启动 OpenCode，让 MCP 加载新工具。告诉 Agent：

> 启动或复用 SolidWorks，打开仓库测试 STEP；按 docs/MCP_ACCEPTANCE.md 的 0.6.0 清单核对 Conda 解释器；读取一个组件的配合和圆柱轴线证据，结合分组候选列出待确认关系。保存原始结果，列出待确认实例，不自动确认刚体或运动关系。

## 导出与分组

打开模型后，在仓库根目录执行（文件名需未被使用）：

```powershell
python -m cadkin spatial-export --page-size 5 --output outputs/spatial.json
python -m cadkin group outputs/spatial.json --output outputs/groups.json
```

第一条自动读完所有页；若包围盒较慢，可另取文件名加 `--without-boxes`。第二条离线生成固定基体、移动平台、传动/导向相关件和待确认四类候选，保留依据；子装配容器不重复分组，未知名称不强行识别。复核方法见验收清单。

新增 `sw_component_constraints` 查询固定标志/配合，`sw_component_cylinders` 查询指定零件的圆柱面轴线/半径。它们只读；嵌套固定状态、装配级几何差异和运动关系仍需核对。

Skill 在 `.opencode/skills/`，工具在 `cadkin/tools/`，COM 在 `cadkin/adapters/`。当前不含零件移动、配合编辑或自动运动关系识别。

[下一步](docs/DEVELOPMENT_PLAN.md) · [实机验收清单](docs/MCP_ACCEPTANCE.md) · [使用与排错](docs/OPENCODE_START.md) · [工具接口](docs/TOOL_CONTRACTS.md) · [分层](docs/ARCHITECTURE.md) · [开源来源](THIRD_PARTY_NOTICES.md)
