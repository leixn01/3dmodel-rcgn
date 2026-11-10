---
name: assembly-inventory
description: 读取 SolidWorks 活动装配的组件树，保留重复实例、父子关系及抑制或未解析状态，导出并核对清单。不负责运动推断、组件移动或配合编辑。
---

# 装配组件清单

以下输出路径相对于仓库根目录。接口见 [工具约定](../../../docs/TOOL_CONTRACTS.md)。

1. 调用 `sw_active_document`；仅对装配调用 `sw_component_tree`。若 STEP 导入为多实体零件，如实报告类型，不输出空装配。
2. 核对返回文档/配置与目标一致，检查实例路径、父子关系、名称、文件路径、引用配置及读取状态；同一文件的不同实例不合并。
3. 检查 `status`、`complete` 和 `errors`。部分结果保留原始错误，不自动解析轻化组件；达到数量/深度上限时按需要调整参数重读并明确口径。
4. 用文件工具将实际 JSON 保存到 `outputs/solidworks_inventory.json`，已有文件改用新名称。也可用共用 CLI 的 `--output`；不得手工补造缺失数据。
5. 与 SolidWorks 模型树核对根装配和若干实例，报告包含子装配、抑制和未解析项的统计口径；未作人工核对就说明未核对。

需要选择某个组件时交付其完整 `occurrence_path` 和文档上下文，不在本流程内移动或修改几何。
