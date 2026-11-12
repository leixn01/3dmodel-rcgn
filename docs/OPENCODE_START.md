# OpenCode + SolidWorks 使用与排错

## 首次安装

在已安装 SolidWorks 的 Windows 电脑，取得仓库后进入根目录。使用已有的 Python 3.10+ Conda 环境，下面环境名换为你本地实际名称：

```powershell
git clone https://github.com/leixn01/3dmodel-rcgn.git
cd 3dmodel-rcgn
conda activate 你的环境名
python -m pip install -e ".[solidworks]"
```

已有仓库先 `git pull --ff-only`，再执行依赖安装命令；升级后退出并重新启动 OpenCode，让本地 MCP 进程及工具目录刷新。当前应有 26 个工具。仅维护 Windows；自动启动的就绪检查使用 SolidWorks 2015+ API，旧版不保证可用。STEP 已随仓库提供，无需解压。依赖为官方 MCP SDK 1.29.0、Windows 上的 pywin32 及 SDK 依赖；离线体检无需安装这些依赖。不要把第三方上游仓库也注册成同名 MCP，以免调用到另一套工具。

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
6. 需要重建时明确要求“加载 solidworks-document，重建当前文档”；该操作不保存。工具目前不负责移动零件、添加配合或自动推断运动关系。

用户也可以先手动打开 STEP，再从组件读取开始。若导入为多实体零件，组件树工具会返回 `NOT_ASSEMBLY`，不生成空装配结果。

## 组件分组

模型已打开后执行 README 的 `spatial-export` 和 `group` 命令，或让 Agent 使用 `component-grouping`。指定子装配用 `group ... --scope "完整实例路径"`；人工复核用 `--review outputs/review.json` 加新输出文件名。输入/复核文件必须在项目内，分组输出必须在 outputs 内；不覆盖原文件。旧版单次空间导出改为分页，推荐直接使用新 CLI 收齐，不把一页返回当整机结果。

## 配合与轴线证据

从真实组件树选择一个完整实例路径，让 Agent 分别调用 `sw_component_constraints` 与 `sw_component_cylinders`。前者保留固定/浮动标志及原始配合，后者读取解析圆柱面的轴线/半径；缺失与上下文限制明确返回。按 0.6.0 清单核对，不把没有配合当作自由运动，也不把圆柱轴线直接当旋转副。

## 配合引用面核对

按 0.9.0 清单给圆柱采集传 include_face_references=true，并用新文件重算关系。由 mate-face-matching 调用 sw_match_mate_faces，输入完整空间文件和少量圆柱文件；保存完整 envelope 后交给 connection-review。面身份与配合状态分别报告，旧文件仍可作实例对关联。

## 无配合 STEP 的邻近与距离

按 [0.10.0 清单](MCP_ACCEPTANCE.md#0100组件距离与近接触候选) 先取包含包围盒的完整空间 JSON；component-proximity 离线生成少量待测对，component-distance 逐对只读测量，proximity-review 离线整理。两种阈值都需显式给出，并注明探索值或真实工程依据。

已有两条实例路径时可独立测量，不必先读配合或圆柱。需要筛选时只读已有空间文件；只有缺少输入才补采，不强制加载三套 skill。partial、未测和缺失包围盒保留未知，不能写成零距离或确认机械连接。

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
| 缺少新增工具 | 更新仓库并安装依赖，退出并重新启动 OpenCode；核对 MCP 工具目录应为 26 个 |
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

用户已反馈旧版 15 工具的实测结果；新增组件距离按 0.10.0 清单验证；面身份核对保留 0.9.0 清单；配合状态/连接复核保留 0.8.0 清单；几何候选保留 0.7.0 清单；Conda、配合与轴线保留 0.6.0 清单；显示/超时修复与分组保留 0.5.0 复测项，启动仍按 0.4.0 清单验证。请按 [26 个工具验收清单](MCP_ACCEPTANCE.md) 记录首次联调结果；后续任务见 [开发计划](DEVELOPMENT_PLAN.md)。

官方说明：[Skills](https://opencode.ai/docs/skills/)、[MCP](https://opencode.ai/docs/mcp-servers/)、[V1/V2 兼容](https://opencode.ai/docs/migrate-v1/)。

Conda 官方说明：[conda run](https://docs.conda.io/projects/conda/en/stable/commands/run.html)。
