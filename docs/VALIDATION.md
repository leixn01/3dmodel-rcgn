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

## OpenCode skill 与工具分层

2026-11-10，Python 3.12.14。

- 三个 SKILL.md 的 YAML 元数据、命名与目录对应关系校验通过；本地 Markdown 引用均可解析。
- 工具移到 `cadkin/tools/intake.py` 后，原有 5 个单元测试通过，包发现包含 `cadkin.tools`。
- 用仓库内真实测试 ZIP 对比移动前实现与当前 CLI，JSON 输出完全一致。
- 单独按 `cad-intake` 流程执行只读检查成功；ZIP 大小、SHA-256、成员清单及 CRC 核验通过。
- 分层说明与三个 SolidWorks 工具契约已完成；尚未实现 COM 适配器或 MCP 服务，没有启用不存在服务的配置。

当前执行环境没有进行 Windows PowerShell、SolidWorks 或 OpenCode 客户端的实跑。文件布局按官方规则静态核对，不代表已验证客户端自动发现；上述离线检查也不代表 SolidWorks 连接和组件导出已完成。这些将在用户的目标电脑实现与验证。
