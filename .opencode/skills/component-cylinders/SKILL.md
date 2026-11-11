---
name: component-cylinders
description: 从 SolidWorks 指定零件实例读取解析圆柱面的轴线和半径，给组件分组、轴类或孔类零件分析提供几何候选。用于“找圆柱轴线”“读取轴孔半径”“没有配合时补几何证据”；不认定运动副、孔轴配合、导程或行程。
---

# 圆柱轴线证据

输入：一个已解析零件实例及匹配配置。输出：零件定义圆柱面的根坐标轴线/半径。

1. 调用 sw_component_cylinders，需要后续面身份核对时设 include_face_references=true，保存原始 JSON；不自动解析、打开零件或切换配置。
2. 检查 complete/truncated/errors，保留 body/face 快照索引和原始参数，不从摘要重写数值。
3. 零件定义不含装配级切除；轴向正负等价、轴点不是端点，不判孔轴、行程或运动副。关系分析另交付该文件。

仅在不确定参数、字段含义或遇到失败时读取 [细节与分支](references/details.md) 的对应段落；常规调用按 MCP Schema，不预加载参考文件或其他 skill。引用其他能力时只交接所需输入/输出。
