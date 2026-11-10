# 项目约定

## 环境与范围

- 正式仓库为 `leixn01/3dmodel-rcgn`；直接维护仓库，不另发仓库 ZIP。
- 用户在另一台已安装 SolidWorks 的 Windows 电脑使用 OpenCode。先确认实际运行环境，不把当前环境自动认定为那台电脑。
- 先读 README；开发时读 `docs/DEVELOPMENT_PLAN.md`。远期 `docs/ROADMAP.md` 不代表本轮任务范围。
- 样例已在 `examples/three_servo_lift/three_servo_lift.zip`，优先使用仓库文件；原 ZIP 保持不变，工作副本和结果放 `outputs/`。

## 按需加载

Skill 使用 OpenCode 默认位置 `.opencode/skills/<name>/SKILL.md`，不要把所有 skill 正文塞进全局规则或 instructions。

| 任务 | Skill |
| --- | --- |
| STEP/ZIP 来源与文本体检 | `cad-intake` |
| SolidWorks 会话、活动文档与连接诊断 | `solidworks-connect` |
| 装配组件实例树与清单 | `assembly-inventory` |

Skill 只负责流程。工具代码放 `cadkin/tools/`；后续 COM 适配器放 `cadkin/adapters/`，MCP 入口放 `cadkin/mcp_server.py`。依赖关系与实现状态见 `docs/ARCHITECTURE.md`，接口约定见 `docs/TOOL_CONTRACTS.md`。SolidWorks 工具尚未实现，不能假称调用成功；仅在任务要求开发/修复时补齐能力。

## 数据与执行

- 第一版只读访问已有 SolidWorks 会话，不自动开空实例、切换文档、保存、关闭或修改模型。
- 保留组件实例与父子关系；无文档、零件输入、抑制/轻化、部分失败分别表示。读取失败不能填成零组件。
- STEP 可在 SolidWorks 打开；导入文档类型及原 Mate 是否保留要实测。PRODUCT/NAUO 数量不是展开后的实例数量；未知运动参数不补造。
- 允许提交指定测试 ZIP 及来源校验值；其他工程文件、运行输出、账号信息和密钥不提交。
- 修改工具后运行 `python -m unittest discover -s tests -v`，区分离线测试、真实 COM 调用和人工核对。未实测就明确记录。
- 文件增删或修改后同步 `MANIFEST.json`；排除清单自身及忽略的工作输出。
