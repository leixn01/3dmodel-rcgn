# 3DModel-RCGN

工业数模运动关系构建项目。当前包含测试模型和 STEP 文本体检工具；下一步用 OpenCode 在已安装 SolidWorks 的 Windows 电脑上开发组件树读取功能。

## 开始使用

在 PowerShell 中：

```powershell
git clone https://github.com/leixn01/3dmodel-rcgn.git
cd 3dmodel-rcgn
Expand-Archive -LiteralPath .\examples\three_servo_lift\three_servo_lift.zip -DestinationPath .\outputs\three_servo_lift
```

已有仓库则在目录内执行 `git pull --ff-only`；已经解压的模型无需重复解压。

1. 在 SolidWorks 中打开 `outputs/three_servo_lift/temp/3X Lift Assembly.STEP`。
2. 在仓库根目录启动 `opencode`。
3. 告诉 OpenCode：**读取 AGENTS.md，按 docs/DEVELOPMENT_PLAN.md 实现并验证 SolidWorks 连接和组件树导出。**

详细任务提示见 [OpenCode 起步说明](docs/OPENCODE_START.md)。工作结果放在 `outputs/`。

## 可选：运行已有的离线体检

有 Python 3.10+ 时，在仓库根目录运行；不需要安装本项目：

```powershell
python -m cadkin inspect examples/three_servo_lift/three_servo_lift.zip
```

该命令打印 STEP 文本统计，不调用 SolidWorks，也不执行自动拆解。
