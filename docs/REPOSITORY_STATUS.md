# 仓库状态

更新：2026-11-10。正式仓库：[leixn01/3dmodel-rcgn](https://github.com/leixn01/3dmodel-rcgn)，默认分支 `main`。Python 包版本 0.2.0。

| 内容 | 状态 |
| --- | --- |
| 测试 STEP/ZIP 与来源校验 | 已提供 |
| 离线输入体检 | 已实现，无 CAD 软件依赖 |
| 八个 OpenCode skill | 按默认目录拆分 |
| 13 个 SolidWorks 工具与 CLI | 已实现，离线测试通过 |
| MCP stdio 与项目配置 | 已实现，协议测试通过 |
| Windows + SolidWorks COM / OpenCode 客户端 | 用户已确认打开模型可用，其余工具待实测 |
| 自动拆解、运动副推断、配合编辑 | 未实现 |

复用范围见 [第三方说明](../THIRD_PARTY_NOTICES.md)。工具详情见 [接口约定](TOOL_CONTRACTS.md)，下一步见 [实机验收](DEVELOPMENT_PLAN.md)。输出留在 `outputs/`，不提交用户工程与本机配置秘密。
