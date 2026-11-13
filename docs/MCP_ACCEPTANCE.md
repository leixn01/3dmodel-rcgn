# 当前版本 MCP 实机验收

目标：在安装 SolidWorks 的 Windows 电脑，通过 OpenCode 实际调用当前59个工具（含补采执行、回填、比较及证据关联复用），核对返回值与 SolidWorks 窗口。离线测试及模拟后端不能作为实机通过证据。

## 准备与连接

1. 在仓库根目录执行 `git pull --ff-only`，按 README 安装或更新 `.[solidworks,templates]`，退出并重启 OpenCode。先完成 0.6.0 的 Conda 环境核对；SolidWorks 未运行时再按 0.4.0 启动，无需手动提前打开。
2. 运行 `opencode mcp list`，确认 `solidworks` 已连接；进入 OpenCode，确认 MCP 工具目录包含当前 59 个工具。客户端可能给工具名添加服务器前缀。
3. 记录提交 SHA（`git rev-parse HEAD`）、Windows/Python/OpenCode/SolidWorks 版本。MCP 已连接仅代表协议可用，必须继续检查 `sw_session_status`。

用户最新反馈：在 SolidWorks 2025、STEP 导入装配的环境对旧版 15 个工具逐项调用，11 项 API 通过，2 项失败（辅助对象显示），2 项部分通过（组件隐藏实际生效但超时、空间清单小范围正确而全量超时）。原图报告 254 个组件、60 秒超时，未提供提交 SHA 或原始 JSON；该反馈不等于 0.5.0 已验收。0.4.0 起已有第 16 个启动工具、180 秒调用上限；本次修复不能仅靠调高超时宣称成功。先完成下面 0.5.0 复测。

## 0.21.0：目标证据优先与可选模板

更新仓库后在已有Conda安装`.[solidworks,templates]`，重启OpenCode。仍45工具、38功能skill。只使用目标证据的草案不调用USD模板解析；下方模板对照验收需要templates依赖。

```powershell
python scripts/verify_target_evidence.py --output outputs/verify-0.21
```

预期`passed: true`、27项检查、退出码0，输出目录必须未存在。脚本用合成目标证据和仓库固定bench_vise资产，验证swivel保留为参考revolute、目标类型unknown/DOF=null，以及不加载模板的完整草案→检查→计划→合成执行→回填→比较→索引→停止。不能称为该升降机实机验证。

### 用本机已有证据升级

已有真实`cad_build_rigid_candidates`原始文件及全部来源；保持原件，用新输出名。旧草案、check和索引可按原版本读取，但其模板类型字段不能作为新结论；需要重新生成草案，不能手改algorithm_version或哈希。

```powershell
# 默认：不传 --template-ids，不需要找到合适模板。
python -m cadkin draft-joints outputs/rigid.json --output outputs/target-draft-0.21.json
python -m cadkin check-joints outputs/target-draft-0.21.json --output outputs/target-check-0.21.json
# 只有需要台钳结构类比时另存：
python -m cadkin draft-joints outputs/rigid.json --template-ids bench_vise --pattern-size 2 --output outputs/analogy-0.21.json
```

| 检查对象 | 应观察到 | 失败标准 |
| --- | --- | --- |
| 默认cad_draft_joints | algorithm_version=2；template_sources=[]、template_search_requested=false；connection_candidates保留目标关系与来源；match=null是正常状态 | 自动加载参考库或无模板就无结果 |
| 目标结论 | target_joint_kind=unknown、target_degrees_of_freedom=null；assessment区分约束特征、几何候选、冲突与证据不足 | 仅凭名称/同轴/接近或模板赋fixed/revolute/prismatic/1DOF |
| 显式bench_vise类比 | reference_joint_kind可为revolute，hypothesis_kind仍unknown；reference_dof与目标自由度分开 | swivel被继承成端座↔导轨的目标旋转副 |
| 基线一致性 | 同输入、同目标参数下，是否选模板都不改变connection_candidates | 模板影响目标证据或强制删除不匹配组件对 |
| 预算和风险 | max_target_pairs默认200、所有方案共享；target_pair_coverage保留省略；原冲突和未知继续报告 | 截断视为无连接，或无模板被报PARTITION_NOT_SEARCHED |
| 后续流程 | check→补采→回填→新check索引可完全不使用模板；真实执行仍需要原文档/配置/位姿一致 | 回填时悄悄重新选择模板或索引把参考类型当目标类型 |

`cad_match_mechanism_templates`显式调用仍可搜索参考结构，但新输出也分离参考/目标类型。分数只评连接线索和相对轴线，同证据下旋转/平移参考可以同分。即使真实目标有lock特征，也只报告约束特征及与参考运动的冲突，尚未调用求解器证明刚体或自由度。

原始输入、调用返回、草案/check/计划、后续执行证据全保存在outputs。离线步骤不改变SolidWorks窗口或模型；旧计划继续用旧绑定。已有执行历史时，用新check和最新receipt重建索引，再生成携带该索引的新计划，保持原有累计轮数；不能省略索引重新计数。

## 0.20.0：面证据回填与变化比较

更新方式见README：已有Conda中`git pull --ff-only`、`python -m pip install -e ".[solidworks,templates]"`，重启OpenCode。仍45工具、38功能skill。

```powershell
python scripts/verify_face_reintegration.py --output outputs/verify-0.20
```

预期`passed: true`、28项检查、退出码0；输出目录必须未存在。报告、调用返回与原始数据位于该目录。合成CAD提供观测，生产离线工具完成回填/比较/索引；不作为升降机实测通过证据。脚本检查11条新probe、原观测保留、原阈值优先、明确依据补充、来源重放、独占输出、比较和停止。

### 本机已有面测量时

前置：0.19.0生成的本轮执行receipt完整且guards_passed；原check、原计划及全部绑定来源仍可读取。receipt中的probe必须来自真实SolidWorks。处理当前轮再续轮，不能把历史索引冒充本轮执行记录。以下名称为示例，替换成真实路径。

| 工具 | 参数 | 预期核对 |
| --- | --- | --- |
| `cad_reintegrate_evidence` | execution_path、output_path；可选face_review_path | recomputation_complete=true才有after_check_source。已有组件对保留旧行/原阈值；未覆盖对仅导入明确复核中匹配当前guarded probe的行 |
| `cad_compare_draft_checks` | before_check_path、after_check_path、output_path | face_evidence逐对区分新增、旧测量变化与provenance_changed_ids；保留阈值覆盖、旧新支持/冲突。局部测量仍不确认连接 |
| `cad_index_evidence` | draft_check_path=成功回填后的check、execution_path=同一本轮receipt、output_path | 新索引绑定新check，保留历史与轮数；若回填失败使用原有效check |
| `cad_plan_face_probes` | 新check、新索引及原有阈值/预算、新output_path | 已尝试对不重复；无新任务或预算用尽时stop，仍列剩余风险 |

```powershell
# 原链已有兼容复核依据时可省略 --face-review；参数不能覆盖已有组件对阈值。
python -m cadkin reintegrate-evidence outputs/face-run.json --face-review outputs/face-review.json --output outputs/update-0.20.json
python -m cadkin compare-checks outputs/check.json outputs/update-0.20-derived/check.json --output outputs/compare-0.20.json
python -m cadkin index-evidence outputs/update-0.20-derived/check.json outputs/face-run.json --output outputs/index-0.20.json
```

