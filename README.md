# 3DModel-RCGN

工业数模自动拆解项目。已提供测试模型、STEP 体检和 SolidWorks 本地 MCP：读取文档/组件树、打开模型、切换视图、选择组件、重建。已通过离线与 MCP 协议测试，SolidWorks 实机待验收。

## 在 Windows 上使用

在仓库根目录的 PowerShell 中执行（已有仓库先 `git pull --ff-only`）：

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[solidworks]"
Expand-Archive -LiteralPath .\examples\three_servo_lift\three_servo_lift.zip -DestinationPath .\outputs\three_servo_lift
```

需要 Python 3.10+；已解压无需重复解压。启动一个 SolidWorks 实例，再在仓库根目录运行：

```powershell
opencode mcp list
opencode
```

项目 `opencode.json` 已配置本地 MCP。告诉 Agent：

> 加载 solidworks-connect，检查连接；然后加载 solidworks-document，打开 outputs/three_servo_lift/temp/3X Lift Assembly.STEP，报告实际文档类型。若为装配，加载 assembly-inventory 导出组件树。

## 直接检查

```powershell
.\.venv\Scripts\python.exe -m cadkin sw sw_session_status
.\.venv\Scripts\python.exe -m cadkin sw sw_component_tree --output outputs/solidworks_inventory.json
python -m cadkin inspect examples/three_servo_lift/three_servo_lift.zip
```

Skill 在 `.opencode/skills/`，工具在 `cadkin/tools/`，COM 在 `cadkin/adapters/`。当前不含零件移动、配合编辑或自动运动关系识别。

[使用与排错](docs/OPENCODE_START.md) · [工具接口](docs/TOOL_CONTRACTS.md) · [分层](docs/ARCHITECTURE.md) · [开源来源](THIRD_PARTY_NOTICES.md)
