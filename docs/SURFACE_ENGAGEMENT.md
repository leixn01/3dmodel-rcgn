# 0.30.0 表面配合假设补证

从0.29有限圆柱轴向包络继续：读取有限查询点的面成员关系、定向法向及真实边邻面，离线汇总内外表面互补和邻接端面候选。模板可省略；结果不是已确认的物理配合、运动副或行程。

| 工具 | 输出 | 范围 |
| --- | --- | --- |
| sw_sample_cylinder_face | 原始点、投影、法向、成员关系、采样材料侧 | 一面1–32点；持久面及原边界前后核对 |
| sw_read_face_adjacency | 每边两槽邻面、持久ID、同体身份、descriptor | 一面默认64边；缝边/null保留，邻接回读 |
| cad_analyze_surface_engagement | 摘要与完整来源绑定报告 | 离线消费保护通过的观测；生成缺失读取所需明确查询点 |

`cad_plan_evidence_tasks`新增互斥`engagement_analysis_path`入口（v8）。只读采集、证据重放/数学解释、计划、执行和skill各自分离。新增三个功能skill，入口仅讲当前任务，细节按需展开。

## 运行流程

1. 以原finite报告调用离线分析；已有更新index必须传入，沿用原check与全部历史。
2. 需要补证时规划v8；两个实例两面通常为4次读取+6次保护，批次可一次执行。不是每个采样点一次MCP请求。
3. batch完整且保护通过后索引原receipt，携最新index重新分析原finite报告，再规划确认stop。输出写新路径。
4. 已有失败/partial不重采；距离、目录、边界、补证共享最多四轮。已耗尽则输出剩余风险，不重建链或会话绕过。

CLI支持`python -m cadkin plan-evidence CHECK --engagement-analysis REPORT --output NEW_PLAN`；通用`python -m cadkin sw TOOL --arguments JSON`使用同一生产工具层。Windows本机仍使用用户已有Conda。

## 解释边界

- 共同轴向包络内2个站位、8个角向方向，每侧在自身解析圆柱上生成点。两侧UV无需对应；同面跨候选去重，最多32点，遗漏明确保留。
- GetClosestPointOn距离在阈值内仅证明相应查询的有限面成员关系；16/16不证明360度、点间区域、接触或实际啮合，计数不是面积/概率。
- Solid body法向相对于径向的方向支持该采样点inner/outer；两个outer不算互补，sheet只报告定向法向。点间距离和法向对向分别输出，未判定装配间隙或配合公差。
- IEdge.GetTwoAdjacentFaces2、IsSame同体/选中面核对和持久引用round-trip提供真实邻接；缝边排除于端面列表。邻接平面的相向/位置接近不证明有限端面相交、接触、挡肩或轴向保持。
- 来源仍是放置后的零件定义，不包含装配级切除；快照非原子。旧来源错误、遗漏、失败及竞争解释保持。目标类型unknown，DOF/行程null；不向原生约束求解器伪造mate。

## 验证

运行`python scripts/verify_surface_engagement.py --output outputs/verify-surface-engagement-0.30`，重跑换新目录。包含完整、半圆、同向外表面、法向失败、邻接失败五种明确合成情境；真实SDK/stdio集成测试也使用隔离CAD替身。它们验证实现，不是升降机实测。

实机逐项记录新工具的原envelope、receipt/index、耗时、完整/部分/失败状态；严格沿用当前geometry/finite/check/index，不修改STEP。完整采样仍不能标记运动识别完成。

下一步先用这些证据核查候选端面的有限区域重叠及接触方向，再设计有状态恢复的受控运动验证。未经验证不执行拆卸。
