# 项目约定

## 环境与范围

- 正式仓库 `leixn01/3dmodel-rcgn`，直接维护仓库。用户在另一台已安装 SolidWorks 的 Windows 电脑使用 OpenCode；先确认实际执行位置。用户使用本地已有 Conda 环境；MCP 和 CLI 用激活环境的 python，不新建 .venv、不硬编码其环境名。后续只面向 Windows，不维护 Ubuntu 适配或 CI；保留错误平台的明确报错。
- 先读 README。当前已有 MCP 0.31.0（59 个工具）；用户 SolidWorks 2025 实测旧版 15 工具：11 项 API 通过、显示工具 2 项失败、组件显隐/全量空间读取 2 项部分通过。先按 0.5.0 清单复测修复，再核对分组；自动启动仍待实机验证；不重新搭建已有功能，不把远期路线图一次性实现。
- 可直接打开的模型已在 `examples/three_servo_lift/3X Lift Assembly.STEP`，不要再要求用户解压；原始输入保持不变，需修改的工作副本和结果放 `outputs/`。

## 功能与分层

| 任务 | Skill |
| --- | --- |
| STEP/ZIP 体检 | `cad-intake` |
| 软件启动与启动完成检查 | `solidworks-start` |
| 会话与活动文档检查 | `solidworks-connect` |
| 组件实例树 | `assembly-inventory` |
| 实例位置、变换与近似包围盒 | `component-spatial` |
| 叶实例角色候选与自动证据核对 | `component-grouping` |
| 固定标志与关联配合证据 | `component-constraints` |
| 零件定义圆柱面轴线/半径候选 | `component-cylinders` |
| 离线同轴/平行候选与来源关联 | `component-relations` |
| 根装配配合状态/坐标/引用身份 | `assembly-mates` |
| 配合引用面到候选圆柱面的在线身份核对 | `mate-face-matching` |
| 无圆柱依赖的原生根配合关联 | `root-mate-review` |
| 几何候选与配合的离线关联 | `connection-review` |
| 近似包围盒待测组件对 | `component-proximity` |
| 两个零件实例的最小距离/最近点 | `component-distance` |
| 距离文件的离线近接触候选复核 | `proximity-review` |
| 单实例有限面目录/持久引用 | `component-faces` |
| 指定面局部间隙/法向探测 | `face-gap-probing` |
| 面探测文件的离线候选复核 | `face-contact-review` |
| 指定机构链的离线证据清单 | `chain-evidence` |
| 首次有界单链联调入口 | `chain-session` |
| 首轮采集到关系基线/索引 | `chain-baseline` |
| 机构参考目录检索 | `mechanism-template-search` |
| USD参考刚体/关节图提取 | `mechanism-template-extract` |
| 已有对应关系下的图结构评分 | `mechanism-template-compare` |
| 来源重放与目标实例图 | `mechanism-target-graph` |
| 参考局部子图匹配与候选解释 | `mechanism-template-match` |
| 多零件刚体候选分组 | `mechanism-rigid-groups` |
| 指定圆柱面的解析边界读取 | `face-boundary` |
| 圆柱面点成员关系与定向法向 | `cylinder-face-sampling` |
| 真实同体边邻接 | `face-adjacency` |
| 表面内外侧/邻接补证 | `surface-engagement-analysis` |
| 邻接端面有限闭合区域 | `planar-face-region` |
| 有限投影面积与方向候选 | `planar-contact-analysis` |
| 有限轴向范围及局部端面方向证据 | `finite-connection-analysis` |
| 无配合几何连接的竞争解释 | `geometric-connection-analysis` |
| 目标局部配合约束组合分析 | `mechanism-constraint-analysis` |
| 两实例局部瞬时约束秩与运动方向 | `mechanism-local-motion` |
| 单链多组件瞬时约束与闭环限制 | `mechanism-chain-motion` |
| 目标关系草案与可选模板类比 | `mechanism-joint-draft` |
| 草案结构/证据一致性检查 | `joint-draft-check` |
| 最近点引导的面候选与有限面探测规划 | `face-probe-plan` |
| 有预算的只读补采任务规划 | `evidence-task-plan` |
| 单步只读补采执行与原始记录 | `evidence-task-execute` |
| 兼容补采来源回填与重算 | `evidence-reintegration` |
| 前后候选/发现与覆盖比较 | `joint-draft-compare` |
| 补采观测与组件/候选关联及复用索引 | `evidence-observation-index` |
| 打开/导入或重建文档 | `solidworks-document` |
| 标准视图/缩放 | `solidworks-view` |
| 基准面等辅助对象显隐 | `solidworks-display` |
| 装配组件显隐 | `component-visibility` |
| 选择/清空组件选择 | `component-selection` |

