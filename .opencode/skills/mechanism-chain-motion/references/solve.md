# 调用与范围

MCP cad_solve_chain_constraints必填constraint_analysis_path、reference_occurrence_path、characteristic_length_mm、output_path。原analysis v1/v2及所有来源必须可回读。范围来自原target的全部叶实例（2–20个），不能靠筛掉不方便的组件让结果完整。超范围需由chain-evidence明确新链及边界，保留原链。

特征长度0.001–1000000毫米；优先沿用局部求解尺度，否则根据已有跨度选代表值并记录依据。没有依据可明确用100毫米计算基准，不把它解释成行程。参考实例可选择链中的基座候选或首个实例，但必须说明这只是相对速度坐标约定，不依赖IsFixed或名称证明接地。

可选relative_rank_tolerance默认1e-8（1e-10–1e-3），max_constraints_per_pair默认200（1–200）；截断使结果不完整。几何公差沿用原analysis，不与数值阈值混用。

```powershell
python -m cadkin solve-chain-constraints outputs/constraints.json --reference-occurrence-path "实际根实例路径" --characteristic-length-mm 100 --output outputs/chain-motion.json
```

摘要含solution_source/coverage/逐快照维数/图回路数/缺口和冲突计数。完整文件保存每行原配合证据、各组件运动模式、共同原点与变量顺序、输入哈希及原补采历史。结果文件不是cad_plan_evidence_tasks的constraint_analysis_path；后续采集继续使用原analysis/check/index。

INVALID_ARGUMENTS/CHAIN_SCOPE_LIMIT先修正范围或参考路径；EVIDENCE_MISMATCH不能改旧哈希绕过；OUTPUT_EXISTS仅换新求解文件。求解不连接COM，不需要重新检查会话或重复读取几何。
