---
name: component-constraints
description: 读取 SolidWorks 指定组件的固定或浮动标志、关联配合及配合引用参数，用于“零件是否固定”“有哪些配合”“给分组补充约束证据”。保留嵌套层级与未知状态，不求解自由度、不修改配合、不把无配合当可自由运动。
---

# 组件约束证据

1. 按 `solidworks-connect` 核对活动装配、当前 token 和运行环境。使用本地已激活 Conda 的 `python`，不创建或调用项目虚拟环境。读取最新组件树，确定完整 occurrence_path，不按零件文件名合并实例。
2. 串行调用 `sw_component_constraints(expected_document_token=..., occurrence_path=...)`，默认最多 100 个配合、每个配合 16 个实体。只查指定实例，不扫描整机所有配合。超过上限时保留 partial/truncated，按需要增加至 Schema 允许范围；超时先检查现场并重启 MCP，不盲目重试。
3. 保留实际返回的原始 JSON 到 outputs 新文件，可用共享 CLI `python -m cadkin sw sw_component_constraints --arguments '<实际JSON>' --output outputs/<新文件>.json`。用户只需离线解释已有记录时，不启动或修改 SolidWorks。
4. 分别报告 fixed_state、reported_mate_count、read_mate_count、complete、truncated、errors。IsFixed 只对当前根装配顶层组件有效；嵌套返回 null 和 FIXED_STATE_CONTEXT_UNAVAILABLE，不据根上下文说子件浮动。顶层 false 也不等于未受配合约束；导入时的固定标志不等于机械固定基体角色。
5. 将 mates=[] 且 reported_mate_count=0 解释为“本次 GetMates 未返回关联配合”，不证明自由运动。mates=null/读取错误不能说“没有配合”。IMateInPlace 等未支持记录保留部分信息，不丢弃。
6. 配合 type_code 保留原始枚举，type_name 只是已知枚举名称；未知代码不猜。ReferenceType2 是选择对象类别，不足以区分圆柱面/平面。reference_component_name 是原 API 上下文名称，未经验证不能当根装配完整路径去选择。EntityParams 位于该配合所属装配坐标系；不自动乘组件矩阵、不视为整机轴线。抑制/求解状态未读取，不据配合类型自动确认刚体或自由度。
7. 将结果作为角色候选的补充证据；与窗口特征树和用户确认核对后再走 `component-grouping` 的复核流程，不自动改已有分组。需要几何轴线时独立使用 `component-cylinders`。

工具代码在 `cadkin/adapters/constraints.py`，共享目标校验在 `cadkin/adapters/evidence.py`；精确字段和 0.6.0 验收见仓库根目录 docs/TOOL_CONTRACTS.md、docs/MCP_ACCEPTANCE.md。
