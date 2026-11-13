# OpenCode + SolidWorks 使用与排错

## 首次安装

在已安装 SolidWorks 的 Windows 电脑，取得仓库后进入根目录。使用已有的 Python 3.10+ Conda 环境，下面环境名换为你本地实际名称：

```powershell
git clone https://github.com/leixn01/3dmodel-rcgn.git
cd 3dmodel-rcgn
conda activate 你的环境名
python -m pip install -e ".[solidworks,templates]"
```

已有仓库先 `git pull --ff-only`，再执行依赖安装命令；升级后退出并重新启动 OpenCode，让本地 MCP 进程及工具目录刷新。当前应有 54 个工具。仅维护 Windows；自动启动的就绪检查使用 SolidWorks 2015+ API，旧版不保证可用。STEP 已随仓库提供，无需解压。依赖为官方 MCP SDK 1.29.0、Windows 上的 pywin32、OpenUSD usd-core 25.11、NumPy 1.26–2.x及其依赖；离线体检无需安装这些依赖。不要把第三方上游仓库也注册成同名 MCP，以免调用到另一套工具。

在同一个已激活 Conda 的终端启动 OpenCode；MCP 子进程通过 PATH 找到该环境的 python。先执行 `python -c "import sys; print(sys.executable)"` 记录解释器路径，再让 OpenCode 调用 `sw_session_status`，比较 `data.runtime.python_executable`，且 `matches_conda_prefix` 应为 true。运行时同时返回 python_prefix、conda_prefix、python_version；软件未运行时也能检查。没有 CONDA_PREFIX 时匹配值为 null，不能据此声称已在 Conda 中。

## 连接与实际操作

1. 确认本机已安装桌面版 SolidWorks；无需手动提前启动。自动启动使用 Windows 注册的默认版本；许可/恢复文件等弹窗可能仍需本机处理。
2. 在仓库根目录运行 `opencode mcp list`，确认 `solidworks` 已连接，再运行 `opencode`。MCP 已连接只表示协议服务可用；还需调用会话工具验证 SolidWorks。
3. 告诉 Agent：

```text
加载 solidworks-connect，检查 SolidWorks 会话；未运行时加载 solidworks-start 启动并核对启动完成。
加载 solidworks-document，打开 examples/three_servo_lift/3X Lift Assembly.STEP。
报告实际文档类型；如果是装配，加载 assembly-inventory，读取组件树。
加载 component-spatial，使用 spatial-export 分页采集完整清单到 outputs 下的新文件；报告 collection_complete、hierarchy_complete、truncated 和 errors。
加载 solidworks-display，隐藏当前模型的基准面并回读核对。
然后加载 solidworks-view，保持当前视角缩放适合窗口。
```

4. 检查 SolidWorks 窗口及 JSON。需要突出某个实例时，加载 `component-selection`，提供组件树中的完整 `occurrence_path`；Agent 应先读取当前文档 token，再选择和核对。
5. 要隐藏/显示一个装配实例时加载 `component-visibility`，提供组件树中的完整实例路径；该操作不解除抑制、不移动组件。
6. 需要重建时明确要求“加载 solidworks-document，重建当前文档”；该操作不保存。工具目前不负责移动零件或添加配合；离线可生成运动关系候选，尚不确认运动。

用户也可以先手动打开 STEP，再从组件读取开始。若导入为多实体零件，组件树工具会返回 `NOT_ASSEMBLY`，不生成空装配结果。

## 组件分组

模型已打开后执行 README 的 `spatial-export` 和 `group` 命令，或让 Agent 使用 `component-grouping`。指定子装配用 `group ... --scope "完整实例路径"`；默认不传人工review文件，疑点由后续自动分析并最终报告风险。输入/复核文件必须在项目内，分组输出必须在 outputs 内；不覆盖原文件。旧版单次空间导出改为分页，推荐直接使用新 CLI 收齐，不把一页返回当整机结果。

## 配合与轴线证据

