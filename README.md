# 3DModel-RCGN｜自动数模运动关系构建

从一个小任务开始：**在已经安装 SolidWorks 的 Windows 电脑上，用 OpenCode 读取测试装配的基本信息和组件树。**

目前具备测试模型、STEP 文本体检工具和开发说明。SolidWorks 连接与组件树导出是下一步在目标电脑上实现和实测的功能，尚未宣称跑通。

## 1. 取得仓库和测试模型

在目标电脑的 PowerShell 中：

```powershell
git clone https://github.com/leixn01/3dmodel-rcgn.git
cd 3dmodel-rcgn
Expand-Archive -LiteralPath .\examples\three_servo_lift\three_servo_lift.zip -DestinationPath .\outputs\three_servo_lift
```

如果已经克隆，在仓库目录执行 `git pull --ff-only` 即可更新。解压目录已存在时直接使用其中的文件，无需重复解压或覆盖自己的工作。

测试模型已经随仓库提交，约 1.1 MB，普通 Git 克隆即可取得，无需 Git LFS 或额外下载。

| 内容 | 位置 |
| --- | --- |
| 测试模型原包 | [examples/three_servo_lift/three_servo_lift.zip](examples/three_servo_lift/three_servo_lift.zip) |
| 解压后的数模 | `outputs/three_servo_lift/temp/3X Lift Assembly.STEP` |
| 解压后的参考图 | `outputs/three_servo_lift/temp/Bosch SSS 08.JPG` |
| 来源与校验信息 | [样例说明](examples/three_servo_lift/README.md) |

在 SolidWorks 中手动打开上述 STEP，检查模型是否完整，以及导入结果是装配文档还是多实体零件。需要保存为 SolidWorks 工作副本时，保存到 `outputs/` 下。

## 2. 用 OpenCode 开始第一步

在同一台 Windows 电脑的仓库根目录启动 OpenCode。仓库已提供 [AGENTS.md](AGENTS.md)，并在 [OpenCode 起步说明](docs/OPENCODE_START.md) 中给出可直接粘贴的任务描述。

本轮目标只有：**连接已打开的 SolidWorks → 读取活动文档 → 导出组件树到 JSON → 核对实际结果。**

先用 Windows 本地会话完成 SolidWorks 连接，避免把 WSL/容器里的运行结果当作已经连到 Windows 桌面软件。暂时不要求安装 FreeCAD、OCCT、sw2robot、仿真平台或训练模型。

## 3. 可选：已有的离线体检工具

若本机有 Python 3.10+，在仓库根目录直接运行，无需安装本项目：

```powershell
python -m cadkin inspect .\examples\three_servo_lift\three_servo_lift.zip --output .\outputs\step_intake.json
python -m unittest discover -s tests -v
```

体检工具不调用 SolidWorks，也不识别运动副。输出文件已存在时会拒绝覆盖，可换一个输出文件名。

## 文档入口

- [当前最小开发任务](docs/DEVELOPMENT_PLAN.md)
- [OpenCode 起步说明](docs/OPENCODE_START.md)
- [测试模型体检记录](docs/ASSET_AUDIT.md)
- [后续路线图](docs/ROADMAP.md)：等第一步跑通后按需推进

测试样例是 STEP，SolidWorks 可以打开；是否具备可用配合需检查实际导入结果。其余项目资料、个人路径、账号配置、API 密钥与生成的 SolidWorks 工作副本不提交。代码与样例各自的许可来源见 [LICENSE.md](LICENSE.md) 和样例说明。
