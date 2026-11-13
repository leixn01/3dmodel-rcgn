---
name: root-mate-review
description: 将原始根装配配合直接关联到准确组件实例对，生成可进入目标图和约束分析的离线来源。用于已有空间清单与配合采集、但没有圆柱扫描或不需要几何候选的任务；不执行CAD采集、面身份匹配或运动求解。
---

# 根配合关联

输入：完整空间清单和原始sw_mate_inventory envelope。输出：新的根配合关联文件及摘要，绑定原始来源；不调用SolidWorks。

1. 输入齐全时调用cad_review_root_mates，传inventory_path、mate_inventory_path、output_path（outputs内新文件）。不用为了此入口补采圆柱。
2. 输入缺失才交接component-spatial或assembly-mates。已有面身份匹配文件需其原几何来源，交接connection-review；不能删去面匹配字段绕过检查。
3. 先读摘要complete/counts/coverage；需要实例对、状态、未解析引用或失败处理时再读[结果与边界](references/interpretation.md)和输出文件。保留partial、抑制、特征错误和未映射记录。
4. 把review_source交接chain-evidence的evidence_paths，再按任务进入mechanism-target-graph及mechanism-constraint-analysis。已有基线的补采交给evidence-reintegration，不能重建首轮清除索引。

实例配合关联不证明运动副、接触、真实自由度或有限运动。空配合仍未知；不套模板、不请求人工复核。
