# 调用与尺度

MCP cad_solve_local_constraints：

- constraint_analysis_path：原cad_analyze_constraints报告，含全部可回读绑定来源。兼容v1/v2；v2已有index/check/轮数会原样保留。
- characteristic_length_mm：必填，0.001–1000000毫米；用于把线速度与角速度放到同一数值尺度。优先沿用同链已有选择。否则可以根据已有几何跨度选一个代表长度并记录依据；这是计算尺度，不是推断出的行程/半径。没有尺度依据可明确采用100毫米数值基准并在结论标注，不需要人工复核。
- output_path：outputs下不存在的新JSON。
- relative_rank_tolerance：默认1e-8，允许1e-10–1e-3；数值秩阈值，不能与几何毫米/角度公差混用。
- max_pairs：默认200，1–1225；max_constraints_per_snapshot默认200，1–2000。省略/截断不视为完整求解。

CLI示例（项目根、已有Conda环境）：

```powershell
python -m cadkin solve-local-constraints outputs/constraints.json --characteristic-length-mm 100 --output outputs/local-motion.json
```

可选--relative-rank-tolerance、--max-pairs、--max-constraints-per-snapshot。报告继承原analysis_parameters、公差和覆盖；不会补采、重置轮次或生成执行计划。所有输出保留来源哈希；原文件改动会拒绝重放，不编辑旧报告以匹配新模型。OUTPUT_EXISTS时仅为新分析换输出文件，不能以此重试已停止的采集。

数值敏感先报告秩/零空间维数范围及当前尺度；不通过不断调阈值挑选期望DOF。不支持的配合不自动加近似约束。详细数学解释仅在需要时查项目docs/LOCAL_CONSTRAINTS.md。
