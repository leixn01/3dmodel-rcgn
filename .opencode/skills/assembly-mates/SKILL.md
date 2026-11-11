---
name: assembly-mates
description: 读取活动根装配的配合特征清单、抑制/回滚/特征报错状态及经身份核对的引用实例。用于“配合是否被抑制”“读取整机当前层配合”“给连接复核提供配合状态”；不读取子装配内部配合、不分析运动副。
---

# 根装配配合清单

输入：活动装配 token。输出：sw_mate_inventory 的原始 envelope；后续分析只交付文件。

1. 已有有效 token 时直接调用 sw_mate_inventory；缺少时仅查询活动文档，确认 assembly。采集期间保持模型不变，不启动额外会话、不切换配置。
2. 保存真实返回到 outputs 新 JSON，检查 scope、complete、truncated、errors。范围仅为活动根装配的配合，引用到嵌套组件不表示已读其内部配合。
3. 报告抑制/回滚/特征报错/未知状态；无特征报错不证明求解成功、有效约束或机械连接。原始实体参数不转换成运动轴。
4. 本流程只采集状态。需要与已有几何候选关联时，交付该文件给 connection-review，不在此处重做几何分析。

按需读取：

- 解释 activity、根坐标或引用映射时读 [字段与范围](references/fields.md)。
- 首次调参、partial 或错误时读 [预算与失败分支](references/failures.md)。

常规任务不预加载两个参考文件，不加载完整开发/验收文档；验收任务才读仓库 docs/MCP_ACCEPTANCE.md 的 0.8.0 部分。