没有兼容面复核时，Agent把当前完整probe交给独立`cad_review_face_contacts`，按项目配置或明示工作假设生成复核，再传face_review_path。其完整参数见[接口](TOOL_CONTRACTS.md#0200面回填和证据比较)。30mm/.1mm等模拟阈值不能复制成目标真值，不设置人工复核。

验收数据：逐项检查face_routing、face_updates、applied_capture_ids、reused_capture_ids、supplemental_captures和excluded_captures对应原始哈希、复核阈值及具体面。旧文件字节不变，新文件独占创建。所有这些离线步骤不改变SolidWorks窗口/模型。

失败标准：改写旧阈值或旧probe、导入未通过guard的行、手改复核仍通过、回填失败却返回有效after_check、文件重写被说成测量变化、重复采集已尝试面、把小间隙称为真实连接。正常保留项：无依据、阈值歧义、同面已有另一快照、100条复核/20个来源上限、partial/失败。它们不是必须人工批准的节点。

保存完整receipt、原始probe/目录/距离、复核、回填报告及-derived目录、比较、新索引与续轮计划在outputs中；记录提交SHA与软件版本。`pipeline_error`后的中间文件仅供诊断，不能用于新的有效草案。

## 0.19.0：自动面候选与有限面探测任务

前置：更新仓库，在已有Conda环境安装`.[solidworks,templates]`并重启OpenCode；当前45工具、38个功能skill。

```powershell
python scripts/verify_face_planning.py --output outputs/verify-0.19
```

预期`passed: true`、30项检查、退出码0；重复运行换新目录。该脚本在显式模拟CAD中走“有预算的初始补采→补齐缺失目录→自动面探测→索引→停止”，保留原始调用和receipt。它不连接用户SolidWorks，不能作为升降机实测通过证据。

### 本机真实执行

已有有效draft check、最新evidence index及全部原始来源；当前SolidWorks文档、配置、dirty、实例位姿仍与来源一致。至少一对范围内实例已有完整sw_component_distance原始结果；缺失时先交接对应距离/补采能力，不从包围盒填测点。尚未取得来源时按读取、链清单、草案、检查、补采顺序生成，不能拿模拟文件替代。

1. 调用`cad_plan_face_probes`，必需参数为`draft_check_path`、`evidence_index_path`、`output_path`、`max_component_gap_mm`、`surface_tolerance_mm`。可选预算见[接口](TOOL_CONTRACTS.md#0190面探测任务计划)。距离筛选与解析曲面残差是两个不同阈值，使用已有配置或说明工作假设，不能由参考模板直接定为目标公差。
2. 先看`continuation.action`。collect时按evidence-task-execute逐次调用`sw_execute_evidence_task`；同一plan_path、新output_path，后续传上一receipt路径为previous_execution_path，直到execution_complete。每次最多一个CAD读取。
3. 只有`guards_passed=true`才用`cad_index_evidence`建立新索引；下一轮`cad_plan_face_probes`必须携带该索引并保持阈值/预算。缺目录的计划先采目录，索引后才生成具体面任务。stop时不调用执行器、不反复扫描或增预算。
4. 将最新索引中`family=face_probes`且`usable=true`的`source.path`列表交给`cad_review_face_contacts`，显式给`contact_tolerance_mm`和`angle_tolerance_deg`，独占写新文件。失败/partial探测保留诊断；尚不自动回填草案。

CLI与MCP共用实现。以下路径换成当前真实文件，30mm/.1mm是演示数值，使用时明确自己的阈值依据：

```powershell
python -m cadkin plan-face-probes outputs/check.json --evidence-index outputs/index.json --max-component-gap-mm 30 --surface-tolerance-mm 0.1 --output outputs/face-plan-0.19.json
# 只在计划action=collect时继续
python -m cadkin execute-evidence outputs/face-plan-0.19.json --output outputs/face-run-0.19.json
# 只在完整执行且guards_passed=true时继续
python -m cadkin index-evidence outputs/check.json outputs/face-run-0.19.json --output outputs/face-index-0.19.json
```

逐项核对原始JSON，保存提交SHA、本机版本、耗时和错误；SolidWorks视图、选择、dirty、零件位置应保持原样，不需人工确认才能推进。

| 验收项 | 预期 | 失败标准 |
| --- | --- | --- |
| 计划来源 | algorithm_version=3；check/index绑定与input_files哈希一致 | 接受手改计划/来源或不同check的索引 |
| 候选依据 | 每对保留真实目录哈希、body/face定位、距离来源、两端残差 | 从名称、面类型或同轴直接认定配合面 |
| 种子 | 来自距离端点和去重中点，根装配毫米 | 使用局部点、包围盒或虚构点冒充已测最近点 |
| 缺目录 | 仅安排缺失实例的目录；索引后再规划面探测 | 未采集即猜面索引/持久引用 |
| 共面/分割面 | 保留竞争面及同分截断；finite_face_membership_tested=false | 用无限曲面残差冒充裁剪面成员测试 |
| 实际探测 | 原始sources/parameters与任务一致，有限面GetClosestPointOn、正常解析身份，数值重放一致 | 错面/错误参数/单位/间隙仍被标为可复用 |
| 上下文变化 | 前后检查失败后结果不复用；身份/几何变化停止后续调用 | 变化后沿用旧来源或改token凑通过 |
| 失败与复用 | 普通失败仍执行可独立进行的任务/后置检查；partial/failed留档且不自动重试 | 增加迭代次数、换种子或反向配对绕过尝试历史 |
| 预算 | 组件对、每端面候选、面配对、工具调用各有限制，保护调用计数；共享4轮上限 | 预算未计保护、隐藏遗漏或自动扩预算 |
| 停止 | stop时tasks=[]，调用执行器得到NO_CAPTURE_TASKS且无新receipt | 把停止写成风险已解决或继续只有保护检查的空轮 |
| 面候选复核 | 明确接触候选/角度阈值，保留局部范围；contact_confirmed=false | 小间隙认定接触/运动副，大局部间隙认定整面分离 |

本阶段仅针对放置后的零件定义平面/圆柱面；装配级切除、其他曲面、未检面、接触斑和运动/拆卸路径仍未验证。

## 0.18.0：证据关联、复用与停止

前置：Windows已有Conda环境，更新仓库并安装`.[solidworks,templates]`，重启OpenCode，目录应含44工具。以下模拟验收无需启动SolidWorks：

```powershell
python scripts/verify_observation_reuse.py --output outputs/verify-0.18
```

预期passed=true、26项检查，原始请求/返回与报告在新目录。重复运行更换目录。脚本使用明确测试替身，不是升降机实测；完整回归另覆盖多轮预算、失败/部分观测、来源篡改、停止和CLI。

实机前置：已存在0.17.0原始执行receipt，execution_complete=true、guards_passed=true，并有当前有效check及所有来源。成功回填后使用after_check_source.path。若没有现成输入，按对应独立功能取得实际空间/链/草案/执行记录；不要用模拟文件替代。

依次调用：

1. `cad_index_evidence({"draft_check_path":"outputs/update-0.17-derived/check.json","execution_path":"outputs/run-0.17.json","output_path":"outputs/index-0.18.json","max_contexts":200})`。
2. `cad_plan_evidence_tasks({"draft_check_path":"outputs/update-0.17-derived/check.json","evidence_index_path":"outputs/index-0.18.json","output_path":"outputs/plan-0.18.json","max_tasks":20})`。
3. 读取continuation；collect才按独立执行流程采集，之后兼容回填/比较并用新的receipt和当前check再建索引。stop直接保留结果与风险，不能去掉索引或提高预算反复采集。

等价CLI：

```powershell
python -m cadkin index-evidence outputs/update-0.17-derived/check.json outputs/run-0.17.json --output outputs/index-0.18.json
python -m cadkin plan-evidence outputs/update-0.17-derived/check.json --evidence-index outputs/index-0.18.json --output outputs/plan-0.18.json
```

逐项验证：

| 项目 | 预期与失败标准 |
| --- | --- |
| 来源与原文件 | 索引每条source能回读，哈希一致，原始文件未改；篡改后重放必须拒绝 |
| 组件/候选关联 | 关联指向当前真实实例及草案成员，不按配合引用名称猜根路径；候选分数保持不变 |
| 面目录 | body/face索引只定位该源文件，两个端点有目录也不得标记已选接触面或已确认连接 |
| 约束上下文 | fixed说明当前配置；缺成员/冲突保持未知，不自动升级为刚体或关节确认 |
| 复用与失败 | 完整空结果也复用；partial/失败记录保留且相同工具/范围不自动重试 |
| 预算与多轮 | 未执行延期项可继续安排，保护调用计入预算；单条显式链最多4轮，无自动扩预算 |
| 停止 | continuation=stop时tasks=[]，执行工具返回NO_CAPTURE_TASKS，无CAD调用/新receipt；仍报告风险 |
| 状态改变 | 文档、配置、dirty、完整实例范围或位姿变化拒绝复用，重建来源后再推进 |
| 关联截断 | max_contexts限制明确，不能把未返回候选当不存在；已采集观测仍完整保留 |
| 窗口与记录 | 索引/规划均离线，SolidWorks窗口与模型不应变化；保存JSON、实际耗时及本机异常 |

本版修复上一版Windows短路径/长路径测试比较问题。执行缓存每步仍读回校验输入哈希与参考资源；不是跳过来源检查。停止补采不是机械问题解决，面配对/运动求解仍属后续能力。

## 0.17.0：只读补采执行、证据回填与比较

0.17.0当时为43个工具、36个功能skill。执行、回填、比较是三个独立入口，详细字段按需读取；不设置人工复核。执行器每次最多一个已有只读CAD调用；回填和比较完全离线。

### 一键自动验收

在已有Windows Conda环境、仓库根目录执行，更新后重启OpenCode：

```powershell
git pull --ff-only
python -m pip install -e ".[solidworks,templates]"
python scripts/verify_evidence_execution.py --output outputs/verify-0.17
```

预期`passed: true`、`checks: 30`、退出码0。重复运行换新目录。report.json记录各项结果，calls目录保留参数对应的原始MCP格式返回，synthetic-cad目录保留来源、执行receipt和重算结果。该脚本实际运行显式模拟CAD后端，绝不是用户SolidWorks实测；生产代码没有自动切换模拟后端。

### 本机真实执行

前置：已有原始草案检查和补采计划及其全部来源；当前SolidWorks仍是采集这些来源时的文档/配置/位姿。示例路径必须替换为实际已有文件；缺少输入交接独立采集/计算能力。软件未打开时先走正常启动、打开和采集流程，不能让旧计划凭空适配新token。执行过程中保持装配不变。

| 工具 | 最小参数 | 结果核对 |
| --- | --- | --- |
| sw_execute_evidence_task | `{"plan_path":"outputs/plan-0.16.json","output_path":"outputs/run-0.17-step001.json"}` | 原始envelope独占保存；最多一个CAD读取；返回next_task_id和execution_complete |
| cad_reintegrate_evidence | `{"execution_path":"outputs/run-0.17.json","output_path":"outputs/update-0.17.json"}` | 要求终态且guards_passed；重算兼容证据，保留旧源和应用/补充/排除去向 |
| cad_compare_draft_checks | `{"before_check_path":"outputs/check-0.16.json","after_check_path":"outputs/update-0.17-derived/check.json","output_path":"outputs/compare-0.17.json"}` | 报告新出现/仍存在/本次未再观察到/变化，不声称机械问题已解决 |

MCP执行后续步骤时，相同plan_path、新的output_path，并将前一次返回的output_path传为previous_execution_path。直到execution_complete=true；表中run-0.17.json代表最后一条receipt，使用MCP时替换为实际末步路径。CLI会自动串行调用单步工具并保存末态run.json：

```powershell
python -m cadkin execute-evidence outputs/plan-0.16.json --output outputs/run-0.17.json
python -m cadkin reintegrate-evidence outputs/run-0.17.json --output outputs/update-0.17.json
python -m cadkin compare-checks outputs/check-0.16.json outputs/update-0.17-derived/check.json --output outputs/compare-0.17.json
```

仅在执行guards_passed=true时回填；仅在回填recomputation_complete=true且after_check_source非空时比较。不要在错误结果上继续套用示例路径。

逐项核对：

1. 每次执行前重放计划、原始来源及已有receipt；改变任务tool/参数、源哈希、伪造passed/删除风险应拒绝。底层只能调用原计划已有只读工具，没有启动/打开/选择/显隐/重建/移动/保存操作。
2. summary.calls_executed每次至多增加1；按原计划顺序进行，预算不自动增加。只处理已返回计划任务，deferred_tasks仍未执行。execution_complete表示全部任务有终态，不等于都成功。
3. 文档校验token/路径/标题/类型/配置/dirty；实例校验身份、引用配置、解析/抑制状态及从原始变换得到的根位姿。缺失字段拒绝。单独包围盒失败不会掩盖有效位姿，也不能被拿来证明碰撞。
4. 普通单项采集错误记录failed，其他独立任务和postflight可继续；partial原始返回留档。本轮仅完整passed的capture可回填。文档/位姿变更、TIMEOUT/OUTCOME_UNKNOWN停止剩余调用，绝不盲目重试；后置校验失败全部观测仅作诊断。
5. receipt和原始envelope均独占新建；重复输出或重放已消费prefix应OUTPUT_EXISTS且不再调用COM。崩溃可能留下空/未完成文件；保留诊断，不通过删除文件重试。终态再调用应EXECUTION_COMPLETE。
6. 回填保留原空间快照、公差、模板、分组/搜索预算，依次更新兼容relation/connection/proximity、chain、target、rigid、joints、check。旧数据不改，superseded_sources指明旧新来源。距离不能自动进入原worklist外的候选对；缺少兼容基础/阈值不补造。
7. 单实例约束与面目录分别保留为CONSTRAINTS_CONTEXT_ONLY和FACE_CATALOG_REQUIRES_PAIR_SELECTION_AND_PROBING；不等于关节证据。0.18.0起可用cad_index_evidence关联并交接规划复用，回填报告本身不替代索引；不能因风险仍存在就重复采同一数据。
8. 回填返回partial可能是原冲突/覆盖仍在、部分capture未消费或原计划有延期；读取errors和remaining_findings_summary。pipeline_error时after_check_source=null、applied_capture_ids为空，保留中间文件作诊断。不得称部分步骤形成了完整新结论。
9. 比较先读settings_equal、occurrence_scope_equal和coverage，再解释差异。跨方案同一参考body到成员的局部映射合并用于比较；具体方案保留在草案。changed可能包含来源引用变化，分数不是准确率；no_longer_observed不是resolved，resolved_findings_asserted始终false。
10. 保存提交SHA、软件版本、真实参数/返回/耗时及上下文；对该升降机单链完成真实全流程后才更新MODEL_PROGRESS。模拟、协议、CI成功不代表真实装配或运动校核成功。

失败标准：任意计划工具执行；一次MCP请求隐式跑完整CAD计划；改旧token/哈希绕过；执行错误被覆盖；上下文未通过仍回填；忽略部分/延期；补造阈值/面配对；将采集成功/发现消失写成机械确认；等待人工复核。

当前是一轮有界补采闭环；完整几何原子快照、整机自动划链、自由度/行程/运动/干涉及拆卸路径仍未实现。

## 0.16.0：草案检查与补采规划

0.16.0当时为40个工具、33个独立skill。本轮两个工具只读取来源文件、保存新结果；不会连接SolidWorks或执行计划，不设置人工复核。

### 一键自动验收

在已有Windows Conda环境、仓库根目录执行，更新后重启OpenCode：

```powershell
git pull --ff-only
python -m pip install -e ".[solidworks,templates]"
python scripts/verify_evidence_planning.py --output outputs/verify-0.16
```

预期`passed: true`、`checks: 24`、退出码0。重复运行换新目录。目录保留参数、原始envelope、来源、草案、检查和计划；使用显式模拟CAD数据，不代表升降机实测。报告中的计划调用未执行。

### 用真实模型已有草案验证

前置：已有0.15.0原始关节草案及其绑定的全部文件和固定版本参考资产，保留原路径及内容。缺失来源时重新采集和计算，不手改token/哈希/候选。只在文件存在时用下面示例路径，否则替换成真实路径。

| 工具 | 最小参数 | 核对结果 |
| --- | --- | --- |
| cad_check_joint_draft | `{"joint_draft_path":"outputs/joints-0.15.json","output_path":"outputs/check-0.16.json"}` | 结构错误、证据冲突、竞争解释与覆盖缺口分别记录；每项保留实例/实例对与候选引用 |
| cad_plan_evidence_tasks | `{"draft_check_path":"outputs/check-0.16.json","output_path":"outputs/plan-0.16.json"}` | 具体只读tool/arguments、依赖、优先级、前后校验、原始返回保存路径；executed=false |

等价CLI：

```powershell
python -m cadkin check-joints outputs/joints-0.15.json --output outputs/check-0.16.json
python -m cadkin plan-evidence outputs/check-0.16.json --output outputs/plan-0.16.json
```

核对以下行为：

1. 检查前重放草案、分组、目标图、链与原始来源；修改派生评分/归属/发现或任何源哈希，后续调用应拒绝EVIDENCE_MISMATCH。不可删除风险后再生成计划。
2. `structural_checks_passed=true`只表示成员/端点等结构检查通过；`physical_consistency_verified=false`始终保留。活动lock与转动/移动假设标记冲突；被抑制/错误lock不当作可靠锁定。不同候选的转动/移动解释是竞争假设，不是同时施加的约束。
3. `max_findings`默认200、范围1–2000。先统计全部发现再截断，返回DRAFT_CHECK_LIMIT；有冲突返回partial/DRAFT_CONFLICTS，完整原始检查仍落盘。规划仅消费已返回发现，不能把省略范围当作已检查。
4. `max_tasks`默认20、范围3–200，包含全部文档和实例位姿前后检查；`summary.total_tool_calls`不得超限。预算不足整项采集及其新增校验一起延期，deferred_tasks保留原因；高开销根配合任务延期后允许较小独立任务入选。
5. 完整已有根配合、圆柱、面或距离观测复用；空圆柱扫描、分离距离同样是观测，不盲目重复扫描。无法确认DOF/枢轴/行程/螺距/运动等项保留unresolved_findings。单实例约束仅补充上下文，尚未被链清单消费。
6. 任务使用原始document_token和实例路径。真正执行前须比较文档token/路径/类型/配置/dirty，及实例文件/父级/配置/解析状态/根变换；缺失或不一致停止依赖采集，重新采快照和重算。后置校验失败时新采集只能作诊断，不回填旧快照。JSON哈希不能证明CAD原子快照。
7. 计划只含已有只读工具，参数符合生产目录schema，依赖无环且先于被依赖项；不生成移动/配合编辑/任意脚本，不伪造face_id或投影种子。原始envelope保存路径不得已存在；计划阶段不创建采集文件。将来执行时仍须独占写入，避免覆盖。
8. 输出包含heldout_exposed、reused_evidence、deferred_tasks、unresolved_findings和recompute_handoffs。handoff只是后续重算说明；本轮没有自动执行、回填或前后候选比较器。采集成功不等于发现已解决。

失败标准：来源篡改被接受；竞争候选被称同时冲突；省略范围/延期任务被吞掉；预算漏算校验；计划自动执行CAD；复制或伪造参数；把结构通过/没有发现称物理验证；等待人工确认。

开发环境未连接用户SolidWorks，尚无升降机实机草案检查结果。下一步增加独立只读执行记录、上下文校验与证据回填，再比较候选变化。

## 0.15.0：刚体候选与关节参数草案

0.15.0当时为38个工具、31个独立skill。两个新增工具均只处理文件，不连接SolidWorks、不移动零件、不确认刚体或运动副，不设置人工复核节点。

### 一键自动验收

在已有Windows Conda环境、仓库根目录执行；更新后重启OpenCode：

```powershell
git pull --ff-only
python -m pip install -e ".[solidworks,templates]"
python scripts/verify_rigid_drafts.py --output outputs/verify-0.15
```

预期`passed: true`、`checks: 24`、退出码0。重复运行换新目录。report.json保存各项检查和调用参数，同目录保留原始MCP格式返回、测试来源、分组、草案及负例。脚本使用显式模拟CAD锁定配合/几何，不代表升降机拆解结果或识别准确率；没有启动CAD。

### 真实模型已有证据的验收

前置：已有0.14.0原始target graph及可回读的链/空间/配合/圆柱/距离/面来源，采集时装配、配置和位姿一致。缺少输入时Agent调度对应独立采集能力，保留错误/未知；无需手动填body_map或确认关系。

| 工具 | 最小参数 | 结果核对 |
| --- | --- | --- |
| cad_build_rigid_candidates | `{"target_graph_path":"outputs/target-0.14.json","output_path":"outputs/rigid-0.15.json"}` | 不合并基线始终存在；每方案完整保留所有原始实例，且每实例只归属一个group；合并依据和风险可追溯 |
| cad_draft_joints | `{"rigid_candidates_path":"outputs/rigid-0.15.json","output_path":"outputs/joints-0.15.json"}` | 各方案分别匹配；一个template_body_id可映射多条member_occurrence_paths；目标圆柱几何候选、类型/DOF假设和未知参数分开 |

等价CLI：

```powershell
python -m cadkin rigid-candidates outputs/target-0.14.json --output outputs/rigid-0.15.json
python -m cadkin draft-joints outputs/rigid-0.15.json --output outputs/joints-0.15.json
```

逐项保存原始输入、参数、envelope、输出JSON、版本/耗时，检查：

1. 每个partition的成员并集等于全部target nodes，各成员只出现一次；同文件不同实例未被合并为同一ID。分组只改变JSON假设，SolidWorks文档、位姿和选择不应改变。
2. 干净、未抑制的lock可产生连通候选；其他普通配合、同轴、名称/父级/同文件不单独产生刚体。近距离或收敛局部面信号只生成单接触桥弱替代方案。STEP没有锁定配合时，仅有弱方案或完全不合并均正常。
3. 读取pair_proposals的flags/blocking_reasons、omitted_groups、source_errors和boundary_evidence；运动类配合、实例不可用、来源错误或组大小上限不被忽略。不要把仅有不合并方案写成“所有零件已证实独立运动”。
4. max_partitions=1且存在其他方案时应partial/RIGID_CANDIDATE_LIMIT，仍保留基线；output_truncated表示输出截断，partition_space_exhaustive始终false。该策略不枚举任意多接触桥组合。
5. 关节草案按方案读取match.candidates/template_rankings/best_score_ties_found/search_exhaustive/output_truncated。分组之间不设置“最高分即真”的选择规则；还需报告unmatched_group_ids及所有风险。
6. 默认pattern_size=3。不足3个合格组的方案应skip_reason=insufficient_eligible_groups。关注两个刚体时，在新输出统一用pattern_size=2重算各方案，不混比不同窗口大小的分数。
7. 类型是reference_template_only，DOF/刚性/关节轴/运动仍未验证。axis_origin_m、limits、pitch_m_per_revolution为null；没有复制模板限位/行程。固定副草案不填轴线。
8. 几何方向/轴线只引用目标圆柱；point_on_line_root_m是根坐标米制的无限轴线规范点，不是枢轴。多方向、多位置、平行关系或截断不能强选唯一axis_line_candidate；根坐标轴线公差与参数记录一致。最多每组间对保留128条轴关系、16条线，每线最多32条来源引用并标明截断，原实例对ID全部保留。
9. max_states=1应保留partial/MATCH_SEARCH_LIMIT和零预算方案；总evaluated_states不超过max_states。自动补采建议automatic_followup未在工具内部执行；需要补证据时Agent只调用相应独立能力，重新计算依赖。
10. 修改派生目标图/分组或任何绑定来源应EVIDENCE_MISMATCH，不能创建伪成功输出；重复目标路径应OUTPUT_EXISTS。默认heldout被拒绝。无关节或无正向证据时NO_SUPPORTED_MATCH，不意味着不存在机构。

可选分组参数：max_group_size=8（2–20）、max_partitions=8（1–12）、include_contact_hypotheses=true。
草案参数：pattern_size=3（2–6）、max_candidates=5（1–10/方案）、max_states=20000（1–100000/所有方案共享）、beam_width=50（1–1000）、angle_tolerance_deg=10（0,45]。axis_distance_tolerance_mm=0.1（0,10]）、axis_angle_tolerance_deg=1（0,5]仅用于几何轴线候选去重，不是制造验收公差。

失败标准：原始实例丢失/重复归属；把接触当刚体真值；吞掉来源冲突/省略方案；篡改派生结果仍被接受；复制参考行程或把轴线规范点称枢轴；预算漏报；默认消耗heldout；修改CAD；等待人工机械复核。

本轮开发环境无法连接用户SolidWorks，实机输出仍需由本机采集。自动测试通过不等于刚体/运动副已确认，更不等于拆卸路径可执行。

## 0.14.0：目标实例图与模板局部匹配

0.14.0当时为36个MCP工具、29个功能skill。本轮新增两个独立离线工具：目标图适配与局部模板搜索。默认自动运行，不设置人工复核。原STEP保持不变。

### 一键自动验收

在已有Windows Conda环境、仓库根目录执行，升级后重启OpenCode：

```powershell
git pull --ff-only
python -m pip install -e ".[solidworks,templates]"
python scripts/verify_template_matching.py --output outputs/verify-0.14
```

预期`passed: true`、`checks: 18`、退出码0。再次运行用新目录。报告为report.json，保存原始工具返回、调用参数、模拟来源链、目标图、候选报告、限制/错误用例和4个参考派生控制。脚本不连接SolidWorks。

这18项验证输入适配、来源重放、候选生成、预算、无关节、heldout排除、篡改拒绝与错误恢复等。CAD来源为显式测试替身；参考派生控制给定连接与轴向、隐藏类型和名称，**不是独立几何识别测试或升降机识别准确率**。

### 在真实模型证据上调用

前置：使用同一未变化的装配/配置/位姿采集的完整空间清单，选定2–50个叶实例，已有原始chain dossier及可回读的来源文件。没有清单时由chain-evidence汇总已有文件；缺少必要采集时调用相应独立能力。无需用户填写body_map或人工确认。

| 新工具 | 参数 | 预期结果与核对 |
| --- | --- | --- |
| cad_build_target_graph | `{"chain_path":"outputs/chain.json","output_path":"outputs/target-0.14.json"}` | raw target graph：保留全部所选叶实例/实例对，米制坐标、轴关系、配合/距离/面信号、来源/冲突/边界；连接来源绑定的圆柱关系自动读取 |
| cad_match_mechanism_templates | `{"target_graph_path":"outputs/target-0.14.json","output_path":"outputs/matches-0.14.json"}` | 默认3节点局部窗口、6项reference；候选mapping、joint_hypotheses、score_components、轴角检查、template_rankings、搜索/来源覆盖；无人工等待 |

只有独立圆柱关系文件未被链连接结果引用时，target工具额外传`relation_paths:["outputs/relations.json"]`。可只用已有部分证据，partial保留。输出路径应新建。

等价CLI：

```powershell
python -m cadkin target-graph outputs/chain.json --output outputs/target-0.14.json
python -m cadkin match-templates outputs/target-0.14.json --template-ids gas_lift_bar_stool bench_vise --output outputs/matches-0.14.json
```

逐项保存参数和原始MCP envelope，检查：

1. 节点数等于所选叶实例数；重复文件的不同实例没有合并，parent/configuration保留。米制几何与原始来源一致；近似盒不能当精密尺寸。
2. 连接支持仅来自实际证据；缺失观测/大间隙不改写为不存在机械连接。重放修改后的源文件/派生图应报EVIDENCE_MISMATCH；新输出不产生伪成功。
3. 每个候选的映射一对一，所有映射节点由正向证据连通。模板边界联系、额外支持对、缺少支持的模板边和来源flags保留。
4. 类型字段标明reference_template_only；mechanical_relation_confirmed=false、joint_axis_verified=false、limits/axis_origin_m=null。不能把模板参数写成目标实测。
5. 一起读取search_exhaustive、output_truncated、best_score_ties_found、template_rankings；同分/对称/被截断候选不被伪装成唯一答案。未出现的模板可能无关节或未生成所需窗口，见reference_coverage。
6. 轴向只比较无向相对夹角；多个方向/截断时不挑有利方向。轴角符合不证明统一参考系对齐或运动自由度。分数不是概率。
7. 默认参考搜索不含bar_clamp/planetary_gearbox；普通任务显式传这些ID而不启用include_heldout，返回HELDOUT_TEMPLATE。评测时显式启用会记录heldout_exposed。
8. 将max_states设1、换新输出，应返回partial/MATCH_SEARCH_LIMIT并标明非穷尽；原始来源保持不变。没有支持候选返回NO_SUPPORTED_MATCH，不等于模型没有机构。

可选参数：pattern_size 2–6（默认3；可用目标不足时缩小并记录实际值）、max_candidates 1–20（默认5）、max_states 1–100000（默认20000）、beam_width 1–1000（默认50）、angle_tolerance_deg (0,45]（默认10，为排序探索参数）。相同输入与预算应稳定输出；有限搜索顺序可能影响覆盖，不能把一次未找到当最终否定。

