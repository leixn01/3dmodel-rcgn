# 原生配合独立分析（0.27.0）

根装配的配合现在可直接进入组件关系图和约束求解，**不再要求先取得两份圆柱扫描**。平面零件、无圆柱零件或圆柱扫描失败时，只要原生配合和实例上下文有效，就能分析已支持的约束。新增离线工具cad_review_root_mates；当前51个工具、44个解耦功能skill。

## 两种入口

| 已有数据/任务 | 使用方式 |
| --- | --- |
| 完整空间清单和原始根配合文件 | cad_review_root_mates离线关联，再构建链/目标图和约束分析；不重采 |
| 首次只分析一条链的原生配合 | chain-session配置capture_profile="root_mates"，一次增强配合采集和完整保护 |
| 同时需要圆柱几何候选 | 保持默认geometry_and_mates；配合仍独立建源，扫描失败保留历史 |
| 已有check/index/receipt | 沿用最新历史，执行/回填/缺口规划；不切模式重跑首轮 |

首次配置方法见[单链联调](CHAIN_SESSION.md)。root_mates只读取活动根装配配合及其直接引用的几何类型/参数，不遍历零件实体的圆柱面。默认模式不变；只读配合模式不会在无配合时自动转为圆柱扫描。

## 离线工具与来源

cad_review_root_mates必填参数示例（文件名由实际采集确定）：

```json
{
  "inventory_path": "outputs/spatial.json",
  "mate_inventory_path": "outputs/root-mates.json",
  "output_path": "outputs/root-mate-review.json"
}
```

输出摘要含review_source的path/sha256及counts/coverage/complete。完整文件为connection_review_schema_version=2，sources只绑定inventory和mates；geometry_candidates_evaluated=false。后续工具重放原始来源和关联计算，修改原始文件字节或派生实例对会被拒绝。

只有准确的双实体、双实例配合被关联；根引用、未映射、多实体及数量不一致的记录保留为unmatched_mates。抑制、回滚、特征错误和读取失败仍可见。包含face_matching的文件继续走原cad_review_connections并携带圆柱关系来源，不能删字段绕过；旧schema v1文件仍可重放。

关联文件进入cad_build_chain_evidence的evidence_paths，然后交给cad_build_target_graph→cad_analyze_constraints→cad_solve_chain_constraints。参考实例、数值尺度与公差仍须明确。原生配合可支持既有的lock/同心/重合平面瞬时方程；其他类型和缺参数保留缺口。

## 效率与边界

N个实例的root_mates初始计划需要2N+3次工具调用：2N+2次前后文档/位姿保护及1次增强根配合采集。默认模式可能先完成基础配合和圆柱，再补增强配合。三组件闭合链的合成验收中，采集与保护调用从21降至9；不含入口的活动文档/空间清单调用，也不是实机耗时加速比。批次可因时间预算拆分，继续原receipt即可。

完整、失败、partial都进入索引并计入共享4轮。只有完整且保护通过的采集可自动建基线；partial在首轮可能没有可用基线，此时保留未成功尝试和未知，不重扫。直接离线关联partial来源可保留已读记录，但不会把它升级为完整证据。

无配合STEP仍不能仅凭名称、模板或几何相似性确认运动副。本版没有自动运动、碰撞检查、有限行程或拆卸路径验证，也不含子装配内部配合。目标类型/DOF仍保留unknown/null；模型支持的瞬时维数与真实机构自由度分开。

## 验证

```powershell
python scripts/verify_root_mates.py --output outputs/verify-root-mates-0.27
```

预期passed=true、54项检查；合成案例覆盖闭合链、平面、锁定、无配合、增强partial、默认模式及圆柱全失败。重跑使用新目录。实机步骤见[0.27验收](MCP_ACCEPTANCE.md#0270原生配合独立分析)。
