---
name: component-grouping
description: 根据完整装配空间清单生成固定基体、移动平台、传动或导向相关件及待确认的分组候选，按实例核对并记录人工修正。用于“组件分组”“选一条升降链分析”“修改分组”等请求；不移动零件、不修改配合、不把候选直接认定为刚体或运动关系。
---

# 组件分组与复核

1. 先确认输入。已有空间 JSON 时直接使用，不连接或启动 SolidWorks。需要重新采集时按 `component-spatial` 的分页导出流程生成原始清单。检查 `collection_complete`、`hierarchy_complete`、`truncated`；单页、缺失层级和未解析节点不能当完整输入。字段级几何缺失可以保留，不补造数据。
2. 用户指定某条升降链时，从实际实例树确认其子装配完整路径，作为 `scope_occurrence_path`。不确定对应关系时先给出候选范围；可以先做整机候选分组，但不要称为已识别三条升降链。一个子装配不必然是一条运动链。
3. 调用 `cad_group_components(inventory_path=..., output_path="outputs/<新文件>.json")`，可选 `scope_occurrence_path`。工具直接写新文件并返回路径、源文件哈希、分组数量和覆盖检查。也可在仓库根目录执行 `.\.venv\Scripts\python.exe -m cadkin group outputs/spatial.json --output outputs/groups.json`；指定范围用 `--scope "完整实例路径"`。不要从聊天摘要重新生成空间数据；不要覆盖旧结果。
4. 读取输出 JSON，报告四类的数量、实例完整路径、名称规则依据和待确认项。只有叶实例被分配，子装配容器单独计数；同文件的多个实例不合并。名称命中只是候选，匿名编号或冲突名称保持 pending。近似盒中心距离只是辅助核对，不证明接触、固定、运动或同属刚体。`requires_review=true` 时明确尚待核对，不能自动确认。
5. 需要在 SolidWorks 中核对时，用独立 `component-selection` 流程按完整路径选中目标；用户要求隐藏时才用 `component-visibility` 并记录、恢复原状态。只看离线 JSON 不算窗口核对。不要批量隐藏所有实例或修改几何来证明分组。
6. 仅依据用户明确确认/修改的实例生成新复核 JSON：`inventory_sha256` 必须使用本次工具返回的原文件哈希；`assignments` 每项为 `occurrence_path`、`role`、`decision`、`reason`。role 仅为 `fixed_base`、`moving_platform`、`transmission_related`、`pending`；确认用 `decision="confirmed"` 加具体角色，暂缓用 `decision="pending", role="pending"`。记录用户的实际依据，不编造其确认；未提及实例保留原候选。
7. 再调用分组工具，使用同一 `inventory_path`、同一范围、新 `output_path` 和 `review_path`（CLI `--review`）。检查只有指定叶实例变成 `manual_confirmed` 或 pending；其他实例不变。哈希、范围或路径不符时纠正输入，不绕过校验。确认角色仍不等于确认刚体或运动副。

执行代码在 `cadkin/tools/grouping.py`；参数和文件格式见仓库根目录 `docs/TOOL_CONTRACTS.md`，新增功能验收见 `docs/MCP_ACCEPTANCE.md` 的 0.5.0。缺少包围盒时可先完成角色候选和人工复核，之后再补精确几何/配合证据。
