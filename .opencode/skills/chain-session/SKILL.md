---
name: chain-session
description: 在当前SolidWorks装配中首次跑通一条显式组件链，串联有界批量采集、基线建立、约束补采与瞬时求解，并生成耗时报告。用于尚无该链历史的首次联调；已有结果或中断任务交接原有执行、回填和分析能力。
---

# 首次机构链联调

输入：已打开装配的当前token、2–20个准确叶实例路径、参考实例、数值尺度及公差。输出：新session报告和原始采集/分析文件。实现位于工具模块，入口不包含程序。

1. 先查看已有任务上下文。若已有这条链的check/index/receipt，按[续跑与失败](references/handoff.md)交接，保留历史，不重新初始化。
2. 尚未打开模型时交接solidworks-start和solidworks-document。只在需要确定范围时读取assembly-inventory；选择一条小范围候选链，记录选择依据，名称不证明链已经识别。参考实例仅用于相对坐标，不等于接地。
3. 读取[配置与调用](references/run.md)，用当前token与实际实例生成配置，运行一次`python -m cadkin chain-session`。不手填不存在的路径、复制旧token或硬编码“三独立”对应三个关节。
4. 先读紧凑返回的workflow_complete、stop_reason、solution_summary及handoffs。通过chain-baseline建立首次来源；后续采用原批量执行与回填，最多两轮，不修改原STEP、不加载模板、不移动零件。
5. 需要解释慢在哪时读取报告的performance和cad_capture_tool_timings；需要机械解释时交接mechanism-chain-motion。不把重复嵌套计时相加，不把合成时间当实机提速。
6. 结论区分流程完成、支持的瞬时约束、真实运动验证。无配合或缺证据保留未知；不要求人工复核，也不反复采集。
