---
name: face-boundary
description: 读取指定圆柱有限面的解析边界线与圆弧，保留来源身份、预算及错误。用于轴向范围缺失且已有面目录的任务；只采集单个面的边界，不判断配合或运动类型。
---

# 有限面边界读取

输入：当前文档token、原始面目录中的准确选择；输出：原始边界envelope。

1. 使用face_inventory_path、body_index、face_index选择圆柱面；索引只定位该文件，不是跨次CAD ID。调用参数见[采集](references/capture.md)。
2. 有finite报告与check/index时交evidence-task-plan生成有保护的批次计划，沿用最新历史。只读边界不能绕过既有四轮或失败记录。
3. 调用sw_read_face_boundary后保留完整envelope和错误。partial、unsupported或截断都不能当完整范围；几何/位姿变化停止依赖工作。
4. guard通过后交独立索引，再交finite-connection-analysis；不将边界文件直接当几何报告或原生约束。

不读取全装配包围盒，不重建/移动/保存CAD；不设置人工复核。
