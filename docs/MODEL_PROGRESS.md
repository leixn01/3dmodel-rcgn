# 测试模型拆解进度

当前版本：0.17.0。对象：`examples/three_servo_lift/3X Lift Assembly.STEP`（三独立伺服升降机）。

**项目处在“读取结构、生成角色与连接候选、补充具体面的几何证据并整理链级清单；已增加目标图、参考局部匹配、多零件刚体候选、关节草案、冲突检查、补采执行、兼容证据回填与比较能力”阶段。已有条件刚体分组，但尚未确认刚体/运动副，未生成拆卸顺序或移动零件验证路径。** 软件能力的完成与这台模型的实际验收分开记录；不能把测试替身结果称为升降机的拆解结果。

## 模型实际做到哪一步

| 阶段 | 模型实测状态 | 对应工具/命令 |
| --- | --- | --- |
| 输入与打开 | STEP 已随仓库保存，用户确认可打开并导入为装配；原始文件保持不变 | `sw_open_document`；独立 STEP 体检 CLI |
| 装配结构与基础操作 | 用户实测组件树、当前文档、选择、标准视图等 API 可用；旧报告记录254个组件，未作为本版本重新测得的数量 | `sw_session_status`、`sw_active_document`、`sw_component_tree`、`sw_select_component`、`sw_clear_selection`、`sw_set_view`、`sw_zoom_to_fit`、`sw_rebuild` |
| 实例空间与显示 | 单实例空间/可见性读取通过；旧全量空间读取和显隐设置存在超时，后来已修改实现，仍需实机复测 | `sw_component_spatial`、`sw_spatial_inventory`、`sw_get_component_visibility`、`sw_set_component_visibility`；`spatial-export` 收齐分页 |
| 角色分组 | 工具已开发；尚未取得该升降机可重放的完整分组 JSON | `cad_group_components` |
| 轴线与配合关系 | 工具已开发；尚未取得该模型可核对的配合/圆柱/具体面关联结果，无配合时不能推断无连接 | `sw_component_constraints`、`sw_component_cylinders`、`cad_component_relations`、`sw_mate_inventory`、`sw_match_mate_faces`、`cad_review_connections` |
| 组件接近程度 | 0.10.0 已开发；该升降机真实距离/耗时待验收 | `cad_proximity_candidates`、`sw_component_distance`、`cad_review_proximity` |
| 具体面间隙与法向 | 0.11.0 新增；该模型面身份/测点/法向待实机核对，范围为放置后的零件定义 | `sw_component_faces`、`sw_probe_face_pair`、`cad_review_face_contacts` |
| 单条升降链的连接清单 | 已具备离线汇总；尚无这台模型完整真实链级结果，默认不等待人工确认 | `cad_build_chain_evidence` |
| 参考模板 | 0.13.0已解析8个真实资产结构摘录；其中2个无关节。尚未自动匹配到本STEP | `cad_list_mechanism_templates`、`cad_extract_mechanism_template`、`cad_compare_mechanism_graphs` |
| 目标图与局部模板匹配 | 0.14.0已具备来源重放和候选搜索；尚无本升降机实机目标图/匹配结果 | `cad_build_target_graph`、`cad_match_mechanism_templates` |
| 刚体候选与关节草案 | 0.15.0已具备来源重放、多方案分组和目标轴线草案；尚无本升降机真实输出 | `cad_build_rigid_candidates`、`cad_draft_joints` |
| 草案检查与补采规划 | 0.16.0已具备来源重放、冲突/竞争/覆盖区分及有预算的只读任务；尚无本模型真实结果，计划未执行 | `cad_check_joint_draft`、`cad_plan_evidence_tasks` |
| 只读补采执行与证据回填 | 0.17.0已接通一轮有界执行、兼容回填和比较；该升降机尚无真实运行结果 | `sw_execute_evidence_task`、`cad_reintegrate_evidence`、`cad_compare_draft_checks` |
| 机械拆卸与运动校核 | 未开发、未完成 | 已验证刚体/运动副、零件移动、拆卸顺序与碰撞路径工具尚无 |

这里的“分组”是角色候选，并不是已确认一起运动的刚体。“近接触”是需要复核的局部证据，不是已确认机械连接。样例名称“三独立”不用于硬编码三个关节。

## 用户确实使用过哪些工具

现有实机依据为用户提供的旧版15工具报告（SolidWorks 2025）。未提供该次提交 SHA、完整原始 JSON 和逐项截图，所以仅沿用报告口径：

- **11项 API 通过**：sw_session_status、sw_open_document、sw_active_document、sw_component_tree、sw_set_view、sw_select_component、sw_clear_selection、sw_rebuild、sw_zoom_to_fit、sw_get_component_visibility、sw_component_spatial。
- **2项部分通过**：sw_set_component_visibility（实际生效但超时）、sw_spatial_inventory（小范围正确、全量超时）。
- **2项失败**：sw_get_display_state、sw_set_display_visibility（旧显示常量加载问题）。

自动启动 sw_start_application 已开发，仍待实机验收。上述显示/分页/超时问题的后续修复也不能仅凭 CI 通过改写为用户验收通过。

其余工具的现有成功记录主要是单元测试、离线演示数据、真实 MCP 协议配测试后端及 Windows Conda CI；本次开发环境没有连接到用户另一台电脑的 SolidWorks。真实使用记录只在收到对应原始文件和核对结论后更新。

## 下一次应形成的模型结果

现在可以把本机真实target graph生成多个刚体候选方案，再在各方案下匹配参考局部结构，得到“参考刚体 → 一个或多个目标实例”、组间关节类型/DOF假设、目标圆柱方向/无限轴线候选、未知行程/枢轴与竞争解释。每个方案保留全部原始实例，不合并基线始终存在。默认不等待人工确认。

该升降机的实际拆解进度仍以本机原始文件为准。本轮开发环境没有连接用户SolidWorks；本轮回归及30项新增验收使用显式测试替身，不能称已识别三条升降链或已完成刚体合并。

现在可继续检查草案，生成具体工具参数、依赖和前后文档/位姿校验任务，复用已有完整证据，保留未解决项。规划工具只落盘；现可交接独立执行器，逐步采集并验证上下文，再回填兼容证据及比较草案。面目录/单实例约束仍作为补充上下文。

下一步扩展补充观测关联与复用，并在本机形成一条真实升降链的完整记录。不能把条目消失称为机械问题解决。运动/干涉、行程与耦合、拆卸路径仍在之后开发。
