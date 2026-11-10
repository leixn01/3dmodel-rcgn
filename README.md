# 3DModel-RCGN

工业数模自动拆解项目。提供测试 STEP、离线体检和 15 个 SolidWorks MCP 工具：文档/组件树、视图、选择、重建、显隐，以及组件位置、变换和近似包围盒。用户已确认打开模型可用；其余操作待实机验证。

## 在 Windows 上使用

在仓库根目录的 PowerShell 中执行（已有仓库先 `git pull --ff-only`）：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[solidworks]"
```

需要 Python 3.10+；STEP 已直接放在 examples 下，无需解压。启动一个 SolidWorks 实例，再在仓库根目录运行：

```powershell
opencode mcp list
opencode
```

项目 `opencode.json` 已配置本地 MCP。升级后退出并重新启动 OpenCode，让 MCP 加载新工具。告诉 Agent：

> 检查 SolidWorks 连接；打开 examples/three_servo_lift/3X Lift Assembly.STEP。若导入为装配，读取组件空间清单，将原始 JSON 保存到 outputs 下的新文件，并说明不完整项。

## 直接检查

```powershell
.\.venv\Scripts\python.exe -m cadkin sw sw_session_status
.\.venv\Scripts\python.exe -m cadkin sw sw_component_tree --output outputs/solidworks_inventory.json
python -m cadkin inspect "examples/three_servo_lift/3X Lift Assembly.STEP"
```

Skill 在 `.opencode/skills/`，工具在 `cadkin/tools/`，COM 在 `cadkin/adapters/`。当前不含零件移动、配合编辑或自动运动关系识别。

[下一步](docs/DEVELOPMENT_PLAN.md) · [实机验收清单](docs/MCP_ACCEPTANCE.md) · [使用与排错](docs/OPENCODE_START.md) · [工具接口](docs/TOOL_CONTRACTS.md) · [分层](docs/ARCHITECTURE.md) · [开源来源](THIRD_PARTY_NOTICES.md)