失败标准：来源变化仍被接受；无证据时靠名称造出映射；隐藏预算/冲突/同分；把类型/轴点/行程标为实测；默认消耗heldout；修改原CAD；等待人工机械复核。真实结果和耗时保存到outputs新目录，不提交公共仓库。

当前开发环境无法连接用户SolidWorks。实机可直接执行上述两个离线工具处理已有文件；这些成功也不等于多零件刚体合并、运动或拆卸路径验证完成。

## 0.13.0：参考模板与图结构评分

本轮新增3个离线工具、3个独立skill，并移除默认人工复核skill。目录共34工具、27个skill；旧人工复核API仅保留兼容。下方0.12.0人工复核步骤是历史功能验收，不是现在的拆解前置条件。默认遇到未知继续处理独立部分，最终说明风险。

### 前置与一键自动验证

Windows上激活你已有Conda环境，在仓库根目录执行：

```powershell
git pull --ff-only
python -m pip install -e ".[solidworks,templates]"
python scripts/verify_reference_templates.py --output outputs/verify-0.13
```

输出应为`passed: true`、`checks: 17`，退出码0。目录必须新建，重复运行换`outputs/verify-0.13-2`。报告在`report.json`，另保存所有模板raw graph、构造的错误候选/对应文件/评分和原始工具envelope。全部离线，不需要打开SolidWorks，不修改测试STEP。

17项检查包括：目录默认排除heldout、8个资产的作者标注数量、2个无关节负例保持不完整、同图控制、缺关节、错误类型、部分body_map、未知ID报错及错误后继续调用。构造对应关系已知，仅验证解析/评分，**不是升降机识别率**。

### 逐项通过OpenCode / MCP验证

升级后重启OpenCode，确认生产MCP版本0.13.0、tools/list含34工具。每次调用参数和原始envelope另存到新的`outputs/acceptance-0.13/`，图文件读取工具返回的output_path。

| 工具 | 参数示例 | 必须核对 | 失败标准 |
| --- | --- | --- | --- |
| cad_list_mechanism_templates | `{}` | 6个reference，4个有关节、2个无关节；无planetary_gearbox/bar_clamp | 默认泄漏heldout或把标签称为识别结果 |
| cad_list_mechanism_templates | `{"query":"lifting"}` | gas_lift_bar_stool来源、许可、数量 | 错绑来源或不提供检索范围 |
| cad_extract_mechanism_template | `{"template_id":"gas_lift_bar_stool","output_path":"outputs/acceptance-0.13/lift.json"}` | 5刚体、4关节（2移动/2转动），complete=true；source哈希/CC-BY来源；requires_human_review=false | 丢失来源、错误单位、将行程迁移到目标STEP |
| cad_extract_mechanism_template | `{"template_id":"gear_meshing_kit","output_path":"outputs/acceptance-0.13/gears.json"}` | 3刚体、0关节；partial、complete=false、NO_JOINTS风险 | 从名称补造齿轮传动关节/传动比，或等待人工判断 |
| cad_extract_mechanism_template | `{"template_id":"bench_vise","output_path":"outputs/acceptance-0.13/vise.json"}` | 7刚体、7关节：固定1、移动2、转动4；jaw上限约0.125 m | 把m当mm，把USD行矩阵当CAD列矩阵 |
| cad_compare_mechanism_graphs | 使用自动验证生成的两份raw graph、对应JSON及新output_path | identity控制得1；缺一关节召回6/7；错类型仍有完整连接但类型召回6/7；缺映射不隐藏；报告未评项 | 把这些分数称为自动识别率、隐去缺边/未知或用摘要替代原始关节 |

比较调用的具体参数可直接复用`report.json`中对应calls项，**仅换新的output_path**。真实新图必须重新提供准确对应，不能仅把旧对应里的哈希改成新值。输出summary过期时评分用实际记录，并提示STALE_GRAPH_SUMMARY/partial。

CLI等价入口：

```powershell
python -m cadkin templates --query lifting
python -m cadkin template-extract --template-id gas_lift_bar_stool --output outputs/lift-reference.json
python -m cadkin template-compare outputs/verify-0.13/bench_vise.json outputs/verify-0.13/wrong_joint_type.candidate.json --correspondence outputs/verify-0.13/wrong_joint_type.map.json --output outputs/type-check.json
```

### 错误与证据范围

- 不传来源或同时传template_id/asset_path：INVALID_ARGUMENTS；不存在ID：TEMPLATE_NOT_FOUND。错误后再次列目录仍可用。
- 复用输出：OUTPUT_EXISTS；路径越出项目/输出目录：INVALID_PATH；对应哈希过期：EVIDENCE_MISMATCH，不生成成功报告。
- 仅视觉USD：NO_RIGID_BODIES；外部层/变体/实例：USD_COMPOSITION_UNSUPPORTED，本版不隐式下载或选择变体。解析预算64MiB/20000prim。
- 案例的coupling属性保留但不求解；NO_JOINTS、未知耦合、未知端点等保留不完整状态。轴线位置/角度、限位、刚体误合并、运动与拆卸路径均不在当前评分范围。
- 校验来源时见`cadkin/resources/mechanisms/catalog.json`和ATTRIBUTION.md。8个摘录约100KB，原完整网格不打包；不要拿这些结构摘录直接当完整SimReady场景运行。
- 本轮不连接COM，不能改变SolidWorks实机验收状态；本地仍应保留0.5.0显示/超时修复等复测记录。工程数据不提交公共仓库。

## 0.12.0：机构链证据清单与人工复核

当前 **0.12.0 / 31个工具 / 25个skill**。在已有Conda环境更新安装并重启OpenCode。本轮两项新增均离线运行；已有文件时无需启动SolidWorks。先用真实模型中明确选定的2–5个叶零件验收，不凭模型名称硬编码升降链。

### 准备与准确调用

1. 准备完整空间原始envelope，必须收齐分页/层级；几何缺失可保留partial。可选准备已有分组文件及 cad_review_connections、cad_review_proximity、cad_review_face_contacts 写出的结果JSON。输入须保留原始来源，不能用MCP成功摘要代替结果文件。
2. 明确所选实例范围及名称。调用 **cad_build_chain_evidence**；下面文件路径和实例A/B/C替换为真实值，缺少某一类输入就省略参数或相应数组项，不补造数据：

```json
{
  "inventory_path": "outputs/spatial.json",
  "occurrence_paths": ["实际完整实例A", "实际完整实例B", "实际完整实例C"],
  "chain_name": "升降链候选1",
  "grouping_path": "outputs/groups.json",
  "evidence_paths": ["outputs/connections.json", "outputs/proximity-review.json", "outputs/face-contacts.json"],
  "output_path": "outputs/chain-0.12.json"
}
```

范围2–50个不同叶实例；证据文件最多20个。手工复核过的旧分组若缺review_path，需额外传 grouping_review_path 并使用原review_sha256所绑定的文件；新版分组已保存该路径。没有任何证据文件也可以生成草案，未知对仍保留。

3. 阅读文件中的members、pairs、coverage、boundary_evidence及sources。3个范围实例必须产生3个实例对；未测/无证据的对也在，不能仅统计返回候选。核对链的实际范围，不把清单顺序当作运动或拆卸顺序。
4. 人工逐对给出明确意见后，另存复核JSON。下面是**格式示例**，不要把占位人员、时间、理由或pending改为默认确认；使用实际复核人、带时区时间、基础清单SHA256及该清单的pair_id/evidence_id：

```json
{
  "chain_review_input_schema_version": 1,
  "chain_sha256": "chain-0.12.json的实际SHA256",
  "reviewer": "实际复核人",
  "reviewed_at": "2026-11-12T10:00:00+08:00",
  "decisions": [{
    "pair_id": "从清单读取的pair_id",
    "decision": "pending",
    "relation_type": null,
    "reason": "实际待查理由",
    "evidence_ids": [],
    "acknowledged_flags": []
  }]
}
```

`Get-FileHash outputs/chain-0.12.json -Algorithm SHA256`可读取哈希。decision可为confirmed/rejected/pending/conflict；confirmed须明确relation_type为rigid_connection/revolute_joint/prismatic_joint/other_connection之一，其余为null。每对最多一条；evidence_ids只引用本对，可为空但须有实际人工判断理由。confirmed/rejected还需在acknowledged_flags列出本对所有review_flags的code，并说明判断依据。未给意见的对省略，保持pending。

5. 调用 **cad_apply_chain_review**：

```json
{"chain_path":"outputs/chain-0.12.json","review_path":"outputs/chain-decisions-0.12.json","output_path":"outputs/chain-reviewed-0.12.json"}
```

等价CLI：

```powershell
python -m cadkin chain-evidence outputs/spatial.json --occurrences "实际完整实例A" "实际完整实例B" --name "升降链候选1" --grouping outputs/groups.json --evidence outputs/connections.json --output outputs/chain-cli-0.12.json
python -m cadkin review-chain outputs/chain-0.12.json outputs/chain-decisions-0.12.json --output outputs/chain-reviewed-cli-0.12.json
```

全部使用新输出文件名，不覆盖原始来源。

### 每项怎么验证

| 新增项 | 核对与通过标准 | 失败/未测试标准 |
| --- | --- | --- |
| 实例范围与分组 | members与选择的叶实例一一对应，重复文件实例分别保留，角色标签及人工分组来源可回读；N个实例保留N(N−1)/2对。 | 容器当叶件、遗漏未知对或把角色分组自动称作刚体均为失败。 |
| 三类证据汇总 | 沿source_path/SHA256回读：轴线/配合、组件距离、局部面证据分别保存，没有互相替代测量范围。 | 局部大间隙称全局分离、零距离当接触、配合无报错当求解成功均为失败。 |
| 无轴线候选的根配合 | 来源中存在准确映射到两个实例的根配合时，即使geometric_candidate_indices为空也应列入；保留抑制/错误/未知状态。 | 不能为纳入配合而伪造同轴候选。多实例/未映射/子装配内部配合缺口仍保留；没有案例记未测试。 |
| 边界联系 | 缩小范围后，一端在内一端在外的已有记录进入boundary_evidence；两端在外保留计数，来源unmatched记录仍可查看。 | 范围外未测关系不声称已覆盖，已知边界联系不能静默丢弃。 |
| 未知与partial | 少传证据或只传一对测量时，其他对为unknown，UNASSESSED_CHAIN_PAIRS和源partial保留；missing_evidence_families指出缺口。 | 无证据不等于无连接。complete只描述给定输入的汇总，不是整机已拆解。 |
| 差异提示 | 同阈值距离分类不同、阈值不同或组件上下文距离大于定义面测点间距时，保留双方来源并显示对应review_flags。 | 提示是待核对事项，不能自动认定哪个源正确或删除其中一个；不同范围不能直接叫同一测量。 |
| 人工记录 | 用户明确给意见后核对人员、时间、理由、决定、同对证据ID；没有意见的对仍pending；原清单不变。 | Agent自行填写确认、套用旧pair索引、将rejected当CAD无连接证明均为失败。 |
| 人工与CAD状态分离 | human_confirmed可反映声明，但cad_verified、motion_parameters_verified及mechanical_relation_confirmed仍false；人工全答完不清除源partial。 | 不自动合并、移动、创建关节、推断轴线/行程。姓名时间只作归属，不算身份认证。 |
| 来源变化/错误恢复 | 对副本做哈希不符、派生值变动、错pair/evidence ID或漏acknowledged_flags负例，应拒绝且不写成功结果；随后合法离线调用仍可用。 | 负例验证文件逻辑，不算真实CAD实测。旧清单意见不能自动应用到新来源；不能手改SHA绕过。 |

保存版本/SHA、输入文件哈希、准确参数、原始返回、范围选择依据和真实人工意见到 `outputs/acceptance-0.12-<时间>/`。对真实模型，仍需按对应旧清单核对CAD原始采集；离线汇总成功不能替代实际面/距离测量。测试用演示确认不得写入升降机正式复核记录。

可直接告诉OpenCode：

> 按0.12.0清单，明确选择一条升降链的少量真实叶实例，离线汇总已有角色、配合、组件距离和面证据。保留未知对和边界联系，列出需要我判断的关系；我明确给意见后再单独记录人工复核，不自动确认或移动零件。

## 0.11.0：具体面间隙与法向

本节保留 **0.11.0 新增能力**；当前版本/数量按上方0.12.0检查。在已有 Conda 环境更新安装并重启 OpenCode。本轮验证有限平面/圆柱面上的局部测点间隙和法向，**不验证全局最小面间距或确认真实接触**。模型总体状态见 [拆解进度](MODEL_PROGRESS.md)。

### 前置与准确调用

1. 选择当前装配中两个已解析叶零件，先用少量、可在界面看清楚的平面测试，再试圆柱面。结束在位编辑；记录 SHA、版本、PID、token、配置、dirty、选择、显隐和实例位姿。保持模型/配置不变，不重建或移动。不使用有未知装配级切除差异的面作本轮通过基准。
2. 分别调用 **sw_component_faces**。完整 occurrence_path 换为真实值，首次建议限制为少量面；若目标面不在前缀内，再明确扩大预算重新采集新文件：

```json
{"expected_document_token":"实际24字符token","occurrence_path":"实际完整零件路径A","max_bodies":5,"max_faces":30}
```

另一个实例同样调用。保存完整 envelope 为 outputs/faces-a-0.11.json、outputs/faces-b-0.11.json（或未使用的新名字），保留 status/data/errors。核对 body_index/face_index 对应的 descriptor、face_reference、预算与错误，不用数字索引代替持久 CAD 身份。

3. 从两个目录各选一个已识别的 plane 或 cylinder 面。由用户指定测量位置、已有组件距离最近点或已读取模型位置确定1–8个种子；**必须使用根装配模型坐标，单位毫米**，保存坐标来源。普通起始点只用于启动查询，无须已在面上；不能默认填零或拿局部坐标直接输入。
4. 调用 **sw_probe_face_pair**：下面 source 路径、索引和坐标均须替换为实际数据；[100,200,300] 只是参数格式示例，不是升降机已知测点。

```json
{
  "expected_document_token": "实际24字符token",
  "left": {"face_inventory_path":"outputs/faces-a-0.11.json","body_index":0,"face_index":0},
  "right": {"face_inventory_path":"outputs/faces-b-0.11.json","body_index":0,"face_index":1},
  "seed_points_root_mm": [[100,200,300]],
  "max_iterations": 20,
  "convergence_tolerance_mm": 0.001
}
```

保存完整原始 envelope 为 outputs/face-probe-0.11.json。convergence_tolerance_mm 只检查迭代点位置稳定，不是接触公差；converged=true 也不证明找到了全局最小值。返回的 part_m、root_m/mm、原始法向和修正法向分别保留，不再追加实例变换。

5. 调用 **cad_review_face_contacts**。0.1 mm / 5° 为首次**探索值**，按实际工程需求另定并记录；不能称为通用合格标准：

```json
{
  "probe_paths": ["outputs/face-probe-0.11.json"],
  "output_path": "outputs/face-contacts-0.11.json",
  "contact_tolerance_mm": 0.1,
  "angle_tolerance_deg": 5
}
```

已有完整来源文件时纯离线执行，不启动 SolidWorks；同一来源绑定面对应只传一个快照。等价 CLI：

```powershell
python -m cadkin review-face-contacts --probes outputs/face-probe-0.11.json --contact-tolerance-mm 0.1 --angle-tolerance-deg 5 --output outputs/face-contacts-cli-0.11.json
```

### 每项怎么验证

| 新增项 | 核对与通过标准 | 失败或未测试标准 |
| --- | --- | --- |
| 面目录与身份 | 对可在窗口核对的平面/圆柱检查实例、面积/类型/参数；引用捕获回读成功，重复实例分别绑定完整路径。 | 索引/相同轴线不能当作面身份。无可核对面时记未测试；引用失败保留该面几何与 partial，不能写成完整空目录。 |
| 有限面测点 | 人工核对返回点确在所选有限面上；尤其测试面边界附近或两个底层平面接近但实际裁剪区域相隔的例子。根坐标两点的间距与 gap_m/mm 一致。 | 无限平面距离/圆柱轴线中心距不能代替本结果。UV 矩形不能证明点在有孔或被裁剪的面内。没有可核对实例则记未测试。 |
| 坐标与重复/嵌套实例 | 比较窗口的根模型坐标与 root_mm，检查各自 part_m 和变换关系；重复文件的不同实例不得混用位姿。 | 点再乘父变换或两次实例变换为失败。界面爆炸位置不等于模型坐标，不用其截图距离判定 API 错误。 |
| 局部法向 | 从简单平面开始核对朝向：FaceInSurfaceSense=true 时相对底层曲面法向翻转，旋转后法向保持单位长度。近似相反法向的 opposition_error_deg 接近0。 | 单凭同向/平行不能称相向；曲面体不能默认具有实体外法向。圆柱面边界/接缝处法向仅为该曲面局部方向。 |
| 局部探测范围 | 每个种子的 iterations/converged/errors 保留。不同种子可返回不同有效点对；交换左右面后分别核对点归属和法向。 | 不要求局部算法在不同种子/左右顺序下必得同一全局最小值；大测点间隙不能证明整面分离。 |
| 离线分类 | 阈值内且两端为实体面、法向相反、非零点差方向也相向时为 near_face_contact_candidate；方向不明为 near_points_orientation_unconfirmed；测点间距较大为 sample_gap_above_tolerance；全失败为 unresolved。 | 零间隙仍不区分接触、穿透或包含。所有结果 global_minimum_proven=false、contact_confirmed=false、mechanical_relation_confirmed=false。 |
| 预算与失败 | 有多面时 max_faces=1 应 partial/truncated；通常 max_iterations=1 无法验证迭代稳定，应保留点和 FACE_PROBE_ITERATION_LIMIT。点读取失败 metrics=null；法向失败可保留点距。 | 失败补零、丢弃错误后写 complete=true、把未读面视为无接触均为失败。恰好读完无需截断。 |
| 源绑定与恢复 | 用 Get-FileHash 核对目录与探测文件；混用旧位姿/配置、改写源 JSON 应拒绝 EVIDENCE_MISMATCH；同来源对应重复文件拒绝 DUPLICATE_FACE_PROBE。错误后正常查询仍可用。 | 不改哈希/ID/参数绕过。离线 JSON 副本负例不算真实几何 API 验收；致命 data=null 文件只保存为错误记录。 |
| 只读与变化 | 比较前后 dirty、选择、显隐、位姿、原文件哈希；稳定模式下成功，检测到身份/参数/位姿变化时拒绝混合结果。 | 不自动选择、移动、解析、切配置、重建或保存。无原子几何版本保证；单次 COM 超时仍需先核对现场再重启 MCP。 |

