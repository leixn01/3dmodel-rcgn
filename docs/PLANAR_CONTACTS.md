# 0.31.0 有限端面接触候选

本轮从0.30真实邻接端面继续，读取闭合有限区域，计算投影重叠及定向间隙。孔区会从面积中扣除；圆弧不作为整圆。仍不证明物理接触、轴向保持、行程或已确认运动副。

| 能力 | 工具 | 输出 |
| --- | --- | --- |
| 读取一个真实邻面 | sw_read_planar_face | 原始loops、完整/部分状态、可解析region |
| 离线比较区域 | cad_analyze_planar_contacts | 投影面积、定向间隙、条件闭合方向、来源/缺口 |
| 定向补采 | cad_plan_evidence_tasks + planar_analysis_path | v9计划，复用原批次/索引/四轮历史 |

## 支持范围

- 一个完整圆盘，或一个外圆+一个同心圆孔；通过GetCurveParams3验证完整周期、首尾闭合，不只读取CircleParams。
- 一个无孔凸直边多边形；重建环顺序，不假设返回顺序或方向正确。
- 环数量、边数量、平面位置、闭合和面积均核对；区域面积与GetArea比较。闭合/平面容差1e-8m，面积容差max(1e-12m²,区域面积×1e-6)，不是接触公差。
- 圆类对使用圆交面积的容斥公式，凸多边形对裁剪。混合类型、非平行面、偏心/多孔、分段圆弧、复杂曲线、凹多边形等保留未知或partial；不填孔，不用显示网格或AABB估精确区域。

## 使用

在已有Conda更新安装后重启OpenCode。沿用原engagement/check/latest index：分析→v9规划→batch→同check索引→原engagement+新index重算→停止。

两个实例、四个端面通常是4次读取和6次保护，可由一次batch请求完成。每面读取一次，失败/partial同样留档，不扩预算重试。与所有之前分支共享四轮；已耗尽则报告剩余未知，不能新建链或会话归零。CLI支持`plan-evidence CHECK --planar-analysis REPORT --output NEW_PLAN`。

新分析和计划只在同一次调用内复用已验证的精确索引、核对原字节，减少重复来源重放；不跨调用缓存可变证据、不省略哈希/路径核验。采集只针对已绑定邻面，无整装配扫描。

## 结果怎么理解

`projected_overlap_area_mm2`是有限区域投影交面积。`no_resolved_positive_area`不代表绝无边/点接触；正面积也不代表当前真实接触。`signed_plane_gap_mm`以左面定向法向为正。相向且在原距离容差内输出`opposed_regions_near_tolerance`；负的定向间隙另列，不能直接称全模型穿透。

`hypothetical_closing_direction_right_wrt_left`仅表示固定左实例时右实例减小间隙的假设平移方向，不是速度约束或允许运动。保持target_joint_kind=unknown、DOF/行程null，contact_confirmed/retention_confirmed=false。放置后的零件定义不包含装配级特征，快照非原子，旧来源错误/遗漏/竞争解释保留。

## 验证与下一步

`python scripts/verify_planar_contacts.py --output outputs/verify-planar-contacts-0.31`，重跑换新目录。覆盖圆盘、圆环、小圆落孔区、多边形、圆弧反例和API失败，使用显式合成CAD；真实SDK/stdio测试不等于SolidWorks实机通过。实机准确参数及记录见[MCP验收](MCP_ACCEPTANCE.md#0310有限端面区域与方向)。

下一步设计受控小步运动验证、原始位姿恢复和前后干涉检查，用实际响应检验静态候选。当前版本尚不移动组件或执行拆卸。

接近相切的微小交面积还需超过resolved_area_threshold_mm2；geometry_area_margin_mm2计入闭合公差与周长的裕量，不只看浮点消去误差。这是条件几何判读裕量，不是严格区间算术误差证明或物理接触公差。
