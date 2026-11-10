---
name: component-spatial
description: 读取 SolidWorks 装配组件的位置、局部和整机变换、近似包围盒与尺寸，查询单个实例或导出空间清单。用于“零件在哪里”“读取组件尺寸”“导出装配空间 JSON”等请求；不执行组件移动、配合编辑或运动推断。
---

# 组件空间信息

1. 先按 `solidworks-connect` 检查会话，调用 `sw_active_document` 读取实际类型与当前 `document_token`。只读请求不自动打开、解析、重建或保存模型。若是零件，报告 `NOT_ASSEMBLY`；多实体不能冒充装配组件。
2. 查询指定实例时，先用 `assembly-inventory` 取得完整 `occurrence_path`。名称有歧义时列出候选，不按文件名猜一个实例。调用 `sw_component_spatial(expected_document_token, occurrence_path)`。
3. 导出整机时调用 `sw_spatial_inventory(expected_document_token)`，默认最多 500 个节点、64 层。检查 `status`、`complete`、`truncated`、`errors` 和每项 `spatial_status`。只有数量/深度限制时可在 Schema 范围内适度增加上限重读；未解决前明确标记部分清单。若超时，按接口文档处理，不重复排队调用。
4. 保留实际返回的完整 JSON：单件位于 `data.component`，整机位于 `data.components`。保留实例路径、父路径、引用配置、文档信息、单位、矩阵约定和错误；相同文件的不同实例分别保留。用客户端文件工具或共享 CLI 的 `--output` 写入 `outputs/` 下新文件，不从摘要重编数字、不覆盖旧结果；若客户端截断，改用 CLI 保存原始完整结果并检查文件。
5. 解释 `origin_root_mm` 为组件原点在整机中的位置，`origin_parent_mm` 为相对父组件原点的位置。原点不是包围盒中心或质心；STEP 实例原点相同、零位移也可能正确。`to_root` / `to_parent` 用列向量，平移单位为米；不要给已经相对根装配的 Transform2 再乘一次父变换。
6. 将 `bounding_box.size_mm` 称为“整机坐标轴方向的近似包围盒尺寸”。不要称为精密零件尺寸、行程或碰撞检测结果。原始模型位姿不包含临时展示变换；爆炸/演示状态的画面不能直接代替坐标核对。
7. 保留不可读字段为 null 和对应错误，不补零或单位矩阵；不要自动解除抑制或轻化。子件根变换可用而父变换缺失时，保留根变换、局部变换为 null；总体 partial 也可能源于其他节点的遍历错误，检查字段后再说明范围。
8. 验收时按 `docs/MCP_ACCEPTANCE.md` 的 0.3.0 清单，核对至少三个实例与实际窗口/坐标，并记录是否改变文档、选择或显隐状态。读取期间不要操作界面，返回不是原子快照；没有实机证据就标记待验证。读取之后需要高亮或隐藏时再使用独立的选择/显隐流程。

在仓库根目录查看 `docs/TOOL_CONTRACTS.md` 的精确 Schema、坐标约定、上限与失败处理。执行代码位于 `cadkin/adapters/spatial.py` 和 `cadkin/geometry.py`，不在本 skill 内复制实现。