保存准确参数、种子来源、原始返回、源哈希、耗时、界面读数/截图与逐项结论到 `outputs/acceptance-0.11-<时间>/`。可以通过界面“测量”的点到点模式核对已知点对；界面全局最小值只是另一个对照量，局部值不相等不自动判错，但不能把局部值冒充全局最小值。无法直接核验某点或法向时记录未测试。

本轮读取零件定义并按实例放置，**不含装配级切除、全表面类型、全局干涉检查或接触区域识别**。自动测试/模拟后端不能替代以上实机核对。

可直接告诉 OpenCode：

> 按0.11.0清单验收：选两个可核对的真实零件，读取少量面，从实际根坐标位置探测一对平面或圆柱面的局部间隙与法向，再按探索值0.1 mm/5°离线复核。按需加载独立 skill；记录种子来源、原始返回、partial和未知区域，列出我需要在窗口核对的面和点，不确认全局最小距离、接触或运动副。

## 0.10.0：组件距离与近接触候选

本节保留 **0.10.0 新增能力**；当前版本与工具数量按上方 0.12.0 检查。继续使用已有 Conda 环境，更新安装并重启 OpenCode。三项新能力不要求 STEP 有配合：离线准备待测对、在线单对测量、离线复核。先验收少量组件，不一次跑完整装配的全部组合。

### 前置与准确调用

1. 在 SolidWorks 中打开装配并结束在位编辑，选择 2–5 个已解析的**叶零件实例**。记录 SHA、软件版本、PID、token、配置、dirty、选择、显隐和位姿。保持模型/配置不变；使用实际完整 occurrence_path，不使用文件名代替实例路径。子装配容器不能作为距离目标，内部叶零件可以。
2. 采集**带包围盒**的完整空间原始 envelope：

```powershell
python -m cadkin spatial-export --page-size 5 --output outputs/spatial-0.10.json
```

不要加 `--without-boxes`。确认 collection_complete、hierarchy_complete；缺少单个包围盒时允许部分结果，但该实例必须列为未知。若层级/分页不全，先收齐；不能把一页当完整输入。

3. 调用 **cad_proximity_candidates**。下面实例路径换成清单中的真实路径，5 mm 仅为首次探索筛选值，不能作为工程间隙或误差标准：

```json
{
  "inventory_path": "outputs/spatial-0.10.json",
  "output_path": "outputs/proximity-0.10.json",
  "max_box_gap_mm": 5,
  "occurrence_paths": ["实际完整实例路径A", "实际完整实例路径B"],
  "max_pairs": 100,
  "max_candidates": 20
}
```

默认 max_pairs=20000、max_candidates=200；本轮先缩小范围。读取输出 JSON 的 candidates、unranked_occurrences 与 coverage。包围盒重叠不等于零件接触。若没有候选，记录范围内空清单；只能明确调整探索阈值重算新文件，不能伪造组件对。也可以直接独立测量指定两实例。

4. 对少量返回候选逐个调用 **sw_component_distance**；一次只测一对，参数中的顺序对应 point_left/point_right：

```json
{
  "expected_document_token": "实际24字符token",
  "left_occurrence_path": "实际完整实例路径A",
  "right_occurrence_path": "实际完整实例路径B"
}
```

保存每次**完整原始 envelope**（schema_version/status/data/errors），例如 outputs/distance-ab-0.10.json。API 无解/失败的 partial 文件也保留；致命 error 且 data=null 的文件只作为错误记录，不传给复核伪装成测量。

5. 调用 **cad_review_proximity**，每对仅传一个距离文件。0.1 mm 同样只是明确标注的探索阈值，实际工程阈值由模型与需求决定：

```json
{
  "proximity_path": "outputs/proximity-0.10.json",
  "distance_paths": ["outputs/distance-ab-0.10.json"],
  "output_path": "outputs/proximity-review-0.10.json",
  "contact_tolerance_mm": 0.1
}
```

已有原始文件时可纯离线运行，不启动 CAD。等价 CLI（阈值仍为探索值）：

```powershell
python -m cadkin proximity outputs/spatial-0.10.json --occurrences "实际完整实例路径A" "实际完整实例路径B" --max-box-gap-mm 5 --output outputs/proximity-cli-0.10.json
python -m cadkin review-proximity outputs/proximity-cli-0.10.json --distances outputs/distance-ab-0.10.json --contact-tolerance-mm 0.1 --output outputs/proximity-review-cli-0.10.json
```

所有输出使用新名称，不覆盖原始来源。

### 每项怎么验证

| 新增项 | 核对与通过标准 | 失败或未测试标准 |
| --- | --- | --- |
| 待测组件对 | 两条路径确属所选叶实例；coverage 与实际范围一致；近似盒值只作测量顺序。缺包围盒的实例进入 unranked_occurrences，partial 保留。 | 用盒体重叠确认接触、把缺失写零、把范围外说成不连接均为失败。 |
| 单对最小距离 | 在 SolidWorks“测量”中使用同一对组件的最小距离模式对照，记录界面选择类型/模式/精度与值。distance_m × 1000 与 distance_mm 一致，最近两点间距与标量一致；至少核对一组明显分离的实例。 | 圆柱轴线/中心距或不同选面模式不能代替组件最小距离基准；界面无法选同类型对象时记录未测试，不强行判通过。数值容差需按界面精度明确记录。 |
| 最近点与实例坐标 | 对根装配坐标可核验的简单目标核对 XYZ，重复实例及嵌套实例分别测试；point_by_occurrence_mm 应按真实实例对应。只交换左右目标时距离应一致、点所属实例互换（多解时允许不同有效最近点）。 | 不再乘 Transform2；错用零件局部坐标/重复实例为失败。无可核验点位时最近点坐标分支记未测试。 |
| 近接触复核 | 已测距离 ≤ contact_tolerance_mm 为 near_contact_candidate，大于为 separated_at_measurement；保留标量、点、原始哈希和时间。requires_review=true、两个 confirmed 字段为 false。 | 零/小距离不能区分接触、穿透或包含；正距离也不证明无机械关联。不得关联到未经核对的某对圆柱面。 |
| 失败与未测 | API 无解/异常的原始 partial → unresolved、measurement=null；清单内未提供距离文件的对 → unmeasured，整体 partial。 | 错误/未测写成零或完整空结果为失败。不存在可用测量时只记录工作清单/错误，不编造文件满足输入数量。 |
| 范围与预算 | 在确有多于一对可检查时另存 max_pairs=1 的结果；确有多于一条候选时另存 max_candidates=1。应保留预算错误、truncated 与已处理范围。 | 预算仅检查路径顺序前缀，不得声称找到了全局最近对；恰好处理完无需截断。 |
| 来源一致性 | Get-FileHash -Algorithm SHA256 核对空间、工作清单及原始距离文件；文档、配置、实例与位姿一致。反序重复同一对需 DUPLICATE_DISTANCE_SOURCE；范围外测量需 DISTANCE_OUTSIDE_SCOPE。 | 混用旧空间/工作清单/变换应拒绝，不写成功结果；不手改哈希/位姿绕过。JSON 副本负例仅验证文件逻辑，不算真实 CAD 测量。 |
| 目标与只读保护 | 同实例两端应 INVALID_ARGUMENTS，子装配应 NOT_PART_COMPONENT，过期 token 应 DOCUMENT_CHANGED。在位编辑应 IN_CONTEXT_EDIT_ACTIVE；工具不自动退出。调用后 dirty、选择、显隐、位姿、原文件哈希不变，随后正常查询可用。 | 不自动重建、解析轻化件、切配置、移动、保存。真实 API 失败仍需保留原始错误；单次 COM 仍可能阻塞，TIMEOUT 后先核对现场再重启 MCP，不连续盲重试。 |

每对记录真实参数、返回、耗时、界面截图或人工读数、单位/比较模式、误差及结论，存到 `outputs/acceptance-0.10-<时间>/` 新目录。逐项标记通过/失败/部分通过/阻塞/未测试。token 和哈希不证明几何从未变化；采集中不编辑、不切配置、不重建。API 替身和 Windows CI 均不代替这一步。

可直接告诉 OpenCode：

> 按 0.10.0 清单验收仓库 STEP 的组件距离和近接触候选。先选 2–5 个真实叶零件；用完整带包围盒清单筛选，逐对测量，再离线复核。筛选 5 mm、判读 0.1 mm 仅作本次探索值，记录在结果中。按任务加载独立 skill 和必要参考；保留 partial、未测与未知范围，列出我要在 SolidWorks 测量窗口核对的组件对，不修改原模型或确认运动副。

## 0.9.0：配合引用面核对

本节保留 **0.9.0 新增能力**；当前版本与工具数量按上方 0.12.0 检查。在已有 Conda 环境运行 `git pull --ff-only`、`python -m pip install -e ".[solidworks,templates]"`，退出并重启 OpenCode；调用会话工具核对 Python 解释器和 Conda 前缀。

### 前置与准确调用

1. 记录 SHA、SolidWorks 版本、PID、token、配置、dirty、选择及位姿。在当前装配挑选 2–5 个已解析叶实例，最好包含一条可在窗口核对引用面的根配合和重复实例。仅扫描这一小组；保持模型不编辑、不移动、不切配置、不重建。
2. 保存完整空间基准：`python -m cadkin spatial-export --page-size 5 --without-boxes --output outputs/spatial-0.9.json`。必须收齐层级/分页；输出名已占用则另取新名。
3. 逐个调用 `sw_component_cylinders`，参数为当前 expected_document_token、真实 occurrence_path、**include_face_references=true**。默认 max_bodies=50、max_faces=500、max_cylinders=100。保存完整原始 envelope 为新文件（例如 outputs/cylinder-a-0.9.json、cylinder-b-0.9.json）；核对 face_references_requested=true 和圆柱的 face_reference。
4. 用这些新圆柱文件及上述空间文件调用 `cad_component_relations` 重算关系。必填 inventory_path、cylinder_paths、output_path、distance_tolerance_mm、angle_tolerance_deg；探索值 0.1 mm/0.1° 必须注明，不当作工程公差。不能沿用绑定旧圆柱文件哈希的关系结果。
5. 调用 **sw_match_mate_faces**。下面的 token 和文件名必须换成第 2–3 步真实值；不手填几何或 ID：

```json
{
  "expected_document_token": "实际24字符token",
  "inventory_path": "outputs/spatial-0.9.json",
  "cylinder_paths": ["outputs/cylinder-a-0.9.json", "outputs/cylinder-b-0.9.json"],
  "max_candidate_faces": 100,
  "max_comparisons": 2000
}
```

该工具同时重新读取根配合，无需先调用 sw_mate_inventory。根遍历默认 max_features=2000、max_mates=200、max_entities=16、max_depth=32。原始 envelope 保存为 outputs/mate-faces-0.9.json（或另一个新文件），保留 status/data/errors。

6. 调用 **cad_review_connections**，relations_path 为第 4 步的新关系文件、mate_inventory_path 为第 5 步原始 envelope、output_path 为 outputs 内未使用的文件。等价离线 CLI：

```powershell
python -m cadkin review-connections outputs/relations-0.9.json outputs/mate-faces-0.9.json --output outputs/connections-0.9.json
```

### 每项怎么验证

| 新增项 | 核对与通过标准 | 失败或未测试标准 |
| --- | --- | --- |
| 圆柱持久引用 | 已知圆柱记录包含 base64 face_reference；捕获时解析回读成功。半径/实例位置仍与原圆柱验收一致；默认不请求时仍正常读取。 | 引用失败应保留几何、null 引用和 partial；不能把编号当持久身份。 |
| 具体面对应 | 在 SolidWorks 查看一条已知根配合的引用面，人工核对返回实体的完整实例、body/face 源记录及 matches。两个实体确实对应同一候选两端时，离线 candidate_face_matches 指向正确几何候选索引。 | 只因同轴/同半径或同实例对就确认面相同为失败。模型无可核对根配合时记未测试。 |
| 重复实例/不同面 | 有重复实例或同轴分割面时，核对配合引用的具体实例与面；同几何的另一个面不能自动被匹配。 | 错绑定另一实例/另一个面为失败；缺少案例记未测试。 |
| 配合状态独立 | 即使面身份已对应，抑制/回滚/特征错误仍保留；requires_review=true、mechanical_relation_confirmed=false。 | 面匹配被解释成接触、有效求解、运动副或行程为失败。 |
| 非面/范围外/空配合 | 非面为 not_face，未提供实例为 outside_scope；成功读到空根配合时 mate_count=0、comparisons=0，保留 unvisited_occurrences。 | 空列表不能证明面解析/匹配分支已验收，不能推断无连接。 |
| 预算与部分结果 | 实际比较量大于 1 时另用 max_comparisons=1；实际面数大于 1 时另用 max_candidate_faces=1。保存新 envelope，再离线复核。 | 应 partial/truncated 并保留已证实 matches、预算错误与未知范围；不得称完整整机结果。恰好达到且无剩余时无需 partial。 |
| 来源绑定 | 新圆柱文件须与关系和面匹配绑定一致，逐个 Get-FileHash -Algorithm SHA256 核对；旧文件缺少引用时应 FACE_REFERENCE_UNAVAILABLE。 | 混用旧关系与新圆柱应拒绝 INVALID_FACE_MATCH_SOURCE/EVIDENCE_MISMATCH，不创建复核文件。JSON 副本负例不算 CAD 实测。 |
| 失效/变化 | 自然遇到引用失效、参数变化或实例映射失败时保存完整错误；若需构造案例，仅用用户已有可丢弃工作副本单独进行。 | FACE_REFERENCE_UNRESOLVED/FACE_GEOMETRY_MISMATCH 保持未知；采集中变化被检测后应整次拒绝。没有案例则未测试，不改原 STEP 制造数据。 |
| 只读与错误恢复 | 比较 dirty、选择、显隐、位姿和原文件哈希；max_comparisons=0 应 INVALID_ARGUMENTS，随后正常只读查询可用。 | 不能自动重建、切配置、选择、移动或保存模型；TIMEOUT 后按通用规则核对现场再重启 MCP。 |

将真实参数、源哈希、原始返回、时间与逐项人工窗口结论保存到 `outputs/acceptance-0.9-<时间>/`。STEP 很可能没有配合；空配合路径通过时，具体面匹配仍标记未测试，使用已有含配合装配再验收。只验证活动根装配配合，不声称覆盖子装配内部配合或装配级切除几何。

可直接告诉 OpenCode：

> 按 docs/MCP_ACCEPTANCE.md 的 0.9.0 清单验收。选少量真实零件，采集带持久引用的圆柱原始文件，重算关系，调用 sw_match_mate_faces，再离线复核。只加载当前职责的 skill 和必要参考文件。保留 partial、未知范围和配合状态；列出需要我在 SolidWorks 核对的具体配合和面。没有配合就明确标记面匹配未测试，不修改原模型。

## 0.8.0：配合状态与连接复核

本节保留 0.8.0 引入的两项能力：只读根配合采集与离线关联。当前安装版本/工具数量按上方 0.12.0 检查，skill 参考文件仍按需加载。

### 前置与调用

- 保持同一活动装配/配置和几何不变，记录 SHA、软件版本、PID、token、dirty、选择/显隐。先完成 0.6.0 原始读取及 0.7.0 几何候选的必要核对。
- 测试 STEP 若无配合，可验证空根配合与 geometry_only。非空、抑制、错误或嵌套引用案例需用户已有可核对的装配/outputs 工作副本；不修改原 STEP 制造数据，不具备就记未测试。
- 调用 `sw_mate_inventory`，传当前 expected_document_token；默认 max_features=2000、max_mates=200、max_entities=16、max_depth=32。保存原始 envelope 为 outputs 下未使用的 mates 文件，不能只保存 data。
- 对同次稳定模型采集的几何候选，调用 `cad_review_connections`，传 relations_path、mate_inventory_path、output_path。原空间/圆柱源文件须保留。CLI 等价：

```powershell
python -m cadkin review-connections outputs/relations.json outputs/mates.json --output outputs/connections-0.8.json
```

### 逐项验收

| 项目 | 通过标准 | 失败/未测试标准 |
| --- | --- | --- |
| 根配合及状态 | 与根配合文件夹的名称/类型核对；可观察的抑制/回滚/特征警告与 activity 一致。无特征错误保留 solver_validity=not_evaluated。 | 漏掉抑制记录却称完整，或把状态读取失败补成未抑制。没有适当状态案例则记未测试。 |
| 配置/引用/坐标 | 选一条已知根配合，核对实体引用的完整实例；verified_root_occurrence 需 IsSame 身份证据；EntityParams 保持根装配原始参数。 | 按短名称匹配错误重复实例、重复乘父矩阵，或把选择类别当圆柱类型。 |
| 嵌套范围 | 有根配合引用嵌套零件时核对引用路径；确认 subassembly_internal_mates_included=false。 | 把根引用误报为子装配内部配合已遍历。不存在该案例记未测试。 |
| 空值/失败/预算 | 无配合且遍历成功时完整空列表；对多配合用 max_mates=1、max_entities=1 或 max_features=1 另写文件，按实际未读量检查 partial/truncated 和 LIMIT。 | 入口失败冒充空列表、达到预算仍宣称全量；总数恰好达到上限不应误报截断。 |
| 实例对复核 | 与原关系候选索引、配合 feature_id 对照；抑制/报错/未知记录保留，状态按接口口径区分。 | 未知或抑制记录变成 has_unsuppressed_mate_evidence；面候选数被说成机械连接数。 |
| 关联边界 | requires_review=true、mechanical_relation_confirmed=false、face_match_confirmed=false；多组件/未匹配记录保留 unmatched_mates。 | 宣称同一实体面已匹配、运动副已确认、无配合就可自由移动。 |
| 来源一致性负例 | 仅复制验收 JSON，新副本修改 mate 的文档 token/引用配置/transform.raw_array 平移值，另算新输出。也可在圆柱源副本添加空白，使哈希改变。 | EVIDENCE_MISMATCH 且不创建输出才通过；这是离线负例，不是实机读取证明，不改原始证据/CAD。 |
| 错误与文件保护 | max_mates=0 应 INVALID_ARGUMENTS；重用输出名应 OUTPUT_EXISTS；正常工具随后仍可用。自然发生状态变化保留 MATE_STATE_CHANGED，不强行制造 CAD 变动。 | 覆盖已有结果或错误后服务不能正常响应。TIMEOUT 单独检查现场。 |
| 只读与离线 | 采集前后文档/配置/dirty/选择/显隐/位姿不变；已有文件后 review-connections 无需启动软件。 | 启动额外会话、切配置、重建、改配合或保存模型。 |
| Skill 分层 | 常规任务只选择对应入口；字段不明才读取相应 reference。已有文件时连接复核直接离线运行。 | 强制加载全套 skill/全部参考文件，或者离线任务强制启动/采集 CAD。 |

