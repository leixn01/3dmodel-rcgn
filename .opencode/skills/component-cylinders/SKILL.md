---
name: component-cylinders
description: 从 SolidWorks 指定零件实例读取解析圆柱面的轴线和半径，给组件分组、轴类或孔类零件分析提供几何候选。用于“找圆柱轴线”“读取轴孔半径”“没有配合时补几何证据”；不认定运动副、孔轴配合、导程或行程。
---

# 圆柱面轴线候选

1. 按 `solidworks-connect` 读取当前装配和 token，从最新实例树取一个已解析零件的完整 occurrence_path。在本地已激活 Conda 环境中使用 `python`。目标为子装配时选择具体零件；只读任务不自动解析、打开零件或切换配置。
2. 调用 `sw_component_cylinders(expected_document_token=..., occurrence_path=...)`。默认 max_bodies=50、max_faces=500、max_cylinders=100；限制是单次全局预算，出现 partial/truncated 时不能把已读结果说成所有圆柱面。慢零件可先减小 max_faces，不扫描整机全部面。
3. COMPONENT_MODEL_UNAVAILABLE 表示零件定义未加载；COMPONENT_CONFIGURATION_MISMATCH 表示当前定义配置与引用配置不符或中途变化；NOT_PART_COMPONENT 表示目标不是零件。保留错误并解释需要核对的模型/配置，不自动激活配置或编造轴线。COMPONENT_CHANGED/DOCUMENT_CHANGED 的结果不得继续拼接使用。
4. 保存原始 JSON 到 outputs 新文件，保留源零件配置/dirty、实例、变换、body_index/face_index、raw_array、原点/单位轴向/半径与错误。可使用共享 CLI 的 --output，不能从聊天摘要重编数值。
5. 明确 geometry_scope=referenced_part_definition：这是零件定义几何放置到当前实例位置的结果，不包含装配级切除等实例特有修改。配置已核对仍不等于装配实例几何完全一致；用于连接关系判断前必须核对窗口和装配修改。
6. 原始 CylinderParams 的点/半径单位为米；origin_root_mm 和 radius_root_mm 是整机单位毫米结果。轴向已归一化，轴点不是中心/端点；轴向正负不表示运动正方向。Transform2 已相对根装配，不能再乘父矩阵。
7. 每个解析圆柱面一条记录，同轴分割面可有多条；body/face 索引仅对这次快照有效，不能直接当持久选择 ID。cylinders=[] 只表示此次范围内没有读到解析圆柱面，NURBS、圆锥、螺纹或基准轴未拟合识别。不能自动标为孔/轴、旋转副、直线副、行程或导程。
8. 按 0.6.0 验收核对一个已知圆柱件与其重复实例的半径/轴向/位置、文档与选择是否不变。需要确认机械角色时复用独立分组复核流程，保留待确认项。

实现位于 `cadkin/adapters/cylinders.py` 和 `cadkin/geometry.py`；字段及上限见仓库根目录 docs/TOOL_CONTRACTS.md。
