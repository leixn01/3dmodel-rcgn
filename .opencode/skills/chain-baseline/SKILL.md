---
name: chain-baseline
description: 将空证据机构链的首次有界采集记录离线转为关系基线、目标图、草案、检查、观测索引与约束报告。用于已有首轮完整receipt但尚无关系来源的初始化；不同于后续回填、在线采集和运动求解。
---

# 首次证据基线

输入：空证据链的原始完整execution receipt及全部来源，显式毫米/角度公差。输出：新baseline报告和可交接的check/index/constraints等路径；不调用SolidWorks。

1. 确认是首次空证据链、2–20个叶实例。已有关系来源或索引历史时交给evidence-reintegration，不重新初始化。
2. 按[调用和结果](references/create.md)调用cad_create_chain_baseline。工具自行重放计划、原始返回和保护，不信任手改的通过标记。
3. 先看baseline_created和pipeline_error。成功后把outputs中的check、index、constraints一起交接evidence-task-plan或mechanism-chain-motion；求解还需原链内参考实例和数值特征长度。
4. 保留失败/partial尝试、完整空扫描和原公差。数据不够时保留缺口，不填空配合/圆柱，也不请求人工确认。
