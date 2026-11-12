---
name: component-faces
description: 从 SolidWorks 单个已解析零件实例读取有限面目录、平面/圆柱参数、面积、UV 范围、面朝向和持久引用。用于“读取具体面”“准备面间隙探测”；只读零件定义，不测面间距、不确认接触。
---

# 组件面目录

输入：活动装配 token、完整叶零件实例路径和读取预算。输出：sw_component_faces 原始 envelope。

1. 调用 sw_component_faces；先选少量实例，保留完整返回到 outputs 新文件，不自动解析、切配置或选择面。
2. 保留每个面记录及其错误、complete/truncated；索引只在该源文件内定位，后续必须解析持久引用。
3. 平面/圆柱参数属于零件定义；UV 范围不是裁剪轮廓。记录装配级切除未参与，不能将目录当成全装配几何。
4. 需要测点间隙时只交接文件、实例和面记录给 face-gap-probing；本流程不强制测量。

参数、字段或失败不清楚时读 [面目录细节](references/details.md)。实机验收按 docs/MCP_ACCEPTANCE.md 的 0.11.0 章节，不预加载其他 skill。