保存实际参数、原始返回、时间、文件哈希及人工窗口结论到 `outputs/acceptance-0.8-<时间>/` 新目录。逐项写通过/失败/部分通过/阻塞/未测试，空 STEP 验证不能替代非空配合读取验证。

可直接交给 OpenCode：

> 按 0.8.0 验收读取当前根装配配合清单，核对抑制、特征错误和引用实例；与已有几何候选离线关联，保存原始证据与待复核实例对。只有缺少输入时调用对应采集能力，参考文件按需读取，不加载全套 skill。不修改模型，不确认运动副；测试 STEP 没有配合时如实报告，并列出尚未覆盖的验收项。

## 0.7.0：组件关系候选

0.7.0 新增第 20 个工具 `cad_component_relations`，流程独立于角色分组和 COM 读取。先按下方 Conda 命令更新并重新启动 OpenCode，核对版本 **0.18.0 / 44 个工具**（本节保留 0.7.0 新增项）。软件启动/显示修复、空间和圆柱的实机核对仍分别执行原有清单。

### 采集与调用

1. 选择一条实际升降链上的 2–5 个已解析叶实例，从树中取完整路径。优先包含在窗口可核对的同轴件、平行但偏移的件、重复实例；模型中没有相应案例时记未测试，不能臆造路径或用演示数据冒充。
2. 保持同一会话/文档/配置，采集期间不编辑、不移动、不切配置、不重建。记录 SHA、Python/SolidWorks 版本、PID、dirty、选择/显隐及采集时间。
3. 用 `python -m cadkin spatial-export --page-size 5 --without-boxes --output outputs/spatial-0.7.json` 保存完整空间基准；collection_complete/hierarchy_complete 必须为 true，truncated=false。可先生成独立分组文件，非必需。
4. 用 `sw_component_cylinders`，逐个传当前 expected_document_token、实际 occurrence_path；每个实例原始 envelope 保存到 outputs 新文件。CLI 的 `sw ... --output` 可直接保存，参数组织参照 0.6.0 清单；不要根据聊天摘要手写几何值。核对至少一个圆柱面的真实半径/轴向和实例位置。
5. 明确公差。以下 0.1 mm、0.1° 是探索值，验收记录必须注明；已有工程公差时改为相应值。使用刚保存的真实文件，不能直接运行不存在的 a/b 示例路径：

```powershell
python -m cadkin relations outputs/spatial-0.7.json --cylinders outputs/cylinder-a-0.7.json outputs/cylinder-b-0.7.json --distance-tolerance-mm 0.1 --angle-tolerance-deg 0.1 --output outputs/relations-0.7.json
```

对应 MCP：`cad_component_relations`，inventory_path、cylinder_paths 数组、output_path、distance_tolerance_mm=0.1、angle_tolerance_deg=0.1；默认 max_pairs=10000、max_candidates=1000。可另传 grouping_path，与空间文件 SHA256 不符时应拒绝。

### 每项怎么验证

| 验收项 | 操作与通过标准 | 失败标准 |
| --- | --- | --- |
| 候选与数值 | 读结果文件的 candidates，按完整实例对照窗口/测量。已知同轴样例角度/参考偏移均在阈值内；平行偏移样例应角度合格、偏移超限。保留实际测量方法、公差与误差。 | 错实例、重复乘父矩阵、米/毫米混淆，或将明显不满足阈值的轴列为同轴。模型无合适可核验样例则记未测试。 |
| 溯源与范围 | sources 文件哈希可按 Get-FileHash -Algorithm SHA256 核对；结果 inventory_sha256 与空间文件一致。coverage.scope=provided_occurrences_only；body/face 索引回指相应源记录。 | 把 2–5 个输入描述为整机全部关系，或将分割面配对数描述为连接数。 |
| 结果含义 | 所有候选 status=candidate、mechanical_relation_confirmed=false；requires_review=true。远距离同轴/平行、不同半径均只说明轴的几何关系，人工检查有限面/装配修改。 | 自动改为旋转副/直线副、认为已接触或求出行程。 |
| 部分来源 | 对确有更多面的实例用较小 max_faces 另读原始返回，包含该 partial 文件另算新结果。 | 应 status=partial、SOURCE_INCOMPLETE，源错误保留；即使 comparison_complete=true 也不得 complete=true。缺少可触发案例记未测试。 |
| 计算上限 | 对总面配对数大于 1 的输入，用 max_pairs=1 另写新结果；可再测试 max_candidates=1。 | 应 partial、RELATION_LIMIT、truncated=true、checked_pairs 小于 total_possible_pairs。若恰好总数为 1，应完整而非误报截断。 |
| 空圆柱/无候选 | 自然遇到没有解析圆柱或不同轴向时核对 sources 和 coverage。 | 不补造轴线、不将零候选解释为没有运动关系；零面实例应列于 zero_cylinder_occurrences。 |
| 混用来源 | 仅对验收 JSON 的新副本改 document_token 或 transform.raw_array 中的平移值，或者提供另一空间清单生成的分组；不要改原始记录或 CAD。 | 应 EVIDENCE_MISMATCH 且不创建输出；允许篡改数据穿过校验或创建混合结果为失败。此项是离线负例，不是实际 CAD 实测。 |
| 文件/参数 | 对同一输出名再调用；换新输出名并传 angle_tolerance_deg=0。错误后调用正常离线工具或列工具。 | 应分别 OUTPUT_EXISTS、INVALID_ARGUMENTS，文件不被覆盖、不创建错误结果，MCP 仍可用。 |
| 离线与不修改 | 已有证据后可在不启动 SolidWorks 的情况下单独跑 relations；若软件已开，对照 dirty、选择、显隐和位姿。 | 不应启动/连接 COM，不移动/保存/重建；原始 STEP、空间/圆柱/分组文件字节不变。 |

将准确工具参数、原始输入/输出路径和哈希、时间、公差说明、人工测量/窗口结论保存到 `outputs/acceptance-0.7-<时间>/`。逐项写“通过/失败/部分通过/阻塞/未测试”，不要把离线负例或协议测试当作真实模型数值已验收。

可直接交给 OpenCode：

> 按 docs/MCP_ACCEPTANCE.md 的 0.7.0 清单，在测试升降机的一条链上选少量实际零件，保存完整空间基准和各实例圆柱原始返回；用明确标为探索值的 0.1 mm、0.1° 生成同轴/平行候选。保留源哈希、角色上下文、部分来源和预算状态，列出需要我窗口/测量核对的实例与数值。不要修改模型，不自动确认运动副。

## 0.6.0：Conda与约束轴线证据

### Conda 环境与协议

以下命令在仓库根目录、你已有 Conda 环境中执行，环境名替换为本机名称。无需创建项目虚拟环境：

```powershell
conda activate 你的环境名
git pull --ff-only
python -m pip install -e ".[solidworks,templates]"
python -c "import sys; from importlib.metadata import version; print(sys.executable); print(version('3dmodel-rcgn'))"
opencode mcp list
opencode
```

当前版本应为 0.17.0，工具数 43（本节保留 0.6.0 新增项）。升级后要从同一已激活终端重新启动 OpenCode。调用 `sw_session_status({})`，核对 runtime.python_executable 与终端打印路径一致、matches_conda_prefix=true；软件未运行时 connected=false 也应带这些字段。与目标 Conda 不符即本项失败，不继续把其他环境的测试当作通过。配置不硬编码环境名称或机器路径。

### 两个新工具逐项验收

前置：活动文档为测试装配，先读 sw_active_document 和 sw_component_tree，保存实际 token 与完整实例路径。挑一个顶层实例、一个嵌套实例，以及能在窗口确认的圆柱零件。原 STEP 没有配合时可以验证空列表；含已知配合的成功读取须用用户已有合适装配/工作副本，不修改原 STEP 来制造数据。所有操作串行，保存真实参数/原始 JSON/版本/PID/耗时与窗口结论到 `outputs/acceptance-0.6-<时间>/`。

| 项目 | 操作与准确参数 | 通过标准 / 失败标准 |
| --- | --- | --- |
| 顶层固定标志与配合 | `sw_component_constraints`：expected_document_token=当前值、occurrence_path=实际顶层路径；默认 max_mates=100、max_entities=16。 | fixed_state.value 与该实例特征树固定/浮动标志一致；reported_mate_count/read_mate_count 与实际关联记录核对。配合类型、引用名称和原参数保留；不自动生成自由度、刚体或运动副结论。 |
| 嵌套状态 | 相同工具换成实际嵌套路径。 | fixed_state.value=null，errors 含 FIXED_STATE_CONTEXT_UNAVAILABLE，整体 partial；不会读取错误上下文后声称子件浮动，不切换/激活子装配配置。 |
| 有配合样例 | 在已有可核验配合的装配里查询对应组件；核对至少一个同心/重合等已知配合。 | type_code/type_name 与对应配合一致，entity_count 和引用名称可核对；记录坐标所属装配，不把 EntityParams 当根坐标。无法提供该样例时记未测试，不能用 STEP 空列表代替。 |
| 空值与失败 | 对实际无配合组件查询；自然遇到读取错误时保留原错误。 | 正常空值为 mates=[]、reported_mate_count=0；读取失败必须 partial、mates=null 或对应记录带 errors，不能冒充空列表。没有配合不等于自由运动。 |
| 圆柱面几何 | `sw_component_cylinders`：当前 token、实际已解析圆柱零件路径；默认 max_bodies=50、max_faces=500、max_cylinders=100。 | 至少一个已知解析圆柱面的半径与人工测量一致（注意半径/直径差别），原点在轴线上、方向与该轴平行；源配置匹配、米/毫米正确。标明零件定义范围，不说已包含装配级切除。若导入面是 NURBS，0 条需注明当前不识别，不能强报通过。 |
| 重复/嵌套实例 | 读取同文件不同位置的两个实例，尽量包含嵌套实例；对照 sw_component_spatial 的 Transform2。 | 共享零件定义不合并实例；局部参数相同而根位置/方向随实例正确变化；不重复乘父变换、不把轴点当中心。方向反向表示同一无向轴，不直接当运动正方向。 |
| 不匹配配置/未加载/子装配 | 存在相应现场条件时查询，保留当前文档和配置。 | 分别 COMPONENT_CONFIGURATION_MISMATCH、COMPONENT_MODEL_UNAVAILABLE、NOT_PART_COMPONENT；不自动打开/解析/切配置。条件不具备记未测试，不人为破坏模型。 |
| 上限/缺失 | 对确有多配合/多面的实例分别用 max_mates=1、max_entities=1、max_faces=1 或 max_cylinders=1。 | 未读完时 partial/truncated=true 与对应 LIMIT 错误，已读数据保留。实际恰好读完不应误报截断。失效字段不补零轴、零半径或单位变换。 |
| 只读与错误后可用 | 调用前后比较活动文档/配置、dirty、选择和显隐；分别传过期 token、max_faces=0。 | 没有选择、移动、重建、保存或修改配合；错误分别 DOCUMENT_CHANGED、INVALID_ARGUMENTS，之后正常查询仍可用。TIMEOUT 另按现有规则核对现场。 |

保存参数后也可由共享 CLI 写原始结果：`python -m cadkin sw sw_component_constraints --arguments '<实际JSON>' --output outputs/constraints-0.6.json`；圆柱工具同理。JSON 中必须使用刚读取的 token 和真实路径，不粘贴占位值；文件已存在则改名。优先让 OpenCode 组织实际参数以避免 PowerShell 引号转义问题。

可直接交给 OpenCode：

> 按 docs/MCP_ACCEPTANCE.md 的 0.6.0 清单检查当前 Conda 解释器与 MCP 一致，再读取测试装配中一个顶层实例和一个嵌套实例的约束，以及一个已知圆柱零件和其重复实例的轴线/半径。保存原始 JSON、真实参数和耗时；列出需要我窗口核对的结果。固定标志不等于机械角色，没有配合不等于自由运动，圆柱轴不直接认定为运动轴；不要切换配置、修改配合、移动或保存模型。

## 0.5.0：修复与组件分组

### 更新与证据

```powershell
git pull --ff-only
python -m pip install -e ".[solidworks,templates]"
python -c "from importlib.metadata import version; print(version('3dmodel-rcgn'))"
```

本节保留 0.5.0 的修复验收项；当前更新应显示 0.18.0、44 个工具（0.5.0 时为 17 个）。退出并重新启动 OpenCode，确认含 `cad_group_components`。若仍为 15 个工具或仍报旧的 60 秒上限，先核对所用目录、解释器与 MCP 进程。使用已有打开的测试装配，记录 SHA、软件版本、PID、当前文档/配置/token，以及修改前的选择/显隐/dirty。不要为测试关闭有未保存工程的会话。

每次工具调用保存准确参数、原始返回、开始/结束时间与人工窗口结论到 `outputs/acceptance-0.5-<时间>/`。回读、耗时、窗口效果分别记录；没有窗口证据不填写视觉通过。

### 三个问题复测

| 项目 | 操作 | 通过标准 / 失败标准 |
| --- | --- | --- |
| 显示常量加载 | `sw_get_display_state({})`；然后用当前 token 调用 `sw_set_display_visibility`，target=planes、visible=false；再读状态；最后按记录恢复原类别值。 | 无不存在 LoadTypeLibEx 的错误；planes 回读 false，重复隐藏 changed=false、不会反向切换；返回 redraw_requested=false，其他类别不变。窗口核对辅助面是否隐藏。若总屏蔽影响恢复，记录 DISPLAY_BLOCKED，不擅自改变总开关。 |
| 组件显隐等待 | 从 `sw_component_tree` 取一个已解析叶实例完整路径，先读其显隐；调用 `sw_set_component_visibility` 改为 false，再 `sw_get_component_visibility`；恢复原状态。 | 设置工具本身正常返回，visible 回读匹配、saved=false、redraw_requested=false；当前选择与其他重复实例不被改写。记录实际耗时，不能仅凭之后查询已隐藏就判设置通过。若仍 TIMEOUT，则标部分/失败并记录实例、耗时、弹窗；不要重复执行直到检查现场。 |
| 单页读取 | 当前 token，`sw_spatial_inventory` 参数 page_size=5（max_components=5000、max_depth=64）。 | 本页最多 5 项；实际组件多于 5 时 has_more=true、next_offset=5、collection_complete=false；total_components 与范围内树数量一致。接续 offset=5、expected_inventory_signature=首个签名，其他参数不变。单页 GetBox 不跨全装配循环。 |
| 完整分页导出 | 用下方 CLI page-size=5 导出，整个过程不编辑/重建/切换配置。 | collection_complete=true、hierarchy_complete=true、truncated=false；组件路径集合与同配置完整树一致且无重复，数量以当次实读为准（截图 254 不是硬编码标准）；无字段错误时 complete=true。抽查至少 3 个实例与 `sw_component_spatial` 一致，按 0.3.0 表核对坐标/盒。任何页失败时保存部分数据且 collection_complete=false，不误报完整。 |
| 跳过包围盒 | 另用新文件，加 `--without-boxes` 导出。 | bounding_boxes_requested=false，所有 bounding_box=null、bounding_box_status=not_requested，变换仍保留。没有包围盒不能伪装零尺寸；此文件可用于初步角色候选，但没有近邻盒中心提示。 |
| 分页错误 | 后续 offset>0 故意不传签名；或传入 64 个零的签名。 | 分别 INVALID_ARGUMENTS、INVENTORY_CHANGED；服务仍可查询活动文档。不要为测试主动改动原模型；自然遇到层级/配置变化时保留真实错误。 |

```powershell
python -m cadkin spatial-export --page-size 5 --output outputs/spatial-0.5.json
python -m cadkin spatial-export --page-size 5 --without-boxes --output outputs/spatial-fast-0.5.json
```

已存在文件需改名，不能覆盖。完整导出可能超过 180 秒，这是多个独立页的累计时间；调用 CLI 的终端/Agent 需允许足够的命令执行时间。单页仍超时时先核对现场、重启 MCP，再用 page-size=1 或 without-boxes 和新文件复测；也可能是单个组件 API 阻塞，不能承诺分页一定消除所有卡顿。

### 新增分组与修正

```powershell
python -m cadkin group outputs/spatial-0.5.json --output outputs/groups-0.5.json
```

MCP 等价调用：`cad_group_components({"inventory_path":"outputs/spatial-0.5.json","output_path":"outputs/groups-mcp-0.5.json"})`。详细 JSON 已写入文件，返回精简摘要；不要求从聊天输出重建文件。