Skill 使用 `.opencode/skills/<名称>/SKILL.md`，只保留流程；工具放 `cadkin/tools/`，COM 与 STA 放 `cadkin/adapters/`，MCP 在 `cadkin/mcp_server.py`。不把程序塞入 skill，不在 CLI/MCP 各写一套业务逻辑。精确参数见 `docs/TOOL_CONTRACTS.md` 与工具 Schema。

## 执行和数据

- 用户已要求开发连接与操作能力。当前工具可按任务打开模型、调整视图、控制辅助对象/组件显隐、选择组件或重建；只读检查请求不顺带执行这些动作。用户已授权任务所需的软件自动启动：打开模型任务发现未运行时，通过独立 `sw_start_application` 启动，无需用户手动提前打开；纯状态查询仍不启动。已有进程优先复用，连接失败不通过新建实例绕过，不关闭用户文档或保存覆盖。
- 操作前读取并使用当前文档 token；执行期间逐个调用工具。超时不表示操作取消，先核对 SolidWorks 状态再重启 MCP，不盲目重试。
- 保留组件实例/父子关系及错误；不得把部分结果或 API 失败写成完整空列表。STEP 文本 PRODUCT/NAUO 数量不是展开后的实例数。
- STEP 可在 SolidWorks 打开；实际导入类型与 Mate 是否保留需核对。未知运动参数不补造。
- 只提交指定样例及其校验来源；用户其他工程、outputs、账号凭据和密钥不提交。
- 完整测试：先安装 `.[solidworks,templates]`，再运行 `python -m unittest discover -s tests -v`。基础体检可单独运行 `python -m unittest discover -s tests -p test_intake.py -v`。
- 明确区分测试替身、真实 stdio 协议、真实 COM 与人工窗口核对；未实测不能记为通过。
- 每次新增或改变功能，都在 `docs/MCP_ACCEPTANCE.md` 追加对应版本的验收项：前置条件、准确工具与参数、预期返回、窗口/数据核对、失败标准和证据保存位置。完成回复必须给出更新方式和本次验收入口，不能只说“测试通过”。
- 空间数据用列向量，矩阵平移为米；Transform2 已相对根装配，不重复乘父级。原点不等于质心，包围盒为近似轴对齐边界，不能用于精密测量或直接认定碰撞。
- 保留第三方许可与固定来源，变更后同步 `MANIFEST.json`，排除清单自身与忽略的输出。

- 空间清单采用分页，完整文件用 `spatial-export` 采集；单页不能传作完整分组输入。分组工具 `cad_group_components` 只读项目内 JSON、写 outputs 新文件，不连接 COM。名称规则和近邻只是候选证据；自动补充证据或保留未知，不等待人工复核；不将推断写成human_confirmed。

- 0.6.0 配合与圆柱读取只读指定实例：IsFixed 对嵌套组件不能直接解释；MateEntity 参数保留所属装配坐标，引用名称不自动当根路径；零件定义圆柱不包含装配级切除，不凭轴线认定运动副。配置不匹配时不自动切换。

- 0.7.0 关系工具 cad_component_relations 只比较提供的实例圆柱证据；显式传毫米/度公差，绑定空间清单与可选分组哈希。分割面证据条数不是机械连接数；同轴/平行、角色确认都不证明运动副，部分来源和预算截断必须保留。

