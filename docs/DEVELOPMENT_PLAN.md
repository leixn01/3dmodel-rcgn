# 当前开发计划

更新：2026-11-10。目标环境为用户已安装 SolidWorks 的 Windows 电脑，使用 OpenCode 本地开发。测试模型已内置；用户手动打开 STEP。

## 第一步：连接工具与最小 MCP

加载 `solidworks-connect`，只实现以下闭环：

1. 检查本机 Windows、Python、SolidWorks 与 OpenCode 版本，确定最少依赖；不安装整套 CAD/仿真环境。
2. 在 `cadkin/adapters/solidworks.py` 实现只读连接已有 SolidWorks 会话；在 `cadkin/tools/solidworks.py` 提供 `sw_session_status`、`sw_active_document`。
3. 为 CLI 增加可重复执行的连接检查命令，实际读取版本、标题、路径、文档类型和活动配置。按 `docs/TOOL_CONTRACTS.md` 区分未运行、无文档和 API 失败。
4. CLI 实测后，在 `cadkin/mcp_server.py` 注册同一组工具，使用本地 stdio。保持串行 COM 调用及正确的线程生命周期；协议输出与日志分开。
5. 按本机 OpenCode 版本添加项目 MCP 配置，通过 Agent 工具调用验证得到同一实际文档；记录运行命令、依赖版本、错误处理和实测证据。

完成条件：CLI 与 OpenCode 经 MCP 均能读到用户当前打开的模型；模型没有被修改。没有目标电脑实测时只能标记实现待验收。

## 第二步：独立的组件树工具

第一步通过后加载 `assembly-inventory`，增加 `sw_component_tree`：

1. 读取当前活动配置并遍历装配；多实体零件明确报告类型，不伪装装配。
2. 保留实例路径、父子关系、实例名称、文件路径、引用配置、抑制/轻化与读取状态；重复零件不合并。
3. 返回文档上下文、完整性、错误和统计口径，由 CLI 或 Agent 保存到 `outputs/solidworks_inventory.json`。
4. 处理无文档、错误文档类型、未解析与部分失败，并与 SolidWorks 模型树核对若干实例。

完成条件：层级和实例能对应真实模型树，错误与部分结果明确，原模型不变。

## 后续

组件树验证后，再分别增加组件变换、配合读取与运动关系推断能力；每项有独立工具契约和 skill。暂不展开运动仿真、PLC 或整套平台。完整方向见 [路线图](ROADMAP.md)。

当前已完成目录整理、三个流程说明及接口设计；COM 适配器、SolidWorks 工具、MCP 服务与实机验收均待完成。
