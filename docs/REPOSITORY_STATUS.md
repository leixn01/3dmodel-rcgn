# 仓库与开发约定

- 正式仓库：[leixn01/3dmodel-rcgn](https://github.com/leixn01/3dmodel-rcgn)，默认分支 `main`。
- 执行位置：用户另一台已安装 SolidWorks 的 Windows 电脑；使用 OpenCode 本地开发。
- 当前任务：连接已有 SolidWorks 会话，读取活动文档及组件树。
- 当前已有：测试模型、离线 STEP 体检工具、中文起步说明及 AGENTS.md。
- 测试模型：`examples/three_servo_lift/three_servo_lift.zip`，随普通 Git 克隆提供；解压与工作副本保存在 outputs/。
- Python 包名 `3dmodel-rcgn`，导入包 `cadkin`；打开模型无需先安装本项目。
- 代码、方案、验证说明在仓库维护；当前无 SolidWorks 实机验收结果。
- 持续集成结果见仓库 Actions；后续方向见 docs/ROADMAP.md。