- Skill 必须解耦、逐层披露：description 只说明职责与触发；SKILL.md 保留输入/输出、最小流程与关键边界；详细参数/字段/失败分支放同目录 references，入口写明何时读取。不要预加载全部参考文件、全套 skill 或完整开发文档。跨功能只交接数据，缺什么才调用对应能力；工具不读取 skill，不把执行代码放入 skill。
- 0.8.0 sw_mate_inventory 只取活动根装配 MateGroup 的特征状态与原始实体参数，不含子装配内部配合。普通根配合文件输入的 cad_review_connections 只做实例对关联；未抑制且无特征报错不是求解成功或运动副确认，不把配合引用面当作已匹配候选圆柱面。

- 0.9.0 面身份核对独立于几何候选：sw_component_cylinders 可选 include_face_references=true；sw_match_mate_faces 用持久 ID 解析→实例映射→IsSame 核对。body/face 索引仅定位哈希源文件，不能跨次当 CAD ID。cad_review_connections 只有获得两端准确面的来源绑定证据才提升为 candidate_face_pair；面身份、配合状态、求解/运动关系分别保存。旧圆柱重新采集后需重算关系文件。

- 0.10.0 邻近候选、单对距离、离线复核分别独立。近似 GetBox 只安排测量，未列出/缺失/截断仍未知；sw_component_distance 用根文档 ClosestDistance 接收两个已解析零件实例，拒绝子装配聚合和在位编辑。米制原始值与毫米显示值分开，最近点不再变换。小/零距离不能区分接触、穿透、包含，也不指向某一对圆柱面；不得据此确认接触、刚体或运动副。每次只测一对，保留 API 失败与原始 envelope。

- 0.11.0 面目录、局部面探测、离线面候选复核各自独立。用原始面目录哈希+索引定位记录，再解析持久引用；只探测不同实例上的解析平面/圆柱。GetClosestPointOn 必须调用有限面接口，坐标在零件定义与根装配之间只转换一次；FaceInSurfaceSense=true 要翻转底层法向。converged 或小测点间隙不证明全局最小值/接触；大测点间隙也不证明整面分离。保留种子/预算/错误及装配级切除未参与的范围，不能直接确认刚体、运动副或拆卸路径。

- 0.12.0 机构链范围必须显式列出2–50个叶实例；链名不证明自动识别。离线汇总重算来源，保留全部实例对、未知、边界联系和几何范围。旧人工复核工具仅保留文件兼容，不属于自动拆解流程；禁止伪造用户确认或把它设为继续工作的条件。