| 项目 | 操作 | 通过标准 / 失败标准 |
| --- | --- | --- |
| 候选覆盖与证据 | 读 groups JSON 与源清单，检查每个 role/members/evidence；抽查固定/移动/传动候选或待确认实例。 | 四类计数之和等于 coverage.scoped_leaf_occurrences；每个叶实例出现一次，子装配容器另计，同文件重复实例未合并。自动结果仅 candidate/pending，manual_confirmed_count=0；数值/路径来自输入。匿名或冲突名字可以全部 pending，不以“猜出多少类”评估成功。 |
| 范围选择 | 从真实树中选定一个子装配路径，CLI 加 `--scope "实际路径"`，输出换新文件。 | 只有该实例的叶子后代（若本身是叶则仅该实例）被分配，未混入其他升降链；范围不存在时报 COMPONENT_NOT_FOUND。不要仅靠名称假定此范围就是某条运动链。 |
| 几何辅助 | 抽查成员的 spatial_context 和 nearest_box_centers。 | 源变换/盒字段保持一致，距离为近似盒中心距离；缺盒无近邻提示，不把原点当中心，不把接近认定接触/碰撞/同刚体。 |
| 人工确认/纠正 | 在窗口按完整路径选中一个实例核对；用户明确确认后，按 TOOL_CONTRACTS 格式写 review JSON，再用同一源/范围加 `--review` 和新输出文件。 | 只有指定叶实例变为 manual_confirmed 或显式 pending，reason 保留实际依据；其他候选不变。inventory_sha256 与原始源文件一致；源变了则拒绝 INVALID_REVIEW。确认角色不改变 rigid_body_confirmed=false。 |
| 不完整输入 | 将单页原始返回保存新 JSON，再调用分组工具。 | GROUPING_REQUIRES_COMPLETE_INVENTORY，且没有写出分组文件；单页不能冒充整机。单独缺失几何、层级完整的输入可产生 partial 分组并保留 source_errors。 |
| 文件与模型保护 | 对相同 output_path 再次调用；查询 CAD 状态，并核对原输入哈希。 | OUTPUT_EXISTS，原输出和输入不变；分组本身不选择、不显隐、不移动、不改 dirty 或保存 CAD，也不创建新 SolidWorks 进程。 |

可直接交给 OpenCode：

> 按 docs/MCP_ACCEPTANCE.md 的 0.5.0 清单验证本次修复和组件分组。使用当前测试装配，记录显示与组件原状态，复测隐藏并恢复；按每页 5 个组件导出全部空间清单，核对实际实例路径集合，然后生成角色候选并报告待确认项。保存准确参数、原始 JSON 和耗时到 outputs 新目录，窗口效果与 API 回读分别列出。不要自动确认分组、编辑几何或保存覆盖原模型；超时先检查现场，不连续重试。

## 0.4.0：自动启动 SolidWorks

新增第 16 个工具 `sw_start_application`，默认参数 `{}`，可选 `wait_seconds=120`。仅维护 Windows；CI 只保留 Windows / Python 3.10、3.12。启动操作与打开模型分开，按下面顺序核对：

| 场景 | 操作 | 通过标准 |
| --- | --- | --- |
| 冷启动 | 软件原本未运行时，先调用 `sw_session_status`，再调用 `sw_start_application`；不要为制造场景关闭有未保存内容的工程。 | 状态查询返回 connected=false 且不启动；启动返回 started=true、startup_completed/visible/user_control=true，窗口真实出现，任务管理器只有一个目标 SLDWORKS.exe，PID 与返回一致。 |
| 打开模型 | 在同一会话调用 `sw_open_document` 打开仓库 STEP，再读取活动文档及组件树。 | 模型显示，目标文档正确；实际导入类型如实记录，没有要求用户先手动启动。 |
| 重复调用/已有会话 | 记下 PID、文档、选择及 dirty，连续再调用两次启动工具。也可在原本已运行的会话直接测试。 | started=false、reused_existing=true，PID 不变且无新增实例；当前文档、选择、dirty 不因启动工具变化。应用窗口可能被显示。 |
| 退出客户端 | 在上述成功启动后退出 OpenCode，检查 SolidWorks；再进入 OpenCode 查询。 | SolidWorks 和当前模型仍保留，再次连接返回同一 PID；未执行关闭或保存。 |
| 启动阻塞 | 若实际遇到许可/恢复/插件弹窗，保存原始错误和窗口现象。 | 未完成不得记成功；STARTUP_PENDING 处理弹窗后复用已有进程；TIMEOUT/OUTCOME_UNKNOWN 先检查现场并重启 MCP，不反复新建。未遇到则此项记未测试。 |

保存到 `outputs/acceptance-0.4-<时间>/`：提交 SHA、Windows/Python/OpenCode/SolidWorks 版本、每次参数与原始返回、PID 和人工窗口结论。不要通过自动关闭现有工程来制造冷启动场景；有未保存模型时先验证复用，冷启动项目留待合适时机。

可直接交给 OpenCode：

> 按 docs/MCP_ACCEPTANCE.md 的 0.4.0 清单验证启动功能。如果 SolidWorks 尚未运行，使用 sw_start_application 启动；已有会话就复用。打开仓库的测试 STEP，记录 PID 和活动文档，然后再调用启动工具确认不会重复开进程。把原始结果保存到 outputs 的新目录，列出需要我核对的窗口和退出客户端后的保留状态。不要关闭或保存我的其他工程。

## 原有 8 个工具逐项检查

按表中顺序串行执行。对视图、选择、清空和重建，先调用 `sw_active_document`，把返回的 `document_token` 原样传为 `expected_document_token`；不要编造 token，也不要在调用中切换文档或配置。

| 顺序 | 工具 | 实机通过标准 |
| --- | --- | --- |
| 1 | `sw_session_status` | `status: ok`、`connected: true`；`process_id` 与目标 SolidWorks 进程相符，`revision` 有效。只有协议连接或 `connected: false` 不算通过。 |
| 2 | `sw_open_document` | 输入 `examples/three_servo_lift/3X Lift Assembly.STEP`；模型确实显示且成为活动文档，返回的 `source_path`、`document` 与窗口一致。记录实际导入为装配还是零件，不根据扩展名推断。 |
| 3 | `sw_active_document` | 标题、路径、文档类型、配置及 dirty 状态与当前模型相符，返回 24 字符 `document_token`。导入时路径以 SolidWorks 实际报告为准，并与打开工具返回值核对。 |
| 4 | `sw_component_tree` | 装配输入返回 `status: ok`、`complete: true`；实例路径和父子层级正确，同文件的重复实例分别保留，根装配不计入 `component_count`。与特征树核对至少 3 个实例，尽可能覆盖重复实例与子装配。 |
| 5 | `sw_set_view` | 用 `view: "isometric"`、`fit: true` 调用成功，窗口确实切到等轴测并完整显示模型。仅有 API 完成消息不足以确认视觉结果；起始视角相同时先切到 `front` 再验证。 |
| 6 | `sw_select_component` | 从组件树选一个可读取、未抑制实例的完整 `occurrence_path`；返回路径一致、`selected_count: 1`，窗口/特征树选中的是该实例。不能只按零件文件名选择。 |
| 7 | `sw_clear_selection` | 紧接选择操作调用；`selected_count: 0`，窗口与特征树中的选中状态清除。 |
| 8 | `sw_rebuild` | 在工作副本上执行，返回 `rebuilt: true`、`saved: false`，活动目标仍正确；记录重建后的 dirty 状态及窗口中的错误提示。dirty 不一定变成 true。API 返回成功不代表所有配合与几何均健康。 |

重建工作副本可在 PowerShell 中创建，再通过 `sw_open_document` 打开并重新取得 token。目标已存在时使用已有副本或另选文件名，不覆盖：

```powershell
New-Item -ItemType Directory -Force outputs | Out-Null
if (Test-Path 'outputs/acceptance_model.STEP') { throw '工作副本已存在，请复用或改名' }
Copy-Item -LiteralPath 'examples/three_servo_lift/3X Lift Assembly.STEP' -Destination 'outputs/acceptance_model.STEP'
```

如果 STEP 导入为多实体零件，打开和活动文档检查仍可通过；组件树应报告 `NOT_ASSEMBLY`，组件树/组件选择验收记为“阻塞”，先确认本机导入方式。树返回 `partial` 或 `complete: false` 时保留 errors，记为“部分通过”，不能宣称完整读取。手动打开后读取成功可以证明读取功能，但不能替代打开工具本身的验收。

## 0.2.0：显示控制（5 个工具）

已打开模型时，先记下当前状态，按以下顺序验收，不必为了测试重复打开模型。

| 顺序 | 工具 | 实机通过标准 |
| --- | --- | --- |
| 9 | `sw_get_display_state` | 返回基准面等 6 类开关和总屏蔽值，与界面“隐藏/显示”菜单一致；只读取，不改变画面。 |
| 10 | `sw_set_display_visibility` | 新取 token，`target="planes", visible=false` 后回读为 false，窗口中的基准面隐藏；重复隐藏保持隐藏。恢复记录的原值；其他类别开关不被改动。基准面原本不可见时，仅回读不能替代视觉验证。 |
| 11 | `sw_zoom_to_fit` | 当前非标准或用户选择的视角保持不变，模型缩放适合窗口。 |
| 12 | `sw_get_component_visibility` | 指定完整实例路径，返回自身显隐与隐藏父路径；与装配树中的状态一致。 |
| 13 | `sw_set_component_visibility` | 隐藏一个可解析组件，回读 false 且窗口消失；同文件的其他实例保留。重复隐藏不反向显示，按原值恢复。选择状态不因工具被清空。 |

基准面测试支持 STEP 导入后的零件或装配；组件显隐仅支持装配。测试“显示”时若总开关或父级仍隐藏，应明确报阻塞，不自动显示其他对象。想验证其他辅助类别时对相应 target 重复第 10 项；单个已隐藏特征不会被类别开关强制显示。

## 0.3.0：组件空间信息

本次新增 2 个只读工具。前提：先完成会话/活动文档检查，实际类型为 assembly；读取过程中不操作界面。先记录 dirty、选择及显隐状态。获得当前 token 后串行调用，所有记录存入 `outputs/acceptance-0.3-<时间>/` 新目录。

| 编号 / 新能力 | 怎么调用与核对 | 通过标准 |
| --- | --- | --- |
| 14 单实例空间查询 | 从 `sw_component_tree` 取完整路径；调用 `sw_component_spatial`，传当前 token 与该 `occurrence_path`。至少抽查 3 个实例，尽量包含同文件重复实例及嵌套子件。 | 返回目标和父路径与特征树相符；原点、变换及近似包围盒字段可读。已解析样本应为 `spatial_status=ok`，异常不得补成零值。 |
| 15 整机空间清单 | 调用 `sw_spatial_inventory`，传当前 token；保存完整原始返回为 `inventory.json`。再单独查询第 14 项三个实例，与批量记录对照。 | 正常完整输入 `status=ok`、`complete=true`、`truncated=false`；`component_count` 等于数组长度，根不计数、子装配计数，重复实例不合并。稳定模型下两种查询的对应字段一致；不能只比较数量。 |
| 坐标与单位 | 在 SolidWorks 中显示并定位被查组件的原点，以根装配坐标检查位置；核对已知基准点/方向。对嵌套子件计算父根矩阵 × 子局部矩阵。 | `_mm = 1000 × _m`，矩阵平移为 m；组合得到子件根矩阵（计算误差阈值 1e-8，仅用于矩阵一致性）。原点位置/方向还需独立人工核对，不能只靠矩阵互验。 |
| 近似包围盒 | 查看 `min_mm`、`max_mm`、`size_mm`，检查整机轴方向、位置与数量级，核对显著的 1000 倍单位错误或重复变换。 | `size=max-min`、非负有限，标为 approximate；不把它与零件局部长宽高或精密测量强行相等。无法核对边界准确性时单独标待验证。 |
| 不完整与缺失数据 | 对至少含 2 个实例的装配，用 `max_components=1` 调用整机工具，保存 `inventory-limited.json`；本机若已有轻化/抑制实例，再记录其字段。 | 限制案例应 `status=partial`、`truncated=true`、`complete=false`，保留节点和 `COMPONENT_LIMIT`；不可读字段为 null 并带错误，不自动解析。无轻化案例则该子项记未测试。 |
| 只读行为与错误 | 对照调用前后 dirty、选择、显隐、位姿；传入不同的 24 字符 token；以 `max_components=0` 调用；再做一次正常查询。 | 状态不因空间工具改变；错误依次为 `DOCUMENT_CHANGED`、`INVALID_ARGUMENTS`，随后服务仍可用。零件类型应 `NOT_ASSEMBLY`，空间验收记阻塞。 |

组件原点不是外形中心或质心；STEP 重复实例可能共用整机原点，不能据“位置为零/相同”判失败。若测试模型缺少可独立核对的嵌套旋转/平移，可另用本机坐标已知的小装配验证，并在记录中标明模型；不伪称已在升降机中覆盖。例如已知父级绕 Z 轴 90°、原点 (1000,2000,0) mm，子件相对父级位移 (200,0,0) mm，则子件整机原点应为 (1000,2200,0) mm。这是验算示例，不是升降机实测数据。

出现 null/partial 时先保存原始错误，区分“真实输入不完整”与“正常已解析组件读取失败”；后者记失败并反馈版本、实例路径、参数及错误码。`isError=false` 或 CLI 退出码 0 不等于数据完整。爆炸/临时展示位姿与基础模型坐标不同，需单独说明；这版不读取运动轨迹。

可直接交给 OpenCode：

```text
按 docs/MCP_ACCEPTANCE.md 中 0.3.0 的清单验证本次新增功能。
先检查当前 SolidWorks 会话、文档类型和 token；若尚未打开，打开仓库里的测试 STEP。
加载 component-spatial，调用 sw_spatial_inventory，保存完整原始返回。
从树里选至少 3 个实例，尽量包括重复实例和子装配中的子件，分别调用 sw_component_spatial。
对照批量/单件结果、单位和父子矩阵，再测试 max_components=1 的部分结果及错误 token。
把实际参数、原始返回和逐项结论保存在 outputs/acceptance-0.3-时间/。
列出需要我在 SolidWorks 窗口核对的位置、方向与近似包围盒；未经我核对的项目记待验证。
不要移动、重建、解析或保存覆盖模型；不要把部分结果、模拟测试或协议连通记成实机全部通过。
```

## 错误处理也要验证

- 给视图工具传入与当前值不同的 24 字符 token，应返回 `DOCUMENT_CHANGED`，窗口不应被切换。
- 用 `max_depth: 0` 调用组件树，应返回 `INVALID_ARGUMENTS`，MCP 保持可用；随后正常会话检查仍能成功。
- 条件具备时检查无活动文档的 `NO_ACTIVE_DOCUMENT`、零件输入的 `NOT_ASSEMBLY`。不要为测试关闭有未保存修改的文档。
- 如发生 `TIMEOUT` / `OUTCOME_UNKNOWN`，先核对窗口、弹窗及实际结果，结束阻塞后重启 MCP；不将超时当作操作已取消，也不盲目重复操作。

## 记录与结论

在 `outputs/` 的新目录保存验收记录、每次实际参数和原始 MCP 返回；视图与选择另附人工窗口核对结果。每项标记“通过 / 失败 / 部分通过 / 阻塞 / 未测试”，写明原因。只有 23 项都满足标准，才能说本版本基础能力实机验收通过。

可直接告诉 OpenCode：

> 按 docs/MCP_ACCEPTANCE.md，在当前 Windows 和 SolidWorks 上逐项验收 44 个 MCP 工具。测试模型已在 examples/three_servo_lift/3X Lift Assembly.STEP。串行调用，记录真实参数、原始返回和可观测的窗口现象及不确定项；重建使用 outputs 下的新工作副本，不保存覆盖原始输入。将结果存入 outputs 的新目录，不把模拟测试、协议连通或部分结果写成实机全部通过。

当前仓库已验证离线逻辑和真实 stdio 协议；用户已反馈旧版 15 个工具的实测状态，修复、分组、证据读取和本次关系候选仍需目标 SolidWorks 与 OpenCode 客户端验证。零件移动、配合编辑、CAD 文件保存/导出及机械运动副确认不在当前 45 个工具范围内；已包含几何关系候选；空间结果 JSON 可由客户端或 CLI 保存。

后续每次功能变更都在此追加对应版本的操作、预期返回、人工核对和失败标准。每条记录注明提交 SHA、工具参数、原始返回文件、窗口核对者与结论；没有证据不沿用上版“通过”。

## 0.22.0：目标约束组合分析

前置：Windows、已有Conda环境，拉取并安装最新仓库，重启OpenCode；46个工具，39个功能skill。无需新建.venv。离线验收不要求SolidWorks。

```powershell
git pull --ff-only
python -m pip install -e ".[solidworks,templates]"
python scripts/verify_constraint_analysis.py --output outputs/verify-0.22
```

预期passed=true、35项检查。九个合成场景覆盖lock、旋转/滑动/固定组合、不同位置平行轴、重复轴、无配合、几何冲突、旧版缺少几何字段；检查原始源不变、预算省略、禁止覆盖、重放和伪造结论拒绝。结果与调用在outputs/verify-0.22；重复运行换目录。此脚本使用显式CAD替身，真实stdio另有协议测试；均不等于本机SolidWorks或升降机实测。

### A. 已有目标图离线验收

在仓库根目录，使用当前真实target graph（下面路径是示例；不要手写目标图）：

```powershell
python -m cadkin analyze-constraints outputs/target.json --distance-tolerance-mm 0.1 --angle-tolerance-deg 0.1 --output outputs/constraints-0.22.json
```

等价MCP：
```json
{"tool":"cad_analyze_constraints","arguments":{"target_graph_path":"outputs/target.json","output_path":"outputs/constraints-0.22.json","distance_tolerance_mm":0.1,"angle_tolerance_deg":0.1,"max_pairs":200}}
```

0.1mm/0.1度是验收示例，真实任务按源精度选择并保留参数。检查：
1. 原始源被重放，报告target_source和input_files哈希可追溯。逐pair看snapshots，不把多个源文件拼成一个约束系统。
2. 支持/冲突/缺失分别在constraint_facts/candidates、conflicts、missing_evidence；candidate.evidence_ids能回到具体mate源、feature_id和entity_index。不同快照相同feature_id不能直接当同一观测。
3. 旧数据缺新字段时报告MATE_REFERENCE_GEOMETRY_MISSING_OR_UNSUPPORTED；缺旋转锁定状态时不能默认false。STEP无配合会有NO_USABLE_ACTIVE_PAIR_MATES或NO_ROOT_MATE_SOURCE，同时保留几何上下文；这是合理未知，不是必须匹配模板。
4. supported_local_pattern也仍target_joint_kind=unknown、target_degrees_of_freedom=null。报告不覆盖draft、不自动合并零件、不发起运动。
5. max_pairs=1时coverage明确省略，partial/CONSTRAINT_PAIR_LIMIT；原输出路径再次使用返回OUTPUT_EXISTS。改变任何已绑定源字节后重跑返回EVIDENCE_MISMATCH，不写新结果。

