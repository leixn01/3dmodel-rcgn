---
name: connection-review
description: 将已有同轴/平行几何候选与活动根装配配合记录关联，生成按实例对组织的连接证据复核清单。用于“哪些候选有配合支持”“区分被抑制的连接证据”；只做离线关联，不采集 CAD 或确认运动副。
---

# 连接证据复核

输入：cad_component_relations 结果文件、sw_mate_inventory 原始 envelope，以及它们引用的原始文件。输出：新的连接复核 JSON。

1. 输入已齐时直接调用 cad_review_connections，传 relations_path、mate_inventory_path、output_path（outputs 内新文件）。不为离线任务启动 SolidWorks 或重跑其他 skill。
2. 缺少输入时只请求对应能力交付文件；来源不匹配时重新核对来源，不改写数据绕过。工具按源哈希、文档/配置及实例位姿校验。
3. 读取结果文件，按完整实例对报告 review_state、几何候选索引、配合 feature_id、状态和未知项；partial 保持部分，范围不能扩大为整机所有机械连接。
4. 保持 requires_review=true、mechanical_relation_confirmed=false。当前关联到实例对，配合可能引用不同的面；不能把“有未抑制配合”直接称为几何已匹配或运动副已确认。

仅需解释状态、溯源或处理失败时读 [判读与失败分支](references/interpretation.md)。常规调用不加载原始 COM 文档或其他 skill；实机验收才读仓库 docs/MCP_ACCEPTANCE.md 的 0.8.0 部分。