- 0.13.0 自动拆解不设置人工复核节点。Agent自行调度已有采集/计算能力，有不确定信息时继续处理可独立完成的部分，并在结论列出依据、替代解释、未知和风险。历史requires_review/review_flags表示证据待自动核对，不能解释成必须向用户提问；模型/来源错误仍应明确报告，不能悄悄变成成功。新增输出明确requires_human_review=false。
- 模板数据在cadkin/resources/mechanisms；确定性解析/评分在cadkin/templates；项目文件/MCP边界在tools/templates。工具不读取skill。参考模板不是目标CAD真值；标签只帮助检索，缺少关节不补造。heldout不参与默认检索，若查看或用于调参不能宣称未见评测。
- 0.14.0 已实现目标实例图与局部模板搜索。实例图必须重放原始链清单及来源；匹配前再重放目标图，不能直接读手写高分特征。保留全部实例对、轴线、配合、近距离/面候选、冲突和边界联系。一个目标节点仍是一个叶实例，不等于已合并刚体。
- 匹配为选定模板窗口的有预算搜索：默认3节点、6个reference，世界端点不映射；重复/同分解释、状态与beam截断必须说明。默认不使用heldout。分数是公开权重的排序值，不是概率；关节类型只是假设，目标轴位置/限位仍未知。不能把参考派生观测控制、模拟CAD、真实协议测试当作升降机实测或识别率。
- 0.15.0 已增加cad_build_rigid_candidates与cad_draft_joints，算法在cadkin/rigid，文件重放在tools/rigid，skill独立。保留不合并基线；只有干净有效lock可生成连通组，近接触仅作单桥弱候选，普通配合/同轴/名称不证明刚体。每方案实例成员守恒，flags/运动类配合/大小上限不能被吞掉。
- 分组后的匹配每个参考刚体可映射多个实例，但分组不由匹配分数确认。固定请求窗口大小，共享总状态预算；每方案分别报告同分/截断。方向/线来自目标圆柱；无限轴线规范点不是枢轴，限位/零位/螺距未知，类型/DOF未验证。所有结果均不修改CAD、不设置人工复核。
- 0.16.0 已增加cad_check_joint_draft与cad_plan_evidence_tasks。必须先重放原始草案/检查及全部来源，不接受手改分数、成员或删除风险。结构正确不等于机械一致；有效lock与运动假设的冲突、参考轴向差异、不同候选类型要分开报告。
- 计划只生成JSON，executed=false；仅允许已定义的只读采集与保护工具，预算包括前后document/pose检查，整项依赖不能静默丢失。已有完整观测即使为空也复用；不捏造面索引、种子或运动参数，不靠重复扫描替代缺失求解能力。
- 执行计划需按原token与文档/实例上下文校验；变化则重采快照并重算，不改旧token/哈希。原始返回独占新建，后置检查失败的结果只作诊断。单实例约束暂不被chain自动消费，0.17.0起由独立回填和比较工具处理兼容观测。
- 0.17.0 已实现sw_execute_evidence_task（每次最多一个只读调用）、cad_reintegrate_evidence和cad_compare_draft_checks，CLI可串行执行有界计划。独占保存原始envelope和新receipt；重放计划、原来源和执行记录，禁止伪造执行成功。
- execution_complete只表示任务有终态；完整且所有guard通过后，只有完整capture可自动回填。上下文变化或TIMEOUT/OUTCOME_UNKNOWN停止后续任务；普通失败可继续独立任务及后置检查。崩溃/占用文件不得删除后盲目重试。
- 回填沿用原阈值、模板与预算，仅更新兼容圆柱/根配合/距离基础；单实例约束及面目录仍属补充上下文，回填报告本身不是复用索引；0.18.0起经独立索引再交接规划器，不循环重采。原文件保留；pipeline_error后的中间文件只作诊断。
- 比较返回newly_observed/still_observed/no_longer_observed/changed，保留设置、覆盖与具体内容；本次未观察到不代表机械问题解决。0.18.0已扩展补充观测关联与复用，真实单链联调仍需本机结果；暂不扩展整机仿真或拆卸路径执行。

- 0.18.0 cad_index_evidence重放完整且guard通过的执行链，按当前check关联组件/组件对/发现/关节上下文。完整观测可复用，失败和partial保留尝试。名字不推根实例，面目录不推接触；fixed提示只描述当前配置，不确认物理关节。
- 后续规划必须携带最新evidence_index_path；algorithm_version=2计划返回collect/stop，stop时tasks为空，执行器以NO_CAPTURE_TASKS拒绝且不调用CAD。单条显式链最多4轮，原始文件不覆盖，不删索引绕过次数/尝试，也不自动扩预算。仅来源中的历史可知，不能假称知道其他会话的采集记录。
- 0.19.0 cad_plan_face_probes将已测组件最近点与完整面目录结合，生成algorithm_version=3计划；缺目录时先采集再索引续轮。解析残差只筛选无限曲面，不判断裁剪面成员；实际sw_probe_face_pair才解析持久引用并测有限面。
- 面探测执行复用单步执行器，绑定原目录/参数/前后上下文并重算原始数值。face_probes索引保留完整与失败尝试，反向/换种子/提高迭代次数不自动重试，与通用补采共享4轮。目录或距离快照冲突时保留未知；不任取最后一份。
- 0.20.0回填只消费当前guard通过的receipt：面探测沿用已有复核覆盖组件对的阈值与全部旧行；未覆盖对可传原始face_review_path，只导入匹配当前guarded probe哈希/定位符的行。不扫描目录补历史，不用外部阈值覆盖旧对；歧义、重复、容量、缺依据明确保留。失败派生文件只作诊断。
- 面比较按目录哈希/定位符/阈值区分观察，测量内容变化与来源文件变化分开；不同目录不猜同一CAD实体。新check建立新索引后再规划，沿用轮数与停止规则；不宣称物理接触/运动副/拆卸路径已经验证。
- 只读重放的输入字节/路径缓存只活在一次重放内，返回前重新解析路径和核验内容哈希；不缓存可变JSON对象，不跨调用复用此缓存，不装饰写文件或CAD调用。禁止用缓存绕过来源校验。
- 0.21.0默认cad_draft_joints不加载模板；connection_candidates以目标配合/几何/冲突为主结果，目标类型unknown、DOF=null。仅非空显式template_ids增加类比；reference_joint_kind/reference_dof不得写入目标hypothesis_kind或自由度。bench_vise/swivel不能因结构映射变成升降机revolute，也不凭“端座/导轨”等名字反推fixed/prismatic。
- 新草案与check的algorithm_version=2；目标实例对输出预算max_target_pairs由全部分组方案共享，未知/省略分别报告。没有参考匹配不阻断检查、补采、回填、索引和比较。索引v2区分目标上下文与参考类比，并更正完整面probe的条件回填提示。旧草案/check/index按版本重放，不篡改旧字段/哈希；升级目标结论时从原rigid source生成新草案，不在旧计划中换token或草案。

