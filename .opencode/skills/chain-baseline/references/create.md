# 调用和结果

`cad_create_chain_baseline`参数：execution_path、output_path、distance_tolerance_mm（正有限数）、angle_tolerance_deg（0到5度，含5）。output_path必须是outputs下未使用的JSON。也可用通用CLI：

```powershell
python -m cadkin sw cad_create_chain_baseline --arguments '{"execution_path":"outputs/first-receipt.json","output_path":"outputs/baseline.json","distance_tolerance_mm":0.1,"angle_tolerance_deg":0.1}'
```

优先MCP结构化参数，避免Windows shell转义问题。示例公差必须由当前任务明确选择，不能称已经实机标定。

要求原plan为无索引的初始计划、所有任务有终态且前后保护通过、初始target没有relation/source coverage。已有来源/历史报BASELINE_ALREADY_EXISTS，保护失败报EXECUTION_GUARDS_FAILED，内容变化报EVIDENCE_MISMATCH，已占用文件报OUTPUT_EXISTS；均不调用CAD。

成功时baseline_created=true，outputs给出chain/target/rigid/draft/check/index/constraints的path+sha256。索引从原receipt生成，首轮计为1/4；保留所有失败/partial和补充上下文。至少两个完整圆柱envelope（允许完整空扫描）才建立现有关系基线；根配合还需本轮完整观测。能力缺失时不生成伪造来源，未应用记录仍进入索引。

报告baseline_source仅作为运行诊断，不替代原check/index/analysis输入。只有baseline_created=true的outputs可交接；pipeline_error时outputs为空，派生中间文件只诊断。不会加载参考模板、推断运动副、移动零件或证明真实运动。
