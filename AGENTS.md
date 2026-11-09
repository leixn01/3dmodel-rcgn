# 项目开发说明

## 当前环境与任务

- 用户将在另一台已安装 SolidWorks 的 Windows 电脑上使用 OpenCode。不要重复要求用户安装 SolidWorks，也不要把当前运行环境自动认定为那台电脑。
- 正式仓库是 leixn01/3dmodel-rcgn。直接维护仓库，不另发仓库 ZIP。
- 先读 README.md、docs/DEVELOPMENT_PLAN.md 和 docs/OPENCODE_START.md。docs/ROADMAP.md 是后续参考，不是本轮全部任务。
- 当前只做一件事：在目标电脑连接正在运行的 SolidWorks，读取当前活动文档基本信息及组件树，导出 JSON 并核对。不自动扩展到运动副识别、刚体分组、仿真或 PLC 联调。
- 测试样例已经在 examples/three_servo_lift/three_servo_lift.zip。先使用仓库内文件，不再要求用户另行下载或上传同一模型。

## 实现与验证

- 先检查 Windows、本地运行方式、可用 Python/COM 环境和 SolidWorks 版本，再选择最小实现。若需要依赖，明确新增内容与安装命令；不要先安装一整套 CAD/仿真依赖。
- 用户可手动打开 STEP。脚本优先只读连接已有 SolidWorks 实例，不关闭软件、不修改或覆盖模型、不静默创建空会话来伪装成功。
- 分别处理无活动文档、零件文档、装配文档和 API 读取失败；读取失败不能填成零组件。
- 保留组件出现路径、父子关系、实例名称、抑制/解析状态。空文件路径或轻化组件要显式记录，不静默漏件。
- 输出放 outputs/，不得把 STEP 文本中的 PRODUCT/NAUO 数量当作 SolidWorks 的组件实例统计。
- 开发后运行相关检查，区分离线单元测试、COM 实测和人工视图核对。没有 SolidWorks 实测就如实记录。
- 现有测试命令：python -m unittest discover -s tests -v。

## 数据与后续约束

- 用户已明确要求将指定测试模型放进仓库：允许提交上述单一测试 ZIP、来源和校验值。其他 CAD/PLC/电气工程、outputs/、账号配置和密钥不提交。
- 保持原始 ZIP 不变，解压到 outputs/；修改副本与原始输入分开。
- STEP 可在 SolidWorks 打开；原设计 Mate 是否保留要检查，不能由文件格式直接下结论。
- 后续识别时区分 CAD 实例、刚体和运动副；未知行程、限位、轴线及信号不得补造。先完成当前小任务，再推进下一步。
