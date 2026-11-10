# 3DModel-RCGN

工业数模自动拆解项目。已有测试模型、离线 STEP 体检工具和三个 OpenCode skill；SolidWorks MCP 工具待开发、实测。

## 开始使用

在 Windows PowerShell 中：

```powershell
git clone https://github.com/leixn01/3dmodel-rcgn.git
cd 3dmodel-rcgn
Expand-Archive -LiteralPath .\examples\three_servo_lift\three_servo_lift.zip -DestinationPath .\outputs\three_servo_lift
opencode
```

已有仓库执行 `git pull --ff-only`；已解压的模型无需重复解压。

- 离线体检：告诉 OpenCode **加载 cad-intake，检查仓库内测试模型**。需要 Python 3.10+。
- 开始 SolidWorks 开发：先手动打开 `outputs/three_servo_lift/temp/3X Lift Assembly.STEP`，再告诉 OpenCode **加载 solidworks-connect，按 docs/DEVELOPMENT_PLAN.md 完成第一步只读连接与 MCP 接入**。

Skill 放在 `.opencode/skills/<名称>/SKILL.md`，按默认规则发现、按需加载；执行代码放在 `cadkin/tools/`。

## 直接运行现有工具

```powershell
python -m cadkin inspect examples/three_servo_lift/three_servo_lift.zip
```

该命令只做 STEP 文本体检。工作结果放 `outputs/`。

[OpenCode 用法](docs/OPENCODE_START.md) · [分层与 SolidWorks 联动](docs/ARCHITECTURE.md) · [开发计划](docs/DEVELOPMENT_PLAN.md)
