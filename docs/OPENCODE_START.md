# 在已安装 SolidWorks 的电脑上开始

## 准备

1. 在 Windows 本地取得仓库并按 README 解压内置测试包。
2. 手动在 SolidWorks 中打开 `outputs/three_servo_lift/temp/3X Lift Assembly.STEP`，保留该窗口。
3. 在仓库根目录启动 OpenCode。项目规则已经放在根目录 AGENTS.md，无需重新生成一套规划。

打开 STEP 不要求先安装 Python。开发 COM 读取程序时，再让 OpenCode 检查本机环境并说明最少需要哪些依赖。

## 给 OpenCode 的第一个任务

复制下面这段到 OpenCode：

```text
先阅读 AGENTS.md、README.md 和 docs/DEVELOPMENT_PLAN.md。
这台 Windows 电脑已经安装了 SolidWorks，测试模型已放在仓库的
examples/three_servo_lift/three_servo_lift.zip 中。我会手动打开里面的 STEP。

我们从最小功能开始：请在本机实现并验证一个只读脚本，连接正在运行的
SolidWorks，读取当前活动文档的版本、名称和文档类型；如果是装配文档，
导出其组件树到 outputs/solidworks_inventory.json。每个组件至少记录
实例名称、完整出现路径、父组件、可用文件路径和读取状态。

先检查实际执行环境，再选最少的依赖。不要关闭或修改我已打开的模型，
不要自动安装其他 CAD 或仿真软件。没有活动文档、导入为零件、组件未解析
或 API 调用失败时请明确报告，不要生成空结果后声称成功。

完成后给出运行命令，实际运行并与 SolidWorks 模型树核对几个组件。
这一步只做连接和组件读取，不做运动副识别、动画、PLC 或整套平台开发。
```

## 怎样判断这一步已经完成

有实际目标电脑上的运行结果，而不只是脚本或 mock 测试。核对当前窗口与 JSON 的文档名称、类型，以及根节点下几个组件的实例名称和层级。记录数量时说明是否包含子装配节点、抑制组件和未解析项。

本仓库现有的 `python -m cadkin inspect ...` 是离线 STEP 文本统计，不能替代上述 SolidWorks 实测。

## 工作结果放哪里

脚本和必要文档进入 Git；执行结果、截图和另存的 SolidWorks 文件留在 `outputs/`。提交时检查 `git status`，只提交此次任务相关的代码与说明。

规则文件用法参考 [OpenCode 官方说明](https://docs.opencode.ai/docs/rules/)。