从真实组件树选择一个完整实例路径，让 Agent 分别调用 `sw_component_constraints` 与 `sw_component_cylinders`。前者保留固定/浮动标志及原始配合，后者读取解析圆柱面的轴线/半径；缺失与上下文限制明确返回。按 0.6.0 清单核对，不把没有配合当作自由运动，也不把圆柱轴线直接当旋转副。

## 配合引用面核对

按 0.9.0 清单给圆柱采集传 include_face_references=true，并用新文件重算关系。由 mate-face-matching 调用 sw_match_mate_faces，输入完整空间文件和少量圆柱文件；保存完整 envelope 后交给 connection-review。面身份与配合状态分别报告，旧文件仍可作实例对关联。

## 无配合 STEP 的邻近与距离

按 [0.10.0 清单](MCP_ACCEPTANCE.md#0100组件距离与近接触候选) 先取包含包围盒的完整空间 JSON；component-proximity 离线生成少量待测对，component-distance 逐对只读测量，proximity-review 离线整理。两种阈值都需显式给出，并注明探索值或真实工程依据。

已有两条实例路径时可独立测量，不必先读配合或圆柱。需要筛选时只读已有空间文件；只有缺少输入才补采，不强制加载三套 skill。partial、未测和缺失包围盒保留未知，不能写成零距离或确认机械连接。

## 具体面的局部间隙与法向

按 [0.11.0 清单](MCP_ACCEPTANCE.md#0110具体面间隙与法向)，component-faces 读取单实例面目录，face-gap-probing 解析选定面并从明确根坐标种子获取有限面测点/法向，face-contact-review 离线判读。三者分别按需加载，已有文件时不重走采集流程。

本轮支持解析平面/圆柱，只取零件定义并按实例放置，不含装配级切除；不以圆柱轴线距离代替面点间距。收敛不等于全局最优，大测点间隙不能排除其他区域接近，零/小间隙也不自动确认接触。模型实际进度和已用工具见 [拆解进度](MODEL_PROGRESS.md)。

## 一条升降链的证据清单

按 [0.12.0 清单](MCP_ACCEPTANCE.md#0120机构链证据清单与人工复核)，给出2–50个明确叶实例和名称，让chain-evidence汇总已有分组/连接/组件近接触/面候选文件。输入不必全部齐全；缺失保持未知，不强制启动CAD或补全整机测量。

默认不调用旧人工复核工具。旧review_flags/requires_review仅提示自动核对证据，不能成为向用户索要确认的条件；没有依据就保留未知。旧cad_apply_chain_review仍可读取已有历史文件，不能把Agent推断伪装成用户声明。

## 配置

根目录 `opencode.json` 使用 V1 格式，V2 官方兼容说明支持该格式；无需为了加载 skill 迁移配置。服务启动命令为 `python -m cadkin.mcp_server`，必须在已激活目标 Conda 的终端、仓库根目录启动 OpenCode。

若本机使用 V2 原生配置，可将同一个服务对象置于 `mcp.servers.solidworks`，使用 `disabled: false`，并把超时写为 `timeout: {"catalog": 70000, "execution": 190000}`。不要同时维护两份冲突的同名服务定义。全局个人凭据不应提交到项目。

需要从其他目录启动或有特殊路径时，将 command 第一项改为本机 Conda 环境 Python 的绝对路径，并在命令参数中添加 `--root` 与仓库绝对路径。默认按项目工作目录解析相对模型路径。MCP/CLI 默认调用上限 180 秒，项目 OpenCode 超时为 190000 ms；启动工具的 `wait_seconds` 默认 120，仅约束能够返回控制权的就绪轮询，不能中断阻塞 COM 调用。

如果 OpenCode 由其他启动器运行、不能继承激活环境，可以在本机把 command 改为 `["conda", "run", "--no-capture-output", "-n", "实际环境名", "python", "-m", "cadkin.mcp_server"]`；conda 需可被该启动器找到。必须保留 --no-capture-output，避免缓冲 MCP stdio。机器专属名称/路径不要提交回公共配置；正常从激活终端启动不需要此改动。

Skill 位于 `.opencode/skills/<名称>/SKILL.md`，按默认规则发现；不需要额外配置 skills 路径或把所有正文塞进 instructions。

## 排错

| 现象 | 处理 |
| --- | --- |
| MCP 无法启动 | 激活已有 Conda，用 python -m pip 安装依赖，并从同一终端的仓库根目录重新启动 OpenCode |
| 解释器不符 / matches_conda_prefix=false | 对比终端 sys.executable 与 MCP runtime，退出旧 OpenCode/MCP 后从正确激活终端启动；不要新建项目虚拟环境绕过 |
| `UNSUPPORTED_PLATFORM` | 使用 SolidWorks 所在电脑的 Windows Python；Linux/WSL Python 不能直接访问 COM |
| `connected: false` / `NOT_RUNNING` | 调用 `sw_start_application` 启动，再执行模型任务；纯状态查询保持只读 |
| `APPLICATION_NOT_REGISTERED` | 检查桌面版 SolidWorks 安装和 COM 注册；工具不自动安装、修复注册或猜 exe 路径 |
| `STARTUP_PENDING` | 已连接但启动/插件加载未完成；核对许可或恢复弹窗，处理后再调用启动工具复用该进程 |
| `START_FAILED` / `START_OUTCOME_UNKNOWN` | 进程可能已创建，先检查窗口/任务管理器；不要连续新建进程，结果不明时重启 MCP 后复核 |
| `CONNECT_FAILED` | 确认同一 Windows 用户、相同权限级别，结束启动弹窗；不要把云端服务当作本机连接 |
| `MULTIPLE_SESSIONS` | 当前版本需要保留一个目标 SolidWorks 进程；不要自动关闭用户工程 |
| MATE_STATE_CHANGED | 配合状态在采集期间变化；稳定模型后重新采集，不继续使用混合快照 |
| EVIDENCE_MISMATCH | 空间清单与圆柱证据的文档/配置/实例变换不一致，或分组哈希不符；重新采集一致来源，不改写数据骗过校验 |
| RELATION_LIMIT / SOURCE_INCOMPLETE | 读取结果文件的覆盖和 errors，缩小关系分析范围或补齐来源；partial 不等于完整整机结果 |
| FACE_REFERENCE_UNAVAILABLE | 需要面核对时重新采集带持久引用的圆柱证据，并重算关系，不手写面 ID |
| FACE_REFERENCE_UNRESOLVED / FACE_CORRESPONDENCE_UNAVAILABLE / FACE_IDENTITY_UNAVAILABLE | 保留未知，核对原始 API 错误；不能按几何近似代替身份 |
| FACE_GEOMETRY_MISMATCH / GEOMETRY_CHANGED / MATE_REFERENCE_CHANGED | 几何或引用改变，重新采集稳定的一组证据；不要混用旧文件 |
| INVALID_FACE_MATCH_SOURCE | 核对面匹配与关系使用相同圆柱/空间文件，不修改哈希绕过 |
| IN_CONTEXT_EDIT_ACTIVE | 先报告在位编辑状态；用户处理后重测，不自动退出编辑模式 |
| DISTANCE_NO_SOLUTION / INVALID_DISTANCE_RESULT / DISTANCE_POINT_MISMATCH | 保留 measurement=null、原始错误和 partial；核对实际目标/支持的几何，不用包围盒距离补造结果 |
| NOT_PART_COMPONENT / COMPONENT_CONFIGURATION_MISMATCH | 选择已解析叶零件并核对配置，不自动解析、切配置或聚合子装配 |
| PROXIMITY_PAIR_LIMIT / PROXIMITY_CANDIDATE_LIMIT / UNRANKED_OCCURRENCES | 查看覆盖与未知范围，缩小范围或补齐包围盒；预算前缀不是整机全局最近邻 |
| DUPLICATE_DISTANCE_SOURCE / DISTANCE_OUTSIDE_SCOPE | 每对仅传一个原始距离文件，反序仍是同一对；范围外测量需匹配工作清单或独立报告 |
| UNSUPPORTED_FACE_SURFACE | 面目录可以保留 other 表面，本轮探测仅支持解析平面/圆柱，不近似改成平面 |
| FACE_PROBE_ITERATION_LIMIT | 保留已有有效测点及 partial；点迭代稳定不等于全局最小距离，不无预算扩大整机扫描 |
| FACE_POINT_NOT_ON_FACE / INVALID_FACE_POINT / INVALID_FACE_NORMAL | 保留原始错误；点失败不补零，法向失败时仍可保留点间隙，不能推断相向接触 |
| INVALID_FACE_PROBE_SOURCE / DUPLICATE_FACE_PROBE | 使用原始源目录与探测文件，每个来源绑定面对应只传一个快照；不能改哈希/坐标绕过 |
| INVALID_CHAIN_SCOPE / DUPLICATE_CHAIN_SOURCE | 从完整清单选择不同叶实例；每个证据文件/内容只传一次，不把父装配当叶零件 |
| GROUPING_REVIEW_SOURCE_REQUIRED | 旧人工分组缺review_path时提供原始grouping_review_path，核对review_sha256，不根据标签补造理由 |
| UNASSESSED_CHAIN_PAIRS / SOURCE_INCOMPLETE | 清单仍可作为草案，但未知/未测不等于无连接；保留partial和具体缺口 |
| INVALID_CHAIN_REVIEW / UNACKNOWLEDGED_CHAIN_FLAGS | 核对原清单哈希、实际复核人/时间/逐对意见及已处理提示；不能替用户确认或用旧索引迁移决定 |
| CHAIN_SOURCE_LIMIT | 来源图超过256文件或128 MiB，缩小范围和输入；不通过跳过校验继续生成完整结果 |
| 缺少新增工具 | 更新仓库并安装依赖，退出并重新启动 OpenCode；核对 MCP 工具目录应为 44 个 |
| `DISPLAY_CONSTANTS_UNAVAILABLE` | 检查报错中的类型库原因；需要当前 SolidWorks 安装目录的 swconst.tlb，不靠猜测常量替代 |
| `DISPLAY_BLOCKED` / `PARENT_HIDDEN` | 总开关或父装配仍隐藏；根据用户要求处理，不擅自显示其他对象 |
| `DISPLAY_MISMATCH` | 设置后回读不一致，保留错误并核对窗口，不能报成功 |
| `NO_ACTIVE_DOCUMENT` | 用打开工具或手动打开模型 |
| `DOCUMENT_CHANGED` | 重新读取活动文档和 token，确认目标后再操作 |
| `TIMEOUT` / `OUTCOME_UNKNOWN` | 检查 SolidWorks 弹窗和操作结果，结束阻塞后重启 MCP；不可直接重试可能已执行的操作 |
| `INVENTORY_CHANGED` | 采集期间层级、配置或查询范围变化，保留部分数据并重新完整采集；不拼接不同范围的页 |
| `GROUPING_REQUIRES_COMPLETE_INVENTORY` | 先用 spatial-export 收齐各页并解决层级缺失；不能用单页或截断树做分组 |
| 空间字段为 null / `partial` | 检查字段级错误和实例状态；不补零；正常已解析实例读不到数据时保留原始返回反馈 |
| 组件树为 `partial` | 检查 errors，记录未解析节点或上限；如需解析组件，由用户明确操作后重读 |

诊断命令：`python -m cadkin sw sw_session_status`。结果输出到终端，不会开启 MCP 协议会话。运行产物留在 `outputs/`。

用户已反馈旧版 15 工具的实测结果；索引/复用按0.18.0清单验证；新增补采执行/回填/比较按0.17.0清单验证；草案检查/补采规划保留0.16.0清单；刚体候选/关节草案保留0.15.0清单；目标图/匹配保留0.14.0清单；模板读取保留0.13.0清单；旧机构链汇总按0.12.0，人工复核段仅作历史兼容；面间隙/法向保留 0.11.0 清单；组件距离保留 0.10.0 清单；面身份核对保留 0.9.0 清单；配合状态/连接复核保留 0.8.0 清单；几何候选保留 0.7.0 清单；Conda、配合与轴线保留 0.6.0 清单；显示/超时修复与分组保留 0.5.0 复测项，启动仍按 0.4.0 清单验证。请按 [44 个工具验收清单](MCP_ACCEPTANCE.md) 记录首次联调结果；后续任务见 [开发计划](DEVELOPMENT_PLAN.md)。

官方说明：[Skills](https://opencode.ai/docs/skills/)、[MCP](https://opencode.ai/docs/mcp-servers/)、[V1/V2 兼容](https://opencode.ai/docs/migrate-v1/)。

Conda 官方说明：[conda run](https://docs.conda.io/projects/conda/en/stable/commands/run.html)。

## 0.13.0 参考模板

模板功能无需启动SolidWorks；现有Conda安装额外依赖后直接运行：

```powershell
python -m cadkin templates --query lifting
python -m cadkin template-extract --template-id gas_lift_bar_stool --output outputs/lift-reference.json
python scripts/verify_reference_templates.py --output outputs/verify-0.13
```

输出用新文件名/目录。自带8个结构摘录不是完整网格模型；默认目录只返回6个reference（其中2个无关节负例），另2个留作后续匹配评测。模板轴线和行程只属于参考。比较工具需要两份原始图和真实来源绑定的对应文件；0.14.0可独立搜索目标实例图的局部候选对应；这些假设尚不是完整刚体图，也不能直接当作本评分工具的真值。

新增错误：USD_DEPENDENCY_MISSING检查当前Conda是否安装templates extra；USD_COMPOSITION_UNSUPPORTED表示输入有外部层/变体等，本版只支持独立归一化USD；NO_RIGID_BODIES不把纯视觉模型当机构；TEMPLATE_INCOMPLETE/COMPARISON_PARTIAL保留风险继续；EVIDENCE_MISMATCH重新核对来源，不能只篡改哈希。

## 0.14.0 使用已有真实来源做模板匹配

先运行本轮自动验收（明确使用模拟来源，不启动SolidWorks）：

```powershell
python scripts/verify_template_matching.py --output outputs/verify-0.14
```

应返回passed=true、18项检查。已有本机真实chain dossier时：

```powershell
python -m cadkin target-graph outputs/chain.json --output outputs/target.json
python -m cadkin match-templates outputs/target.json --output outputs/matches.json
```

没有chain.json时让Agent按独立链汇总流程生成；只加载缺少的采集能力，不让用户填写机械确认。已有连接结果关联的轴线会自动读取，只有独立轴线结果才额外传target-graph的--relations。所有输出使用新文件名。

默认匹配3节点局部窗口、参考库6项；按实际范围可用--pattern-size 2到6。要筛选可用--template-ids gas_lift_bar_stool bench_vise。需要更多竞争解释可用--max-candidates 20；预算不足时先看search_exhaustive/beam_pruned_states，按任务调整--max-states和--beam-width。分数不是百分比，关节类型仅是假设，轴点/限位保留未知。

MATCH_SEARCH_LIMIT为有预算结果，NO_SUPPORTED_MATCH表示本范围内没有受支持候选，均不能说明机构不存在。EVIDENCE_MISMATCH需重算修改后的来源；HELDOUT_TEMPLATE普通分析改用参考项。报告来源partial、同分候选、template_rankings以及缺失/额外联系。

补采执行每次调用sw_execute_evidence_task只处理一个已有只读工具；后续传上一次receipt路径和新的output_path。或用CLI execute-evidence串行完成。文档/位姿变更、TIMEOUT、OUTCOME_UNKNOWN停止后续采集；保留原始文件，不删文件或改token重试。回填/比较分别离线运行，参数与完整示例见0.17.0验收。

## 0.18.0 继续补采前

执行receipt完整且guard通过后，用cad_index_evidence将当前check与观测关联。再调用cad_plan_evidence_tasks并传evidence_index_path；只对collect计划执行，stop则报告剩余风险。约束/面目录索引不替代兼容回填或有限面测量。独立入口为evidence-observation-index，按需交接已有规划/执行/回填/比较。模拟验收：`python scripts/verify_observation_reuse.py --output outputs/verify-0.18`，预期26项passed；实机按[MCP验收](MCP_ACCEPTANCE.md#0180证据关联复用与停止)。

## 自动安排具体面探测（0.19.0）

已有草案check和最新evidence index时，按需加载face-probe-plan，提供组件距离筛选与解析残差阈值，调用cad_plan_face_probes。collect交给evidence-task-execute；完整且guards_passed后交给evidence-observation-index，再携带新索引继续。缺目录时先补目录，已有目录时生成来源绑定的面候选和实际最近点种子。

面探测结果交给独立face-contact-review；按明确阈值解释局部候选，不认定接触或关节。stop时保留风险，不改预算或删索引绕过历史。具体命令与数据检查见[0.19.0验收](MCP_ACCEPTANCE.md#0190自动面候选与有限面探测任务)。

## 把面测量用于更新草案（0.20.0）

每轮面探测完成且保护检查通过后，将当前receipt交接evidence-reintegration；原链已覆盖组件对沿用原阈值，未覆盖对可使用face-contact-review的明确依据。回填完成再独立比较，使用新check与同一receipt建立索引后续轮。缺依据或冲突保留风险，不设置人工确认；不要把旧索引绑定到新check，也不要把历史观测全部当本轮回填。

本次一键验证：`python scripts/verify_face_reintegration.py --output outputs/verify-0.20`，预期28项通过。具体真实文件、命令与失败标准见[0.20.0验收](MCP_ACCEPTANCE.md#0200面证据回填与变化比较)。


## 默认不用模板生成关系草案（0.21.0）

从已有rigid candidates执行`python -m cadkin draft-joints outputs/rigid.json --output outputs/target-draft-0.21.json`，再调用check-joints。默认不传template_ids；无需找到合适参考也能补采、回填与比较。只有需要结构类比时另存显式模板分析，不把reference_joint_kind/reference_dof继承到目标。旧文件仍可读取，但若要更新结论需从原rigid source重算，不能直接修改旧类型或哈希。完整参数及验收见[0.21.0验收](MCP_ACCEPTANCE.md#0210目标证据优先与可选模板)。


## 目标约束组合分析（0.22.0）

从原target graph运行`python -m cadkin analyze-constraints outputs/target.json --distance-tolerance-mm 0.1 --angle-tolerance-deg 0.1 --output outputs/constraints-0.22.json`。MCP等价cad_analyze_constraints。按实例对和源快照读取具体配合、面/轴约束、局部候选、冲突和缺失证据；目标最终类型/DOF仍未知。模板不是此阶段输入。

需要直接配合面和锁定旋转状态时，assembly-mates负责按需传include_reference_geometry=true，保存新原始文件，再重建连接复核/链/目标图；旧基础mates不具备新字段。0.23起增强采集可通过约束缺口计划调度（见下节），不能重置4轮索引或重复基础采集冒充已补足。原文件重放兼容，新的约束报告独立于draft/check。详见[0.22.0验收](MCP_ACCEPTANCE.md#0220目标约束组合分析)。

## 约束缺口自动补采（0.23.0）

已有同一target的check和约束报告时，用`python -m cadkin plan-evidence outputs/check.json --constraint-analysis outputs/constraints.json --output outputs/constraint-plan.json`规划。已有历史时加`--evidence-index 最新索引路径`；报告已绑定索引则自动继承。只执行continuation.action=collect的计划；stop时保留原因和未知。

接着`execute-evidence`串行执行，保护通过后`reintegrate-evidence`回填。成功报告直接给出新check、index和constraint analysis；下一轮用新check/report，不重复索引同receipt。具体命令、结果字段和实机失败标准见[0.23.0验收](MCP_ACCEPTANCE.md#0230约束缺口自动补采与重算)。模拟验收入口为`python scripts/verify_constraint_followup.py --output outputs/verify-0.23`，预期38项通过。

## 局部瞬时运动（0.24.0）

已有原约束报告后，用`python -m cadkin solve-local-constraints outputs/constraints.json --characteristic-length-mm 100 --output outputs/local-motion-0.24.json`。100毫米是示例数值尺度，按当前链代表尺寸选择并说明。MCP等价cad_solve_local_constraints，由独立mechanism-local-motion负责调用与判读。

先读每个快照的状态和缺口，再读矩阵秩/瞬时方向；不能将局部nullity写成目标DOF。无有效配合时仍未知，冲突/数值敏感时保留风险。继承已有来源/index/轮数，离线不连接SolidWorks；补采仍交接原analysis。验收与具体字段见[0.24.0验收](MCP_ACCEPTANCE.md#0240局部瞬时约束求解)，数学范围见[局部约束模型](LOCAL_CONSTRAINTS.md)。

## 单链与高效执行（0.25.0）

常规补采优先`sw_execute_evidence_batch`或`python -m cadkin execute-evidence-batch outputs/plan.json --output outputs/batch-01.json`。未完成沿用同一plan，下一批传`--previous-execution <execution_source.path>`；完整且保护通过才把该receipt交给回填。batch_report_source仅诊断。详细规则见[效率说明](MCP_EFFICIENCY.md)。

原约束报告可交给`cad_solve_chain_constraints`，CLI为`python -m cadkin solve-chain-constraints outputs/constraints.json --reference-occurrence-path "实际实例路径" --characteristic-length-mm 100 --output outputs/chain-motion-0.25.json`。按实际链选择参考及数值尺度；先读摘要，仅需要具体方向才展开完整文件。验收命令与边界见[0.25.0](MCP_ACCEPTANCE.md#0250单链约束与批量执行)。升级后重启OpenCode以加载49工具及客户端300秒上限；COM单步180秒超时没有改变。

## 首次机构链联调（0.26.0）

首次分析一条明确范围的链，按[CHAIN_SESSION.md](CHAIN_SESSION.md)创建当前配置并运行chain-session。打开模型可由现有启动/文档能力完成；本入口只读装配，自动串联初次采集、基线、一次可用增强与瞬时分析，输出逐步耗时。已有历史直接使用原check/index/receipt，不重跑初始化。新MCP目录应有50工具；本机仍使用现有Conda。

## 原生配合独立分析（0.27.0）

当前目录51工具、44个功能skill。已有原始空间/根配合文件可直接用cad_review_root_mates离线建源，不先补圆柱。首次只分析配合时，chain-session配置capture_profile="root_mates"，一次增强采集并保留全部保护。默认geometry_and_mates仍可用；已有check/index/receipt沿用历史。无配合STEP保持未知，不自动借模板补关节。详见[配合独立分析](ROOT_MATE_RELATIONS.md)和[验收](MCP_ACCEPTANCE.md#0270原生配合独立分析)。

## 无配合几何分析（0.28.0）

已有target/check及最新index时，交geometric-connection-analysis解释几何候选，再按缺口交evidence-task-plan或face-probe-plan；不重启chain-session清历史。没有几何源时先补合法圆柱关系/面证据，不把缺配合当自由运动。完整调用与更新/验收见[GEOMETRIC_CONNECTIONS.md](GEOMETRIC_CONNECTIONS.md)。


## 0.29 有限轴向范围

已有geometry/check/latest index时交finite-connection-analysis。新工具cad_analyze_finite_connections离线生成候选范围；缺边界交evidence-task-plan的finite_analysis_path，批次完成后索引再分析。两实例两面8次调用保留6保护；不会重扫全装配。47个功能skill按需读取，54个MCP工具。更新已有Conda内的可编辑安装后重启OpenCode。

验证：`python scripts/verify_finite_connections.py --output outputs/verify-finite-connections-0.29`，预期47项通过。具体流程、结果判读及限制见[有限范围分析](FINITE_CONNECTIONS.md)。没有当前证据时先按原单链入口建立来源，不靠新建链删除旧历史。