- 0.22.0新增独立cad_analyze_constraints，逐实例对、逐根mate源输出局部固定/旋转/滑动候选及支持/冲突/缺口。sw_mate_inventory可选include_reference_geometry读取直接引用面和LockRotation；未知不默认false。近接触、同轴、名称和模板不提供约束，不跨快照合并，不把重复轴计为独立约束。目标类型仍unknown、DOF仍null。新报告暂不进入自动补采/草案修改，保留旧文件重放与4轮历史；增强采集必须重新形成绑定来源。

- 0.23.0 cad_plan_evidence_tasks可选constraint_analysis_path生成v4约束缺口计划；报告/check必须同target。只补配合面几何和LockRotation，基础采集不满足增强能力，增强成功/partial/failed均不自动重采。报告绑定索引则自动继承，不换旧索引或绕过共享4轮。全部实例保护计预算，STEP无配合、未知求解规则、多来源歧义不能靠重复扫描解决。
- v4计划回填调用独立索引与分析工具，输出v3回填报告、新check/index及绑定索引的约束报告，保留原公差/范围/预算；partial失败但保护通过也保留尝试和轮数。成功后直接交接新check/report/index，不重复索引同receipt。pipeline_error时全部after来源null，中间文件只诊断。不同快照feature_id不做身份匹配；候选不写成目标类型或自由度。

- 0.24.0 cad_solve_local_constraints独立重放原约束报告，仅显式有效lock/同心轴/重合平面建立缩放速度方程；characteristic_length_mm必填。每对每源独立求解，不把不同快照或近接触拼约束。原报告/index/check/轮数保留；补采仍用原报告，求解不重置历史。
- modeled_instantaneous_dof仅是完整稳定的已建模局部瞬时维数；最终目标类型unknown/DOF=null。缺失/截断只保留已知子集，空模型不当6DOF；冲突/敏感不输出运动模式。相关方程不是可删除配合，基向量不是物理关节；原点与数值尺度必须说明。不认定有限运动、整机自由度或拆卸路径。

- 0.25.0 cad_solve_chain_constraints从原analysis组装2–20个目标实例、同一源快照的约束；显式参考只是去掉整体刚体运动，不证明接地。链内跨对联系由共同未知量处理，链外/未绑定仍是缺口。不相加局部DOF，不跨快照组装；不连通/截断/冲突/敏感保留未知。硬上限每快照6000方程。
- 常规补采优先sw_execute_evidence_batch，服务端串行复用单步执行/保护/停止/receipt，每批默认12步与30秒软预算，最多20步/60秒。不会取消已在执行的COM；批次独占本进程CAD调用，其他CAD请求BUSY，不并行排队。客户端timeout=300000ms；不是延长COM超时或重复失败调用。
- 批次摘要的execution_source才是续跑/回填的receipt，batch_report_source仅计时诊断。未完整/保护失败不复用。计时区分CAD工具调用与编排开销，不包含agent思考/网络/UI；不能将合成时间当实机加速比。优先摘要和文件路径，需要具体证据才展开完整JSON，不重复读取会话/tool list/完整清单或已增强失败历史。