失败标准：只凭“导轨”名称/同轴/近接触/bench_vise swivel出现确定revolute；漏记录抑制/错误/边界约束；跨快照拼接；省略对当无连接；修改旧源、原STEP或CAD；声称已求出DOF。

### B. 本机增强配合采集验收

准备：当前装配与空间清单的文档token、配置、实例路径和位姿一致；否则先新采一致来源。记录窗口的dirty/选择/配置和目标配合的锁转设置，仅做核对，不切换它。取得sw_active_document的真实token，再调用：

```json
{"tool":"sw_mate_inventory","arguments":{"expected_document_token":"替换为真实24字符token","include_reference_geometry":true,"max_features":2000,"max_mates":200,"max_entities":16,"max_depth":32}}
```

将完整原始envelope保存为outputs/mates-geometry-0.22.json。检查reference_geometry_capture、每个具体面引用的root参数/持久身份回读，以及同心配合constraint_options.concentric_lock_rotation。面/实例/参数绑定成功不代表配合已求解；无法读取为null及错误，不能冒充false。若STEP无配合，完整空列表允许，不能为验收自行添加配合。

使用原关系文件和新mates文件调用cad_review_connections写新connections文件，再按原链parameters（保持成员/名称/分组/其它证据和公差，仅替换本次根mate连接源）调用cad_build_chain_evidence写新chain、cad_build_target_graph写新target，最后用A步骤分析新target。缺源/配置/位姿不一致时明确报错，不修旧哈希。

核对一条目标组件对，例如“端座—导轨”：记录真实完整occurrence_paths，查看哪些配合及具体面支持候选、缺哪些条件、是否有冲突。若只有几何观察，应保持未知。另有本机原生装配可核对现存同心配合+端面重合、锁转等组合；不要为测试改动用户模型。

预期窗口选择/dirty/位姿/配置保持原状，无修改配合或重建。变化被捕获时返回MATE_STATE_CHANGED/GEOMETRY_CHANGED/COMPONENT_CHANGED/DOCUMENT_CHANGED，混合快照不可用于分析。保存原始envelope、新派生JSON和结果，不仅保存聊天结论。

本版增强采集和约束报告缺口尚未接入自动计划/receipt闭环；已有4轮上限及索引历史继续保留，不把本机单次验收称为自动补采已完成，也不通过新文件名绕过停止规则。

## 0.23.0：约束缺口自动补采与重算

### A. 可复现验收

在已有Conda环境更新仓库、重新安装`.[solidworks,templates]`并重启OpenCode。工具仍46个，功能skill仍39个。

```powershell
python scripts/verify_constraint_followup.py --output outputs/verify-0.23
```

预期passed=true、38项检查。覆盖基础→增强→回填→索引/约束重算→停止、API失败、部分读取、配合状态变化、无配合与已增强来源。原始envelope、逐步receipt、派生文件和调用记录保存在该新目录。脚本使用显式合成CAD，不调用本机SolidWorks；真实stdio和完整4轮共享历史另由回归测试覆盖。重复验收换新输出目录。

### B. 本机已有单链证据的自动流程

前置：已有同一target graph的原始check及约束报告；所有绑定来源可回读。已有补采历史保留最新index。SolidWorks当前文档/token/配置/实例位姿与原采集一致；若模型已改变，先重新采集快照并重建来源，不改旧token/哈希。只读流程不重建、不移动、不改配合、不保存覆盖原STEP。

以下使用示例文件名；换成实际来源。缺约束报告时先按0.22.A明确公差生成，不从模板取类型。

```powershell
python -m cadkin plan-evidence outputs/check.json --constraint-analysis outputs/constraints.json --output outputs/constraint-plan-0.23.json
```

已有索引时加`--evidence-index outputs/当前索引.json`；报告本身绑定索引可省略。MCP等价`cad_plan_evidence_tasks`，参数draft_check_path、constraint_analysis_path、output_path及可选evidence_index_path/max_tasks。规划只落盘，不连接CAD。

先读continuation与summary。collect才执行下面命令；stop不执行，也不改文件名重新采。N个实例的单次增强需2N+3总调用；默认max_tasks=20，预算不足明确延期，不能删除保护步骤。报告中的其它未知/未实现规则仍保留。

```powershell
python -m cadkin execute-evidence outputs/constraint-plan-0.23.json --output outputs/constraint-run-0.23.json
```

MCP逐步调用`sw_execute_evidence_task`，每步新output_path，第二步起传previous_execution_path，保持同一plan_path，直到execution_complete。核对guards_passed、records、eligible_capture_ids；失败/partial保留真实envelope。前后保护失败则停止复用，记录状态/错误，不执行后续回填。

当完整且guards_passed=true时：

```powershell
python -m cadkin reintegrate-evidence outputs/constraint-run-0.23.json --output outputs/constraint-update-0.23.json
```

MCP等价`cad_reintegrate_evidence(execution_path, output_path)`。成功后读取after_check_source、after_evidence_index_source、after_constraint_analysis_source、constraint_changes。下一轮规划传新的check/report；本例派生路径如下，实际以返回为准：

```powershell
python -m cadkin plan-evidence outputs/constraint-update-0.23-derived/check.json --constraint-analysis outputs/constraint-update-0.23-derived/constraints.json --output outputs/constraint-next-0.23.json
```

无需对同一receipt再次索引；新报告会继承本轮index。普通失败/partial但保护通过也会保存尝试并占一轮，下轮不自动重试。合成夹具预期可出现局部revolute候选；真实升降机不要求出现该候选。

### C. 数据与失败标准

| 检查 | 预期 | 失败标准 |
|---|---|---|
| 缺口和采集 | 仅缺几何/LockRotation时最多一次include_reference_geometry=true；基础观测不误当增强 | 重复基础扫描称已补足，或加未授权编辑操作 |
| 无配合/不支持 | STEP完整空配合或已增强仍不支持时stop，保留未知/冲突 | 凭导轨名字、近接触或台钳swivel认定运动类型 |
| 执行证据 | 前后文档/全范围位姿通过；增强参数、持久面引用、原始根参数一致 | 基础响应冒充增强；几何/状态变化后继续复用 |
| 部分/失败 | 原始错误保留，不回填；保护通过才记入索引并计轮 | LockRotation读取失败默认为false；失败记录消失 |
| 回填与重算 | 原公差、max_pairs及历史保留，成功给出3份after来源 | pipeline_error仍对外提供有效after结论 |
| 续轮 | 最新index自动继承；与通用采集和选面共享4轮 | 换文件名、旧索引或更大预算重试增强 |
| 比较 | 按实例对保留独立快照、覆盖、候选和缺口变化 | 不同源feature_id直接匹配、缺口消失等于机械确认 |
| CAD和结论 | 原文档dirty/配置/位姿不变；目标unknown/null，requires_human_review=false | 修改模型、确认整机DOF或声称已完成拆卸路径 |

保存Git SHA、环境版本、实际工具参数与耗时、原始返回和新派生路径；对窗口或文档状态无法核对的项记录未验证，不把它设成人工复核前置条件。已停止的增强读取仍可继续其它有独立依据的分析；保留不能自动收敛的原因。

## 0.24.0：局部瞬时约束求解

### A. 更新与可复现验收

在项目根和已有Conda环境中更新并安装依赖；没有新增环境要求。升级后重启OpenCode，工具列表应为47个，功能skill40个。

```powershell
git pull --ff-only
python -m pip install -e ".[solidworks,templates]"
python scripts/verify_local_constraints.py --output outputs/verify-0.24
```

预期`passed=true`、63项检查。13种合成来源覆盖锁定、同心/锁转、轴+平面、重复/平行/非平行轴、单/斜平面、数值敏感、无配合、缺几何和冲突；检查秩/模式、预算、篡改拒绝、原文件/CAD状态不变。保存每次工具参数、原始响应、派生文件及report.json。此脚本不连接真实SolidWorks，不能代表本升降机已求解。输出目录必须新建；重跑换新目录。

### B. 本机已有证据的求解

前置：原cad_analyze_constraints报告及全部绑定来源可回读；0.23回填后优先使用返回的after_constraint_analysis_source。沿用该文件绑定的index/check/轮数。工具只分析记录的快照，因此无需启动SolidWorks；不能将旧快照结果冒称当前已改动的模型。缺报告先按0.22/0.23生成，原始文件不可手改。

```powershell
python -m cadkin solve-local-constraints outputs/constraints.json --characteristic-length-mm 100 --output outputs/local-motion-0.24.json
```

文件名替换为真实来源。100毫米是数值尺度示例，应结合该链已有几何跨度选择并记录依据，不代表行程或实际速度。可选--relative-rank-tolerance 1e-8、--max-pairs 200、--max-constraints-per-snapshot 200。不要调整阈值来追求预定DOF。

MCP等价调用：

```json
{
  "tool": "cad_solve_local_constraints",
  "arguments": {
    "constraint_analysis_path": "outputs/constraints.json",
    "characteristic_length_mm": 100,
    "output_path": "outputs/local-motion-0.24.json"
  }
}
```

给OpenCode：使用mechanism-local-motion按需加载细节，读取上述原报告；逐对逐快照报告状态、完整性、约束秩、剩余瞬时方向及纯平移子空间，记录原点和尺度，保留unknown/风险/历史，不设置人工复核。

### C. 数据核对与失败标准

| 检查 | 预期 | 失败标准 |
|---|---|---|
| 输入与快照 | 重放原analysis、target、raw sources；每源单独计算 | 手写矩阵代替来源，或跨快照拼约束 |
| 矩阵与方向 | 仅有效lock/同心轴/重合平面建方程；每行追溯配合证据 | 使用端座/导轨名称、模板swivel、近接触或固定标志加方程 |
| 范围完整 | coverage、source_missing_evidence、unresolved_evidence、source_conflicts保留 | 省略对/约束、未知LockRotation仍称完整求解 |
| 无有效配合 | no_supported_constraint_model；维数null、模式空 | 声称6DOF或凭几何确认滑动 |
| 数值敏感 | 秩阈值×0.1/×10比较，敏感时维数null、模式空、报告范围 | 强行挑一个秩作为真值；空模式解释成锁死 |
| 局部结果 | modeled_instantaneous_dof仅属于建模快照，目标unknown/null | 局部维数改写成整机DOF或目标revolute/prismatic |
| 方向语义 | 说明根坐标原点、L，保留耦合平移/旋转；纯平移单算 | 把基向量当独立关节/电机速度/枢轴/限位 |
| 冲突与冗余 | 冲突模式不展示；相关方程仅作矩阵诊断 | 自动删配合，或以零空间证明非线性装配可解 |
| 历史与补采 | index/check/rounds保持；补采用原analysis | 用本输出替换constraint_analysis_path，或换路径重置4轮 |
| 副作用 | 所有输入字节不变，结果独占新建，0次CAD调用 | 修改模型/草案/原来源，自动移动或保存覆盖 |

对真实升降机不要求出现预定DOF：STEP无配合时“未知”是有效结果。若同时开启SolidWorks，窗口、dirty、位姿、选择应完全不变；本工具不需窗口核对作为继续前置。保存Git SHA、Python/NumPy版本、尺度依据、完整调用/envelope和输出路径；需要进一步证据时由对应采集功能处理，并沿用停止规则。

## 0.25.0：单链约束与批量执行

### A. 更新和可复现验证

在已有Conda环境、仓库根目录运行，之后重启OpenCode（49工具、41功能skill）：

```powershell
git pull --ff-only
python -m pip install -e ".[solidworks,templates]"
python scripts/verify_chain_constraints.py --output outputs/verify-chain-0.25
python scripts/verify_mcp_efficiency.py --output outputs/verify-speed-0.25
```

两个脚本分别预期43项、10项检查，passed=true。前者使用合成配合的原始绑定来源检查开链/闭环/重复约束、耦合模式、不连通、无配合和篡改拒绝；后者通过官方SDK和真实stdio比较单步/批次，保存完整响应、原始CAD返回及计时。均不连接本机SolidWorks，不代表升降机已求解。每次用新的输出目录。

冷启动协议回归也可单独运行，保持原120秒测试上限：

```powershell
python -m unittest tests.test_mcp.McpTests.test_local_constraint_solution_over_production_stdio tests.test_mcp.McpTests.test_batched_capture_and_chain_solution_over_stdio -v
```

前一项检查0.24 Windows首次数值调用卡住的路径；服务端现在在stdio后台读管道之前初始化NumPy/数值库，不在第一个工具线程才首次导入。两项都应完成，错误后仍可调用，不靠提高该测试超时通过。

### B. 本机有界批次

前置：原plan与全部来源有效，当前SolidWorks文档/token/配置/实例位姿与计划一致。continuation.action=stop时不执行、不重采；工具不自动启动或打开其它文档。首次调用：

```powershell
python -m cadkin execute-evidence-batch outputs/plan.json --output outputs/batch-01.json
```

MCP为sw_execute_evidence_batch，参数plan_path、output_path；可选previous_execution_path、max_steps（默认12，上限20）、time_budget_seconds（默认30，上限60）。时间只在步骤间判断；原COM单步180秒超时不变。OpenCode客户端设300000ms供默认配置使用，不代表COM可取消或自动重试。

如果continuation.action=continue，下一批用新output，并传**上一返回execution_source.path**：

```powershell
python -m cadkin execute-evidence-batch outputs/plan.json --previous-execution outputs/batch-01-steps/step-012.json --output outputs/batch-02.json
```

上述step-012仅举例，实际路径以返回为准；时间预算可能提前停止。保持同一plan，不从首步重新执行。单步诊断仍可使用原sw_execute_evidence_task，不与批次并行。完整且guards_passed=true时将最后execution_source.path交给cad_reintegrate_evidence；batch_report_source指向诊断文件，不能作execution_path。

performance保存批次总时间、CAD工具调用时间之和、编排时间、工具调用/步数和逐工具明细；agent思考、网络和UI等待不在其中。仅需要定位具体慢工具时展开batch_report_source.path。失败和partial仍保留原始envelope及receipt，不会因批量执行提升为有效证据；TIMEOUT/OUTCOME_UNKNOWN和文档变化停止。

### C. 本机单链求解

前置：同一原链的约束报告、原始来源全部可回读；0.23/0.25回填后使用after_constraint_analysis_source。2–20个实例、每快照上限6000方程；参考路径必须属于链。无需连接CAD。

```powershell
python -m cadkin solve-chain-constraints outputs/constraints.json --reference-occurrence-path "实际实例路径" --characteristic-length-mm 100 --output outputs/chain-motion-0.25.json
```

MCP为cad_solve_chain_constraints，必填constraint_analysis_path、reference_occurrence_path、characteristic_length_mm、output_path；可选relative_rank_tolerance默认1e-8、max_constraints_per_pair默认200。100毫米仅示例尺度；记录选择依据。参考仅去掉共同刚体运动，不凭名称或IsFixed认定接地。

先读summary、coverage和逐源status/缺口计数；需要具体模式/证据时读取solution_source.path。每个模式同时包含各组件的耦合速度。缺失/不连通/冲突/敏感均保留未知，不强制产生某种自由度或关节类型。

### D. 失败标准与证据

| 检查 | 预期 | 失败标准 |
|---|---|---|
| 批次语义 | 与逐步相同的依赖、8项保护及1项采集（示例） | 为提速删保护、重试失败或并行COM |
| 续跑 | 沿同plan和最新execution_source；只处理剩余前缀 | 把batch report作receipt、重复采集或增加轮数 |
| 不确定状态 | blocked/TIMEOUT/OUTCOME_UNKNOWN不继续；已运行COM可能仍完成 | 将超时当取消后重试、宣称状态已恢复 |
| 紧凑返回 | 摘要保留状态/缺口/错误码，完整raw/receipt/结果存盘 | 为缩短输出丢失证据或隐藏partial |
| 链级组装 | 同快照、共同原点与显式相对参考；内部跨对联系联合处理 | 相加局部DOF、跨快照组装、删掉链外/未知联系 |
| 闭环 | graph_cycle_count与additional_loop_rank仅线性诊断 | 自动删“重复”配合或宣称非线性闭合/有限行程可行 |
| 空/断开模型 | modeled_chain_instantaneous_dof=null，诊断范围明确 | 无配合就确认12DOF或孤立节点当接地 |
| 数值启动 | 冷stdio首次求解可完成，未提升原测试期限 | 第一次数值工具长时间无响应 |
| 性能结论 | 保存本机时间，区分工具/编排/agent等待 | 用合成0.2秒或9→1往返当SolidWorks实机加速倍数 |
| 原始模型/历史 | 0次额外编辑；源哈希、index/check与4轮不变 | 写回草案最终类型、移动组件或覆盖模型 |

保存Git SHA、Python/NumPy版本、全部工具参数/响应、原始envelope、逐步receipt、批次计时和链结果。真实升降机没有配合时未知是有效结论；不需要人工复核作为继续前置。

## 0.26.0：首次单链联调

前置：已有Conda安装`.[solidworks,templates]`并重启OpenCode（50工具）。自动验收：

```powershell
python scripts/verify_chain_session.py --output outputs/verify-chain-session-0.26
```

预期35项检查、passed=true。案例含闭环、无配合、增强partial、TIMEOUT，使用显式合成CAD与生产CLI/工具编排；实际软件另按下表验收。命令不会把夹具放入生产启动路径，原有14套验收继续保留。

