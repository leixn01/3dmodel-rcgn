# 项目约定

## 环境与范围

- 正式仓库 `leixn01/3dmodel-rcgn`，直接维护仓库。用户在另一台已安装 SolidWorks 的 Windows 电脑使用 OpenCode；先确认实际执行位置。
- 先读 README。当前已有 MCP 0.3.0（15 个工具）；用户已确认打开模型可用，下一步按 `docs/DEVELOPMENT_PLAN.md` 验收空间读取、显示控制及其他未测功能；不重新搭建已有功能，不把远期路线图一次性实现。
- 可直接打开的模型已在 `examples/three_servo_lift/3X Lift Assembly.STEP`，不要再要求用户解压；原始输入保持不变，需修改的工作副本和结果放 `outputs/`。

## 功能与分层

| 任务 | Skill |
| --- | --- |
| STEP/ZIP 体检 | `cad-intake` |
| 会话与活动文档检查 | `solidworks-connect` |
| 组件实例树 | `assembly-inventory` |
| 实例位置、变换与近似包围盒 | `component-spatial` |
| 打开/导入或重建文档 | `solidworks-document` |
| 标准视图/缩放 | `solidworks-view` |
| 基准面等辅助对象显隐 | `solidworks-display` |
| 装配组件显隐 | `component-visibility` |
| 选择/清空组件选择 | `component-selection` |

Skill 使用 `.opencode/skills/<名称>/SKILL.md`，只保留流程；工具放 `cadkin/tools/`，COM 与 STA 放 `cadkin/adapters/`，MCP 在 `cadkin/mcp_server.py`。不把程序塞入 skill，不在 CLI/MCP 各写一套业务逻辑。精确参数见 `docs/TOOL_CONTRACTS.md` 与工具 Schema。

## 执行和数据

- 用户已要求开发连接与操作能力。当前工具可按任务打开模型、调整视图、控制辅助对象/组件显隐、选择组件或重建；只读检查请求不顺带执行这些动作。不自动启动空会话、关闭用户文档或保存覆盖。
- 操作前读取并使用当前文档 token；执行期间逐个调用工具。超时不表示操作取消，先核对 SolidWorks 状态再重启 MCP，不盲目重试。
- 保留组件实例/父子关系及错误；不得把部分结果或 API 失败写成完整空列表。STEP 文本 PRODUCT/NAUO 数量不是展开后的实例数。
- STEP 可在 SolidWorks 打开；实际导入类型与 Mate 是否保留需核对。未知运动参数不补造。
- 只提交指定样例及其校验来源；用户其他工程、outputs、账号凭据和密钥不提交。
- 完整测试：先安装 `.[solidworks]`，再运行 `python -m unittest discover -s tests -v`。基础体检可单独运行 `python -m unittest discover -s tests -p test_intake.py -v`。
- 明确区分测试替身、真实 stdio 协议、真实 COM 与人工窗口核对；未实测不能记为通过。
- 每次新增或改变功能，都在 `docs/MCP_ACCEPTANCE.md` 追加对应版本的验收项：前置条件、准确工具与参数、预期返回、窗口/数据核对、失败标准和证据保存位置。完成回复必须给出更新方式和本次验收入口，不能只说“测试通过”。
- 空间数据用列向量，矩阵平移为米；Transform2 已相对根装配，不重复乘父级。原点不等于质心，包围盒为近似轴对齐边界，不能用于精密测量或直接认定碰撞。
- 保留第三方许可与固定来源，变更后同步 `MANIFEST.json`，排除清单自身与忽略的输出。
