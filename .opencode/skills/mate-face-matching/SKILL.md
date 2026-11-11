---
name: mate-face-matching
description: 在 SolidWorks 中核对根配合引用面是否对应已有圆柱候选面，保存实时对象身份与来源证据。用于“配合是不是作用在这个面”“把配合关联细化到具体圆柱面”；只采集面对应，不生成关系候选或离线复核清单。
---

# 配合面身份核对

输入：当前装配 token、完整空间清单、带持久面引用的圆柱原始文件。输出：sw_match_mate_faces 原始 envelope。

1. 检查输入是否齐全；旧圆柱文件没有 face_references_requested=true 时，只交由圆柱采集能力补取，随后关系候选也需重算。不要手写 ID、哈希或面索引。
2. 保持文档/配置/位姿/几何不变，调用 sw_match_mate_faces 并保存到 outputs 新文件；先选少量实例，保留范围、预算与错误。
3. 只将返回的 matches 解释为对应源文件内的面身份核对；空匹配、非面引用、范围外或失败均不能推断无连接。配合状态与面身份分开解释，不确认运动副。
4. 需要连接复核时仅交付本 envelope 和对应源文件给离线复核能力；不在这里重写配对算法。

准备调用或解释具体字段时读 [参数与证据](references/evidence.md)；发生失败、截断或上下文变化时读 [失败分支](references/failures.md)。不要预加载其他 skill；验收才读 docs/MCP_ACCEPTANCE.md 的 0.9.0 部分。