- 0.26.0 chain-session仅用于首次空证据链，2–20个准确叶实例、当前token、显式参考/尺度/公差。CLI复用公开工具服务，不并行CAD；初次清单默认不取全量包围盒。原计划与保护不改，最多初始和一次增强两轮；已有历史须沿用最新check/index/analysis，不重启初始化绕过4轮。
- cad_create_chain_baseline离线重放首轮完整guarded receipt，创建首次兼容关系/连接来源并立即索引所有成功/失败/partial尝试，报告绑定index。已有来源/索引使用reintegrate。少于两个有效圆柱envelope时不伪造关系，保留补充观测与缺口。
- session报告的workflow_complete只表示受限流程完成；handoffs是最新文件定位，错误后中间结果只诊断。stdout摘要、详细调用独占保存，错误CLI非零退出；中断后依原receipt恢复，不删除占用文件。耗时分阶段与批内工具，不能重复相加，不能当实机加速比。

- 0.27.0 cad_review_root_mates将原始根配合与完整空间清单关联，不依赖圆柱关系。schema v2只绑定inventory/mates，逐源重放；只保留准确双实体/双实例关联，多实体或未映射保持unmatched，不被已有实例对吸收。含face_matching的输入仍走原schema v1几何关联，不删来源绕过。
- 首次baseline可独立消费完整根配合，圆柱失败不阻塞；可选几何关系仍需两份完整圆柱envelope。成功/失败/partial全部索引，旧v1文件照原语义重放。只求原生约束时chain-session配置capture_profile=root_mates，初始v5计划一次增强采集+2N+2保护，不扫描实体；默认geometry_and_mates不变。已有history不切模式重启，无配合STEP仍未知，不自动转模板/造关节。

- 0.28.0 cad_analyze_geometric_connections独立解释目标圆柱关系、局部平面采样和距离，复用同target的最新index。重复面不投票，多轴防转仅为啮合条件成立时的推论；缺啮合/保持/运动证据不选唯一类型。no_direct_joint/other_relationship保留，名称、模板、AABB不确定类型。报告不进入原生约束求解器或覆盖草案，target类型unknown/DOF=null。
- 几何报告可交cad_plan_evidence_tasks的geometry_analysis_path分支，v6只安排缺失组件对距离与全部保护，和constraint/initial profile互斥。报告必须先绑定最新index，禁止新索引配旧缺口或替换历史。执行→同check索引→同target几何重算；不要求先有proximity来源。近距离有限面验证交原face planner，仍共享4轮和失败/partial不重试。面探测和几何分类不证明真实关节/有限运动。

- 0.29.0 sw_read_face_boundary只读取已绑定圆柱面的GetEdges、直线顶点/圆弧参数并回读；不读AABB/显示网格代替有限边界。复杂曲线、零边界、数量不符、失败、预算截断保持未知；圆弧不当完整圆周。referenced_part_definition不含装配级特征，前后回读不是原子拓扑指纹。
- cad_analyze_finite_connections使用原geometry报告及其同target的当前/后继index，解析轴向投影包络；圆弧投影用完整圆的保守包络。重叠不证明角向覆盖或轴孔啮合；分离只针对指定面，半径差不当配合间隙。轴向局部平面样点未证明与圆柱同实体/邻接，更不能确认限位。unknown/null保持，报告不传原生运动求解器。
- finite_analysis_path生成v7补采，和其他profile互斥；只采候选面未尝试边界，同面去重、64边预算不自动提高、全部文档/位姿保护计成本。批次→同check索引→原geometry+最新index重算finite，保留失败/partial与共享4轮。新index不得配旧finite报告，既有v1–v6计划重放语义不改。

- 0.30–0.31采样/邻接/有限端面读取与离线解释解耦。采样点命中不证明连续覆盖；圆盘/同心环扣孔，凸多边形裁剪，复杂轮廓partial/未知，不填孔或当完整圆。邻面只能用原始adjacency持久引用，不猜catalog索引。面积/相向小间隙不证明接触、保持、运动或行程，假设闭合方向不变成约束。v8/v9互斥规划共用原保护、失败历史与4轮；旧v1–v8重放语义不改。
