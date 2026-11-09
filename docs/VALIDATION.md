# 验证记录

## 仓库初始化

2026-11-09，Python 3.12.14。

- 5 个离线单元测试通过。
- editable 安装及 cadkin 命令入口验证通过。
- 下载命令对固定 revision 的真实资产运行，SHA-256 与大小匹配。
- STEP 文本体检：46 个 PRODUCT、80 条 NAUO、37 个 MANIFOLD_SOLID_BREP 定义。
- 初始化提交的 GitHub Actions 在 Python 3.10 和 3.12 下通过。

## 内置测试模型与小范围起步

- 指定原 ZIP 随仓库保存，大小 1,095,163 bytes，SHA-256 与源配置一致。
- ZIP CRC 与包内 STEP/JPG 文件清单已核对；仓库文件不是 Git LFS 指针。
- 本地重新运行 5 个现有测试，并用现有工具读取仓库内 ZIP。
- README 与 OpenCode 起步任务只覆盖模型打开、连接和组件树读取。
- 最新远端 CI 状态以仓库 Actions 为准。

当前执行环境没有进行 Windows PowerShell、SolidWorks 或 OpenCode 的桌面端实跑。上述检查不代表 SolidWorks 连接和组件导出已完成；该功能将在用户的目标电脑实现与验证。
