# 3DModel-RCGN

工业数模自动拆解项目。MCP 0.8.0 提供 22 个工具：SolidWorks 启动、文档/组件树、选择/显隐、分页空间读取，可复核的组件分组，配合/圆柱轴线证据读取，同轴/平行候选与配合状态关联。STEP 测试模型已在 examples 中。

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

> 启动或复用 SolidWorks，打开仓库测试 STEP；按 docs/MCP_ACCEPTANCE.md 的 0.8.0 清单，读取根装配配合状态，并与已有几何候选离线关联。只加载当前任务对应 skill，按需读取参考文件；保存原始证据，列出待核对实例，不自动确认运动副。

## 导出与分组

打开模型后，在仓库根目录执行（文件名需未被使用）：

```powershell
python -m cadkin spatial-export --page-size 5 --output outputs/spatial.json
python -m cadkin group outputs/spatial.json --output outputs/groups.json
```

第一条自动读完所有页；若包围盒较慢，可另取文件名加 `--without-boxes`。第二条离线生成固定基体、移动平台、传动/导向相关件和待确认四类候选，保留依据；子装配容器不重复分组，未知名称不强行识别。复核方法见验收清单。

`sw_component_constraints` 查询固定标志/配合，`sw_component_cylinders` 查询指定零件的圆柱面轴线/半径。它们只读；嵌套固定状态、装配级几何差异和运动关系仍需核对。

新增离线 `cad_component_relations`：输入空间清单和至少两个圆柱证据文件，输出候选夹角、轴偏移、来源与待确认项。使用步骤见 [0.7.0 验收](docs/MCP_ACCEPTANCE.md#070组件关系候选)。

新增 `sw_mate_inventory` 读取根配合状态，`cad_review_connections` 关联几何候选与配合证据。[0.8.0 验收](docs/MCP_ACCEPTANCE.md#080配合状态与连接复核)包含两项的核对步骤。

Skill 在 `.opencode/skills/`，入口简短、references 按需读取；工具在 `cadkin/tools/`，COM 在 `cadkin/adapters/`。当前不含零件移动、配合编辑或自动运动关系识别。

[下一步](docs/DEVELOPMENT_PLAN.md) · [实机验收清单](docs/MCP_ACCEPTANCE.md) · [使用与排错](docs/OPENCODE_START.md) · [工具接口](docs/TOOL_CONTRACTS.md) · [分层](docs/ARCHITECTURE.md) · [开源来源](THIRD_PARTY_NOTICES.md)
