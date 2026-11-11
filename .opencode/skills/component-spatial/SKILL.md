---
name: component-spatial
description: 读取 SolidWorks 装配组件的位置、局部和整机变换、近似包围盒与尺寸，查询单个实例或导出空间清单。用于“零件在哪里”“读取组件尺寸”“导出装配空间 JSON”等请求；不执行组件移动、配合编辑或运动推断。
---

# 组件空间信息

1. 先按 `solidworks-connect` 检查会话，调用 `sw_active_document` 读取实际类型与当前 `document_token`。只读请求不自动打开、解析、重建或保存模型。若是零件，报告 `NOT_ASSEMBLY`；多实体不能冒充装配组件。
2. 查询指定实例时，先用 `assembly-inventory` 取得完整 `occurrence_path`。名称有歧义时列出候选，不按文件名猜一个实例。调用 `sw_component_spatial(expected_document_token, occurrence_path)`。
3. 导出整机优先在仓库根目录使用 `python -m cadkin spatial-export --page-size 20 --output outputs/spatial.json`（选新文件名）。工具串行采集所有页，默认整树上限 5000、64 层，每页仅计算 20 个组件的空间数据。慢机器用 `--page-size 5`；只需变换/初步分组时可用 `--without-boxes`，包围盒明确为 null/not_requested。读取期间保持模型不变，不在多个客户端并行操作。
4. 直接走 MCP 时，先调用 `sw_spatial_inventory(expected_document_token, page_size=20)`；有 `pagination.has_more` 就将 `next_offset` 作为下一页 offset，并原样传 `expected_inventory_signature`，其他查询参数不变。单页 complete=false 不代表字段读取失败；最后一页也不等于完整集合。不要手工拼聊天摘要来冒充全量 JSON，完整持久化优先使用上述 CLI。检查导出文件的 `collection_complete`、`hierarchy_complete`、`complete`、`truncated`、errors；INVENTORY_CHANGED 重新采集，部分失败保留已读记录，超时先核对现场并重启 MCP。保留实例路径、父路径、配置、单位、矩阵和错误；同文件实例分别保留。
5. 解释 `origin_root_mm` 为组件原点在整机中的位置，`origin_parent_mm` 为相对父组件原点的位置。原点不是包围盒中心或质心；STEP 实例原点相同、零位移也可能正确。`to_root` / `to_parent` 用列向量，平移单位为米；不要给已经相对根装配的 Transform2 再乘一次父变换。
6. 将 `bounding_box.size_mm` 称为“整机坐标轴方向的近似包围盒尺寸”。不要称为精密零件尺寸、行程或碰撞检测结果。原始模型位姿不包含临时展示变换；爆炸/演示状态的画面不能直接代替坐标核对。
7. 保留不可读字段为 null 和对应错误，不补零或单位矩阵；不要自动解除抑制或轻化。子件根变换可用而父变换缺失时，保留根变换、局部变换为 null；总体 partial 也可能源于其他节点的遍历错误，检查字段后再说明范围。
8. 验收时按 `docs/MCP_ACCEPTANCE.md` 的 0.5.0 分页清单及 0.3.0 坐标清单，核对至少三个实例与实际窗口/坐标，并记录是否改变文档、选择或显隐状态。读取期间不要操作界面，返回不是原子快照；没有实机证据就标记待验证。读取之后需要高亮或隐藏时再使用独立的选择/显隐流程。

在仓库根目录查看 `docs/TOOL_CONTRACTS.md` 的精确 Schema、坐标约定、上限与失败处理。执行代码位于 `cadkin/adapters/spatial.py` 和 `cadkin/geometry.py`，不在本 skill 内复制实现。
