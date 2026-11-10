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

## OpenCode skill 与工具分层（目录整理阶段）

2026-11-10，Python 3.12.14。

- 三个 SKILL.md 的 YAML 元数据、命名与目录对应关系校验通过；本地 Markdown 引用均可解析。
- 工具移到 `cadkin/tools/intake.py` 后，原有 5 个单元测试通过，包发现包含 `cadkin.tools`。
- 用仓库内真实测试 ZIP 对比移动前实现与当前 CLI，JSON 输出完全一致。
- 单独按 `cad-intake` 流程执行只读检查成功；ZIP 大小、SHA-256、成员清单及 CRC 核验通过。
- 分层说明与三个 SolidWorks 工具契约已完成；尚未实现 COM 适配器或 MCP 服务，没有启用不存在服务的配置。

## MCP 第一版

2026-11-10，Python 3.12.14、官方 MCP Python SDK 1.29.0。

- 已实现 8 个工具、Windows COM 适配器、STA 调度、CLI 与 stdio 服务，提供项目 OpenCode 配置。
- 22 个测试通过，覆盖原体检、文档/配置变化、组件重复与部分失败、打开/激活、选择回读、重建失败、参数拒绝、已有实例连接路径及超时后的停止执行。
- 使用真实 MCP 客户端和子进程完成 initialize、tools/list、成功调用及 isError 错误调用；成功 CAD 操作由显式测试替身提供，未调用真实 SolidWorks。
- 生产服务器在 Linux 下真实返回 UNSUPPORTED_PLATFORM，没有自动切换到模拟成功；独立按连接 skill 检查也得到一致结果。
- 构建 wheel 成功，确认包含 MCP 入口、工具包以及 Apache-2.0 LICENSE/NOTICE，不包含测试后端。
- 六个 skill 的元数据、目录及本地链接通过检查。测试模型保留原始文件与校验值。
- CI 增加 Ubuntu/Windows 和 Python 3.10/3.12 的依赖安装及离线/协议测试；远端运行状态以 Actions 为准。

当前环境没有进行 Windows PowerShell、SolidWorks 或 OpenCode 客户端的实跑。OpenCode 配置及 skill 布局按官方规则核对；协议通过不代表 COM 或客户端联调已通过。真实版本兼容性、STEP 导入和操作结果须按 DEVELOPMENT_PLAN.md 在目标电脑验收。

## 直接提供 STEP 与 MCP 验收清单

2026-11-10，Python 3.12.14。

- `examples/three_servo_lift/` 已直接包含 STEP（7,777,725 bytes）与 JPG（95,271 bytes），与原 ZIP 成员逐字节一致，SHA-256 记录在来源配置中。保留原名和原始编码，Git 禁止对这些文件进行文本转换。
- 直接 STEP 体检与读取 ZIP 内 STEP 的结果一致；原 22 项测试再次通过，CI 的新增资产完整性检查已在本地通过。
- 6 个 skill 的元数据与本地 Markdown 引用校验通过。README、使用说明与相关 skill 均使用直接 STEP 路径。
- 新增 `docs/MCP_ACCEPTANCE.md`，列出 8 个工具的实机通过标准、异常检查与结果记录方式。
- 本次未执行 SolidWorks 或 OpenCode 客户端实机验收；不能将上述结果视为 COM 操作已经通过。

## 显示控制 0.2.0 与用户反馈

2026-11-10。

- 用户反馈：在另一台 Windows 电脑使用本仓库，已确认打开模型可用；原有其他 7 项尚未验证。未提供具体 SolidWorks 版本、提交 SHA 或原始返回，因此只记录“用户确认打开可用”，不扩展为全部 COM 工具通过。
- 根据“隐藏基准面”需求增加 5 个工具，总计 13 个：辅助对象显示状态查询/设置、组件显隐查询/设置、独立缩放适合窗口。增加两个独立功能 skill，合计 8 个；执行代码仍只在工具和适配层。
- 35 项本地单元及协议测试通过：包括成功隐藏返回 false、重复隐藏不反转、类别间隔离、总开关遮挡、父装配遮挡、同文件多实例隔离、回读失败、类型库失败、旧 token 拒绝以及独立缩放不请求新视角。测试替身使用任意枚举值，验证代码按名称读取类型库而非猜数值。
- 使用真实 MCP stdio 客户端串行执行 15 次操作，完成基准面隐藏/重复隐藏/回读、rail-2 隐藏/按原值恢复、独立适合窗口；均由显式隔离测试后端响应。未将这些结果作为 SolidWorks 实机或窗口验收。
- 8 个 skill 的元数据与本地 Markdown 链接通过检查；0.2.0 wheel 构建通过，包含显示适配器及第三方许可，不含测试后端；模型原始字节校验通过。
- 新的显示 API 与类型库加载需在用户安装版本验证；新增验收标准见 `MCP_ACCEPTANCE.md`。远端 CI 状态以对应提交的 Actions 为准。
