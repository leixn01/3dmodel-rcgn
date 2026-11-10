# 仓库状态

更新：2026-11-10。正式仓库：[leixn01/3dmodel-rcgn](https://github.com/leixn01/3dmodel-rcgn)，默认分支 `main`。

| 内容 | 状态 |
| --- | --- |
| 指定测试模型及来源校验 | 已随普通 Git 克隆提供 |
| 离线 STEP/ZIP 体检 | 已实现，代码位于 `cadkin/tools/intake.py` |
| OpenCode skill | 三个独立 SKILL.md，使用默认发现目录 |
| SolidWorks 分层及接口 | 已设计，见 ARCHITECTURE.md 和 TOOL_CONTRACTS.md |
| COM 适配器、SolidWorks 工具、MCP 服务 | 待实现 |
| Windows / SolidWorks / OpenCode 联调 | 待目标电脑实测 |

运行环境为用户已安装 SolidWorks 的 Windows 电脑。Python 包名 `3dmodel-rcgn`、导入包 `cadkin`；打开 STEP 不要求安装本项目。工作输出放 `outputs/`。

首个任务是连接和活动文档读取，随后封装 MCP，再增加组件树。实施步骤见 [开发计划](DEVELOPMENT_PLAN.md)，验证记录见 [VALIDATION.md](VALIDATION.md)。