| 实机步骤 | 准确入口/参数 | 预期与失败标准 |
| --- | --- | --- |
| 启动与范围 | 使用原sw_start_application/sw_open_document，随后sw_component_tree；从当前返回取2–20个叶实例及token | 活动文档是目标装配；不把文件名“三独立”当识别结果 |
| 配置 | 按CHAIN_SESSION.md写outputs/chain-session-config.json；提供当前token、scope、reference、数值尺度和毫米/度公差 | 原尺度/公差记录完整；禁止不存在的路径和旧token |
| 首次联调 | `python -m cadkin chain-session outputs/chain-session-config.json --output outputs/chain-session-0.26.json` | workflow_complete=true且退出码0；可能仍有未知。错误退出码2，报告/原始日志保留 |
| 基线离线重放 | `cad_create_chain_baseline`：execution_path为首轮receipt，output_path为新JSON，显式distance_tolerance_mm/angle_tolerance_deg | 不调用CAD；完整保护后baseline_created=true、outputs给出check/index/constraints，首轮记1/4。已有关系/索引拒绝 |
| 计时 | 读report_source的performance、cad_capture_tool_timings及batch_sources | 批内工具按实际调用计时，阶段包含批次不能相加；不将结果称为纯COM/API时间 |
| 当前结论 | 读solution_summary、evidence_summary、remaining_findings_summary与stop_reason | 无配合不能称自由运动；有限运动/整机DOF/机械验证仍false/null |
| 失败/续跑 | 原receipt、最新check/index/constraints交接独立工具 | 不改旧token/哈希、不删占用文件、不换文件名重采以绕过历史；TIMEOUT先核对软件状态 |

证据保存在指定session JSON和同名-files目录。配置、原始envelope/receipt、基线、index、analysis和solution均保留，源文件不得覆盖。若用户运行被软件对话框/超时阻塞，应依据最末完整调用日志定位；不能把自动测试通过写成实机通过。窗口中模型的位姿、显隐和保存状态应保持不变；本入口不负责移动/碰撞验证。

## 0.27.0：原生配合独立分析

### 前置条件与自动检查

Windows已有Conda环境更新：git pull --ff-only、python -m pip install -e ".[solidworks,templates]"，重启OpenCode。目录应列出51工具，包括cad_review_root_mates。以下命令使用显式合成CAD，不连接真实SolidWorks：

```powershell
python scripts/verify_root_mates.py --output outputs/verify-root-mates-0.27
python -m unittest tests.test_root_mates tests.test_mcp.McpTests.test_root_mates_without_cylinders_over_production_stdio -v
```

脚本预期passed=true、54项，原始来源/receipt/索引/求解保存在指定新目录；重跑换新目录。测试覆盖平面/lock/闭合链、无配合、partial、圆柱全失败、身份/姿态/哈希/派生篡改、实体引用歧义、预算/历史、CLI及生产MCP协议。无真实COM机械结论。

### 实机首次入口

让agent读取当前活动装配token和准确叶实例路径，按CHAIN_SESSION.md创建2–20实例配置，增加capture_profile="root_mates"。reference_occurrence_path选实际链内实例；characteristic_length_mm及毫米/角度公差按任务尺度明确，不复制示例为校准结论。执行：

```powershell
python -m cadkin chain-session outputs/root-mates-config.json --output outputs/root-mates-session-0.27.json
```

已有check/index/receipt必须沿用，不为验收删除历史重跑。尚未打开模型可让agent用现有启动/打开能力处理；采集时保持文档/配置/位姿不变。

核对：报告capture_profile=root_mates；首次v5计划只有一次include_reference_geometry=true的sw_mate_inventory采集，加前后2N+2个document/pose保护。无sw_component_cylinders/faces/distance调用；正常首轮计1/4，原始envelope和执行receipt均可回读。三实例的批内工具总数为9；入口活动文档/空间分页另计，不限制实际批次数。状态窗口不应出现零件移动、配合编辑或保存覆盖。

有完整有效双实例配合时，baseline.outputs应有可读的target/index/constraints，连接来源schema=2且仅inventory/mates，relation_sources可为空；支持的lock/同心/重合平面进入瞬时求解。无配合时允许workflow_complete=true但维数仍null/无受支持模型。首轮增强partial不应重复采集；保留失败尝试，可能以NO_EXISTING_CONNECTION_BASIS停止。保护失败不得回填，TIMEOUT保留receipt并停止后续CAD调用。

### 已有采集文件的离线入口

无需启动CAD或重采，调用cad_review_root_mates：inventory_path=原完整空间清单路径，mate_inventory_path=原sw_mate_inventory envelope路径，output_path=outputs下新JSON。两来源须同一文档/配置/实例位姿。返回review_source和coverage；完整结果按需查看。再将review_source.path加入cad_build_chain_evidence的evidence_paths，交接原目标图/约束分析/链求解。已有基线更新仍用cad_reintegrate_evidence保留索引。

含face_matching的输入应报FACE_MATCH_BASIS_REQUIRED，继续原cad_review_connections并携带几何来源；不能删除字段绕过。多实体/未映射引用在unmatched_mates，不应变成正常两端约束。旧schema v1链可重放；旧文件不改写。

### 失败标准与保存

把缺配合写为自由运动、把partial写成完整、无依据重复采集/清索引、模板类型写入目标、缺少保护、覆盖原文件、歧义配合进入确定模型，都判失败。完整输出保存在outputs的新目录：配置、原始返回、plan/receipt、baseline、index/check/constraints/solution和session计时报告。结论列出已支持约束、未知、来源范围与风险；不以人工复核作为继续条件。

## 0.28.0：几何连接解释与定向补采

### 更新与自动检查

在已有Conda环境运行git pull --ff-only和python -m pip install -e ".[solidworks,templates]"，重启OpenCode。工具目录应有52项，包括cad_analyze_geometric_connections；功能skill45个。

```powershell
python scripts/verify_geometric_connections.py --output outputs/verify-geometric-connections-0.28
python -m unittest tests.test_geometric_connections tests.test_mcp.McpTests.test_geometry_analysis_capture_and_stop_over_stdio -v
```

验收脚本预期passed=true、44项；显式合成CAD，非SolidWorks实机或升降机识别率。输出目录必须新建。覆盖几何无配合解释、已有距离/平面复用、距离失败后停止、三轮距离/面目录/有限面探测、历史与原文件保留。协议测试把真实SDK/stdio和合成CAD分开；离线重算使用生产MCP。

### 实机前置与分析

复用一条显式链的target/check和最新index；source files全部可读，当前装配文档/配置/位姿与其一致。target至少有绑定的圆柱关系、距离或面探测来源，否则应返回insufficient_geometry，不能补假数据。已有history不重新运行首次chain-session绕过轮数；原root_mates模式未采圆柱，不能凭其空几何得出运动关系。

调用cad_analyze_geometric_connections：target_graph_path=实际target路径，evidence_index_path=最新实际索引（没有历史才省略），distance_tolerance_mm/angle_tolerance_deg=明确的任务公差，output_path=outputs下新JSON；max_pairs默认100，可在1–200限范围。0.1 mm/0.1°仅示例，不代表升降机已标定。

预期摘要含analysis_source、coverage、rounds_completed；详细pairs在文件。几何同轴可以给多种候选，但target_joint_kind必须unknown、target_degrees_of_freedom必须null；每解释保留支持与未验证条件，不加载模板或编辑配合。较宽来源公差的同轴判定仍须通过本报告阈值；放宽阈值不能补回源扫描遗漏的实例对。相向近平面不等于接触或运动副，多条轴的防转冲突是条件性的。

### 定向取证与验证

cad_plan_evidence_tasks传同target的draft_check_path、新geometry_analysis_path、output_path和max_tasks；与constraint_analysis_path/initial_capture_profile互斥。已有index从报告自动继承；不同显式索引应拒绝，先用最新索引重算报告再规划。

有缺失距离时，预期v6计划只列sw_component_distance与全部前后保护；两实例一项测距共7次（6保护+1测量）。预算6应生成stop/空任务及延期，不省保护。已有完整距离包括大间隔不重采；失败/partial尝试保留索引并阻止自动重试。

用sw_execute_evidence_batch执行，未结束按execution_source续跑。guard通过后cad_index_evidence传同check、新execution_path、新output_path；再同target+新index重算几何报告。保护失败不可索引/复用，TIMEOUT保留receipt并停止。窗口不应出现零件移动、配合编辑或保存覆盖。

已有近距离而缺有限面时，交cad_plan_face_probes，显式传同check/index、max_component_gap_mm、surface_tolerance_mm及预算。缺目录先采目录、索引，随后规划真实face locator/见证点种子并探测；再索引、重算几何报告。每一步沿用当前轮数，第四轮后不自动继续。已探测面不反向/换种子重试。

### 失败标准与留档

把几何candidate_kind写成目标已确认类型/DOF、把同轴偏移当组件表面间隙、把局部样点当持续接触、用模板替代目标约束、删除失败历史/换报告绕过索引、忽略源公差或未测范围均判失败。将几何报告传入cad_solve_chain_constraints应报INVALID_CONSTRAINT_SOURCE，禁止混用。

保存原始target/check/index、全部来源、geometry report、v6/v3 plan、原始envelope、receipt及更新index到outputs新路径。报告可因原target缺口继续partial，不能因一次成功测量清除所有风险。不要求人工复核；物理连接、接触持续性和有限运动缺能力时明确保留未知。完整说明见[GEOMETRIC_CONNECTIONS.md](GEOMETRIC_CONNECTIONS.md)。


## 0.29.0有限圆柱边界与轴向范围

### A. 更新与可复现验证

在用户已有Conda环境、仓库根目录执行：

```powershell
git pull --ff-only
python -m pip install -e ".[solidworks,templates]"
python scripts/verify_finite_connections.py --output outputs/verify-finite-connections-0.29
```

预期passed=true、47项；重跑换新目录。脚本为明确合成CAD，不能代替实机COM。重启OpenCode，list_tools应54，版本0.29.0。

### B. 本机读取边界

前置：活动根装配、相同配置/实例位姿，已有当前原始face catalog与准确圆柱face选择。expected_document_token使用实际返回。调用sw_read_face_boundary：

```json
{"expected_document_token":"实际24位token","face":{"face_inventory_path":"outputs/faces.json","body_index":0,"face_index":2},"max_edges":64}
```

例中索引须替换成真实目录所选圆柱，不能沿用示例猜测。预期原始envelope含face_boundary_schema_version=1、source原目录哈希、直线endpoints_part_m或circle_parameters_part、read/reported_edge_count及complete/truncated。圆弧可能没有顶点，工具只对直线读取端点；不把圆参数当完整圆周。预算截断/复杂曲线/读取失败应partial或error，不补零范围。相同面身份、描述、位姿及边界回读改变应拒绝。窗口选择、零件位置、模型dirty状态不应被此只读工具修改。

### C. 自动分析—补采—索引

复用原geometry报告、check和最新index，调用cad_analyze_finite_connections，参数geometry_analysis_path、output_path，可选evidence_index_path和max_face_pairs。优先读摘要coverage/analysis_source，再按需读pairs。缺目录时返回缺口，不扫描目录；已有完整无冲突目录中的圆柱候选面可用于补边界。

cad_plan_evidence_tasks传draft_check_path、finite_analysis_path、output_path；不要混传其他profile。预期v7未执行计划；两实例一面各1次，2采集+6保护=8次。max_tasks=4无法容纳单面5次时应stop，不省保护。实际预算允许只采一面时保留另一面的deferred；不可把只采一面算成完整关系。

sw_execute_evidence_batch按原保护执行，必要时按execution_source续跑。guard通过且完整后cad_index_evidence传同check与receipt；包括失败/partial尝试。再cad_analyze_finite_connections传原geometry及新index，重算后才能继续规划。当前或后继index必须同target且历史连续，新index不能直接替换旧finite计划的历史。第四轮后停止剩余边界采集，不从0开始。

预期comparison的投影区间/重叠/间隔来自原解析边界。axially_separated_face_enclosures只针对指定面；axial_enclosures_overlap并不证明角向裁剪对应。radius_difference_mm不是配合间隙。局部轴向平面即使接近投影端点，也未证明与圆柱同实体/邻接，retention_confirmed=false、travel_limit_mm=null。

### D. 失败标准和留档

未知/部分边界变成完整区间、失败后换预算自动重试、通过删index/新建链清轮数、把投影包络变成行程、直接认定转动/滑动或把finite报告传入原生求解器，都判失败。几何报告/输入被改应EVIDENCE_MISMATCH；目标类型unknown、DOF及motion_limits_mm仍null。

保存原catalog/geometry/check/index、原始边界envelope、plan/receipt、更新index与finite报告到outputs新路径；不覆盖模型或旧证据。不设人工复核门槛，未完成的互补表面、角向覆盖、邻接、接触持续性和有限运动在结论说明。详情见[FINITE_CONNECTIONS](FINITE_CONNECTIONS.md)。

## 0.30.0：表面采样与邻接补证

当前57工具、50个独立功能skill。在已有Conda执行README更新步骤，重启OpenCode。自动验收：

```powershell
python scripts/verify_surface_engagement.py --output outputs/verify-surface-engagement-0.30
```

预期95项`passed: true`，完整证据留在新目录；五种合成装配情境不代表升降机实机结果。不要在实机使用合成目录的token、面ID或query点。

实机用原finite报告、同check及最新index，所有输出使用新路径：

1. `cad_analyze_surface_engagement`：`{"finite_analysis_path":"outputs/finite.json","evidence_index_path":"outputs/latest-index.json","output_path":"outputs/engagement-030.json"}`。若没有更新index可省略该参数以继承原报告；有历史不得省略绕过。核对coverage、rounds_completed、来源和缺口；离线不会启动CAD。
2. `cad_plan_evidence_tasks`：`{"draft_check_path":"outputs/check.json","engagement_analysis_path":"outputs/engagement-030.json","output_path":"outputs/engagement-plan-030.json","max_tasks":20}`。核对algorithm_version=8、planned_capture_tasks及含保护总数；两个实例各一面时通常4capture+6guard=10调用。计划没有capture时停止，不空跑保护。
3. `sw_execute_evidence_batch`：`{"plan_path":"outputs/engagement-plan-030.json","output_path":"outputs/engagement-batch-030-01.json","max_steps":20,"time_budget_seconds":60}`。若未完成，原样传plan_path并以execution_source续作previous_execution_path，换新output。不得重新初始化计划或删除partial/failed。
4. 完整receipt交`cad_index_evidence`：`{"draft_check_path":"outputs/check.json","execution_path":"实际最终receipt路径","output_path":"outputs/engagement-index-030.json"}`。使用实际receipt，保护失败的capture不能变成usable。
5. 以原finite报告+新index重算到`outputs/engagement-after-030.json`，再规划到新路径，检查已尝试的面/工具不再调用，第四轮后保持stop。

逐项判断新增功能：

| 项目 | 应核对的返回 | 不能据此声称 |
| --- | --- | --- |
| 点成员与内外侧 | 每面1–32点，原始投影与定向法向；查询距离/阈值、inner/outer或sheet_orientation_only；失败行保留 | 完整360度覆盖、接触面积、已配合 |
| 真实邻接 | 每边两槽、同体和面身份、持久引用、空邻面/缝边；预算/读取失败为partial | 跨组件接触、止推、挡肩限位 |
| 离线汇总 | paired_samples中双侧成员/相反材料侧、点间距离、法向；实际邻接轴向平面；来源与旧错误/遗漏 | 目标revolute/prismatic、整机DOF或行程 |
| 效率与停止 | 批次内实际调用/各耗时、共享rounds_completed；已有完整/失败不再读 | 合成速度等于实机加速比 |

记录本机SolidWorks版本、提交SHA、原envelope/receipt/index与耗时；本轮只读，不移动或保存模型。风险直接写入结论，不增加人工复核节点。

## 0.31.0：有限端面区域与方向

当前59工具、52个功能skill。已有Conda执行README更新安装并重启OpenCode；自动验收命令：

```powershell
python scripts/verify_planar_contacts.py --output outputs/verify-planar-contacts-0.31
```

预期82项`passed: true`；六种显式合成情境，不是升降机实机结果。重跑换新目录。

实机复用当前原始engagement报告、同check及最新index，输出均用新路径：

1. `cad_analyze_planar_contacts`：`{"engagement_analysis_path":"outputs/engagement.json","evidence_index_path":"outputs/latest-index.json","output_path":"outputs/planar-031.json","max_plane_pairs":20}`。无更新索引时继承报告，不丢弃已有历史；查看coverage、rounds_completed、源错误与缺口。
2. `cad_plan_evidence_tasks`：`{"draft_check_path":"outputs/check.json","planar_analysis_path":"outputs/planar-031.json","output_path":"outputs/planar-plan-031.json","max_tasks":20}`。应algorithm_version=9；两个实例四面通常4capture+6guard。任务使用原邻接文件和原持久引用，不猜face索引；与其他profile互斥。
3. `sw_execute_evidence_batch`：`{"plan_path":"outputs/planar-plan-031.json","output_path":"outputs/planar-batch-031-01.json","max_steps":20,"time_budget_seconds":60}`。只有有capture才执行，未完成以execution_source作previous_execution_path续跑同计划，换新输出。
4. 完整receipt交`cad_index_evidence`：`{"draft_check_path":"outputs/check.json","execution_path":"实际最终receipt路径","output_path":"outputs/planar-index-031.json"}`；用原engagement+此新index重算至新planar报告，再规划确认已尝试的面不重读、第四轮后停止。

| 新能力 | 核验内容 | 失败/未知标准 |
| --- | --- | --- |
| sw_read_planar_face | 原adjacency持久引用/同体与上下文；loops数量、边数、完整圆周期或凸闭合直边；面积和GetArea一致 | 数量/身份/来源变化拒绝；预算、复杂轮廓、圆弧、偏心/多孔、凹轮廓或面积不符保留partial/错误 |
| cad_analyze_planar_contacts | 圆环扣孔，区域投影面积mm²；原容差下的signed_plane_gap_mm；正/负间隙与条件闭合方向 | 不支持混合/倾斜面比较为unknown；没有正解析面积不证明绝无边接触；接触/保持false，类型unknown、DOF/行程null |
| 规划与效率 | 一面一次、含全部保护的预算、batch实际耗时、receipt/index历史 | 失败/partial不扩参数重试，四轮不重置；无空保护、无整装配扫描 |

保存每次原envelope、receipt/index、提交SHA及本机版本/耗时，核对SolidWorks无选择/位姿/保存变化。范围为零件定义、不含装配级特征；未在实机运行不能标记通过，不设置人工复核节点。
