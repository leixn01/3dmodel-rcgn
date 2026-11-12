# 测试模型拆解进度

当前版本：0.11.0。对象：`examples/three_servo_lift/3X Lift Assembly.STEP`（三独立伺服升降机）。

**项目处在“读取结构、生成角色与连接候选、补充具体面的几何证据”阶段。尚未实现自动刚体合并、运动副确认、拆卸顺序生成或移动零件验证路径。** 软件能力的完成与这台模型的实际验收分开记录；不能把测试替身结果称为升降机的拆解结果。

## 模型实际做到哪一步

| 阶段 | 模型实测状态 | 对应工具/命令 |
| --- | --- | --- |
| 输入与打开 | STEP 已随仓库保存，用户确认可打开并导入为装配；原始文件保持不变 | `sw_open_document`；独立 STEP 体检 CLI |
| 装配结构与基础操作 | 用户实测组件树、当前文档、选择、标准视图等 API 可用；旧报告记录254个组件，未作为本版本重新测得的数量 | `sw_session_status`、`sw_active_document`、`sw_component_tree`、`sw_select_component`、`sw_clear_selection`、`sw_set_view`、`sw_zoom_to_fit`、`sw_rebuild` |
| 实例空间与显示 | 单实例空间/可见性读取通过；旧全量空间读取和显隐设置存在超时，后来已修改实现，仍需实机复测 | `sw_component_spatial`、`sw_spatial_inventory`、`sw_get_component_visibility`、`sw_set_component_visibility`；`spatial-export` 收齐分页 |
| 角色分组 | 工具已开发；尚未取得该升降机经人工确认的完整分组 JSON | `cad_group_components` |
| 轴线与配合关系 | 工具已开发；尚未取得该模型可核对的配合/圆柱/具体面关联结果，无配合时不能推断无连接 | `sw_component_constraints`、`sw_component_cylinders`、`cad_component_relations`、`sw_mate_inventory`、`sw_match_mate_faces`、`cad_review_connections` |
| 组件接近程度 | 0.10.0 已开发；该升降机真实距离/耗时待验收 | `cad_proximity_candidates`、`sw_component_distance`、`cad_review_proximity` |
| 具体面间隙与法向 | 0.11.0 新增；该模型面身份/测点/法向待实机核对，范围为放置后的零件定义 | `sw_component_faces`、`sw_probe_face_pair`、`cad_review_face_contacts` |
| 机械拆卸与运动校核 | 未开发、未完成 | 刚体合并、运动副确认、零件移动、拆卸顺序与碰撞路径工具尚无 |

这里的“分组”是角色候选，并不是已确认一起运动的刚体。“近接触”是需要复核的局部证据，不是已确认机械连接。样例名称“三独立”不用于硬编码三个关节。

## 用户确实使用过哪些工具

现有实机依据为用户提供的旧版15工具报告（SolidWorks 2025）。未提供该次提交 SHA、完整原始 JSON 和逐项截图，所以仅沿用报告口径：

- **11项 API 通过**：sw_session_status、sw_open_document、sw_active_document、sw_component_tree、sw_set_view、sw_select_component、sw_clear_selection、sw_rebuild、sw_zoom_to_fit、sw_get_component_visibility、sw_component_spatial。
- **2项部分通过**：sw_set_component_visibility（实际生效但超时）、sw_spatial_inventory（小范围正确、全量超时）。
- **2项失败**：sw_get_display_state、sw_set_display_visibility（旧显示常量加载问题）。

自动启动 sw_start_application 已开发，仍待实机验收。上述显示/分页/超时问题的后续修复也不能仅凭 CI 通过改写为用户验收通过。

其余工具的现有成功记录主要是单元测试、离线演示数据、真实 MCP 协议配测试后端及 Windows Conda CI；本次开发环境没有连接到用户另一台电脑的 SolidWorks。真实使用记录只在收到对应原始文件和核对结论后更新。

## 下一次应形成的模型结果

先选一条升降链和2–5个相关零件，保存完整空间基准、角色候选及人工修正；对少量邻近实例获取组件距离，再读取一对具体面并保存局部测点/法向。把结果整理成“零件A—零件B、可能关系、依据、缺失项、人工结论”的连接清单。

按 [0.11.0 验收](MCP_ACCEPTANCE.md#0110具体面间隙与法向) 记录真实参数、原始返回、耗时和窗口核对，保存到 outputs 新目录；不把其他用户工程或这些输出提交到公共仓库。拿到足够的人工确认连接后，再推进刚体、运动副与拆卸路径。
