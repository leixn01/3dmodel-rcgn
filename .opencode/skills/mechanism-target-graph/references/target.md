# 图适配说明

cad_build_target_graph必填chain_path、output_path；可选relation_paths（最多20个项目内原始cad_component_relations结果）。输入chain_dossier_schema_version=1，不接受人工review结果或手工候选表。工具重算链及来源，连接文件绑定的圆柱关系自动收集。补充独立关系文件也必须绑定相同完整空间清单、配置和位姿。所有来源合计最多256文件/128MiB。

输出target_graph_schema_version=1，保留2–50个选定叶实例、全部实例对、来源哈希和范围外联系。节点记录实例路径、父级、配置、米制根坐标/列矩阵及近似盒；缺几何留空，重复文件的实例不合并，抑制/未解析节点不参与匹配。角色和名称仅作上下文。

pair包含signals、最多32条axis_relations、flags和link_support。默认权重为：可用根配合1、近局部面点0.65、近组件0.55、同轴0.3、平行0.2；取最大值，不累计重复观测。存在冲突、配合记录错误或多个轴分类公差时减半。权重只用于排序，不证明接触/连接或关节类型。

几何单位统一米、角度为度。轴向去重按无向角1e-6度；只有唯一轴向且未截断时提供representative_axis_unit，它仍是圆柱几何方向。分割面不算多个关节；多个方向不挑最有利的一条。大间隙/没有观测不视为无机械连接。

INVALID_TARGET_SOURCE：检查是否原始链清单；EVIDENCE_MISMATCH：来源或派生字段改变，重新生成受影响阶段，不只改哈希。缺失原始文件则报告数据缺口并继续独立任务。OUTPUT_EXISTS换新文件；TARGET_AXIS_LIMIT保留partial，不等用户确认。

CLI：`python -m cadkin target-graph outputs/chain.json --output outputs/target.json`。有额外关系时加`--relations outputs/relations.json`。比较/匹配读取raw输出文件，不读MCP envelope。
