---
name: proximity-review
description: 将已有邻近测量清单与组件距离原始文件离线复核，区分近接触候选、已测间隔、读取失败和未测。用于“整理无配合模型的近接触证据”；不连接 CAD，不与圆柱面对应或运动副确认混为一谈。
---

# 距离候选复核

输入：proximity 工作清单、其空间源文件、每对一个原始距离 envelope 和明确阈值。输出：新的近接触候选复核 JSON。

1. 输入齐全时直接调用 cad_review_proximity；显式传 contact_tolerance_mm，输出选 outputs 新文件。离线任务不启动 SolidWorks。
2. 来源不匹配时核对后重采/重算，不能改 token、位姿、哈希或距离绕过；缺失测量保留 unmeasured，不自动补零。
3. 按完整实例对报告 review_state、距离/最近点、来源与错误；partial 保持部分，未筛入/未测范围仍未知。
4. 保持 requires_review=true、contact_confirmed=false、mechanical_relation_confirmed=false。组件最小距离不能证明某一对圆柱面接触，也不自动修改之前的配合复核结论。

解释分类、预算或失败时读 [判读与来源](references/details.md)；只缺哪个文件才交付对应能力，不强制加载完整采集链。
