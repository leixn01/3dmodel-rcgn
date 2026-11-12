# Skill、工具、MCP 与 SolidWorks

| 层 | 实现位置 | 职责 |
| --- | --- | --- |
| Skill | `.opencode/skills/<名称>/SKILL.md` | 任务流程、工具选择与结果判断 |
| 工具 | `cadkin/tools/solidworks.py` | 固定工具目录、参数 Schema、统一错误 |
| 分页汇总/分组 | `cadkin/tools/spatial.py`、`grouping.py` | 逐页采集和离线角色候选；分组不创建 COM 对象 |
| 关系候选 | `cadkin/tools/relations.py` | 独立离线轴线比较、公差/来源校验与预算；共享 inventory.py 的清单校验，不依赖分组算法或 COM |
| MCP | `cadkin/mcp_server.py` | 官方 SDK 的 stdio 协议、工具注册与结构化返回 |
| CLI | `cadkin/__main__.py` | 调用同一工具层、将 JSON 保存到新文件 |
| COM 适配 | `cadkin/adapters/solidworks.py`、`display.py`、`spatial.py`、`session.py`、`constraints.py`、`cylinders.py` | 会话/文档/组件 API；显示、空间读取和显式启动独立模块，通过同一 STA 执行 |
| 配合状态 / 连接复核 | `cadkin/adapters/mate_inventory.py`、`cadkin/tools/connections.py` | 根配合 COM 读取与离线文件关联分开；原始 mate 读取共用 mate_records.py |
| 面身份核对 | `adapters/face_identity.py`、`adapters/mate_faces.py`、`tools/mate_faces.py`、`tools/face_matches.py` | 文件校验、STA 内对象解析/比较与离线解释分离；共享根配合遍历，不跨线程传 COM 对象 |
| 组件距离 / 近接触候选 | `adapters/component_distance.py`、`distance.py`、`tools/proximity.py`、`tools/proximity_review.py` | 在线单对 API、纯数值校验、离线待测清单与判读分开；与配合面身份无强制依赖 |
| 面目录 / 局部面探测 / 候选复核 | `adapters/faces.py`、`adapters/face_probe.py`、`tools/face_sources.py`、`tools/face_contacts.py`、`face_geometry.py` | 只读 COM、来源文件校验、纯变换/法向计算和离线分类分开；不依赖配合/圆柱链 |
| 机构链清单 / 旧复核兼容 | `tools/chain_sources.py`、`tools/chain.py`、`tools/chain_review.py` | 重算已有来源、按显式范围汇总、记录人工声明分别实现；全程离线、不调用COM或自动合并刚体 |
| 模板资源 | `cadkin/resources/mechanisms/` | 固定源版本的结构摘录、目录、哈希及许可；不包含运行流程 |
| 模板算法 | `cadkin/templates/` | 目录、USD解析、给定对应的图评分；不依赖COM或skill |
| 模板文件边界 | `cadkin/tools/templates.py` | 路径、哈希、独占新输出与错误envelope |
| 目标图与匹配算法 | `cadkin/matching/target.py`、`search.py` | 纯特征适配、连通窗口与有预算搜索，不读skill、不连接COM |
| 匹配来源与文件边界 | `cadkin/tools/matching.py` | 复用链级来源重放、重算目标图、校验模板/输出与错误 |
| 空间计算 | `cadkin/geometry.py` | 无 COM 依赖的矩阵、单位与近似包围盒转换 |
| STA 调度 | `cadkin/adapters/sta.py` | 单线程串行调用、超时及取消后的状态处理 |
| 开源兼容片段 | `cadkin/_vendor/sw_mcp.py` | 从固定 SW_MCP 版本提取并修改的 COM 成员访问逻辑 |

Agent 按 skill 选择 MCP 工具，MCP 调用工具层，工具在 STA 线程内调用 COM 适配器。CLI 也走同一工具层。输入体检 `cadkin/tools/intake.py` 保持独立，无 Windows/MCP 依赖。

当前采用 Python + pywin32 + 官方 MCP Python SDK 1.29.0。本地 stdio 服务由 OpenCode 启动，无需开放网络端口或注册 SolidWorks 插件。MCP/COM 进程必须运行在安装 SolidWorks 的 Windows 电脑上；使用已激活 Conda 环境中的 Python；CI 在 Windows 上创建 Conda 的 Python 3.10/3.12 环境。

## 隔离

- Skill 不包含执行代码、COM 对象、MCP 注册或客户端配置；默认按需发现，不互相强制加载完整流程。
- 工具不读取 SKILL.md，不依赖 OpenCode，也不调用 LLM 补造 API 结果。
- MCP 只处理协议；组件遍历和具体操作在适配层，不在协议入口复制。
- COM 对象不离开 STA 线程；输出只含 JSON 数据。失败时传递普通错误数据，不将持有 COM 引用的原异常 traceback 交到外部线程。
- Skill 是流程说明，不是权限沙箱。工具目录限制可调用动作；当前没有任意脚本、保存覆盖、关闭文档、修改配合或移动组件入口。

多个 skill 可复用原子工具，一个 MCP 服务提供多个工具，无需为每个 skill 启动一个服务器。

## 逐层披露

1. 发现层只读取各 skill 的 name/description，按职责选择。
2. 进入后读取简短 SKILL.md，获得输入/输出、最小流程及关键限制。
3. 只有参数不明、需要解释字段或遇到失败时，读取入口明确链接的 references 对应文件/段落。不主动读全套参考、其他 skill 或完整开发文档；验收任务才读对应验收章节。

当前 25 个入口保持简短；详细流程移到 references，配合/面核对按字段、失败分支或判读拆分。references 只含说明，执行仍在工具/适配层。已有文件足够时离线完成；缺少哪个输入才调用对应采集能力，不建立强制串联的全套流程。

## 功能拆分

| Skill | 职责 |
| --- | --- |
| `cad-intake` | 离线 STEP/ZIP 体检 |
| `solidworks-start` | 独立启动/复用会话、可见性及就绪检查，不打开模型 |
| `solidworks-connect` | 会话与活动文档检查、连接诊断 |
| `assembly-inventory` | 装配组件树、部分结果核对与清单导出 |
| `component-spatial` | 单实例/分页空间信息、单位与近似边界说明、完整 JSON 导出 |
| `component-grouping` | 叶实例角色候选、范围选择与证据缺口，不修改 CAD |
| `component-constraints` | 指定组件固定标志、原始配合/引用参数及上下文限制 |
| `component-cylinders` | 匹配配置零件定义的圆柱面轴线/半径候选 |
| `component-relations` | 指定实例的离线同轴/平行候选、公差、来源与待确认项 |
| `assembly-mates` | 根配合特征状态、根坐标及引用实例身份，不识别运动副 |
| `mate-face-matching` | 已保存圆柱面与根配合引用面的在线身份核对 |
| `connection-review` | 已有几何/配合文件的实例对及可验证面配对关联，不连接 COM |
| `component-proximity` | 已有完整空间清单的离线待测组件对，不测量、不确认接触 |
| `component-distance` | 当前两个零件实例的只读距离与最近点，可独立调用 |
| `proximity-review` | 已有待测清单及距离文件的离线复核，不启动 CAD |
| `component-faces` | 单实例面目录、描述符与持久引用，保留失败与预算 |
| `face-gap-probing` | 两个指定有限面的局部测点间隙/法向，不宣称全局最小值 |
| `face-contact-review` | 已有探测文件的离线阈值复核，不连接 CAD |
| `chain-evidence` | 明确叶实例范围的离线证据汇总，保留未知/边界/待核对差异 |
| `mechanism-template-search` | 仅检索参考目录、来源与划分 |
| `mechanism-template-extract` | 只提取单个USD参考结构，保留未知 |
| `mechanism-template-compare` | 根据已有对应评分，保留缺失/额外连接 |
| `mechanism-target-graph` | 原始链清单到实例证据图；不执行搜索 |
| `mechanism-template-match` | 图到局部模板假设；不重新采集CAD |
| `solidworks-document` | 明确请求的打开/导入、重建操作 |
| `solidworks-view` | 标准视图和缩放 |
| `solidworks-display` | 基准面等类别显示过滤与总开关 |
| `component-visibility` | 单个装配实例显隐与隐藏父级核对 |
| `component-selection` | 按完整实例路径选择或清空选择 |

软件启动、文档操作、空间读取与显示操作相互独立；后续详细几何、配合提取、运动关系推断继续独立增加。

## 验证边界

代码、CLI 和 MCP 已实现；单元测试使用显式测试替身验证逻辑，stdio 测试实际进行握手及工具调用。它们不证明某个 SolidWorks 版本的 COM 兼容性。用户最新 SolidWorks 2025 旧版 15 工具反馈为 11 项 API 通过、2 项失败、2 项部分通过；0.5.0 修复/分组及 0.6.0 证据读取及 0.7.0 关系候选、0.8.0 配合状态/连接复核、0.9.0 面身份核对、0.10.0 组件距离及 0.11.0 面探测仍需按验收文档在用户电脑复测。

只保留一个 SolidWorks 进程。调用串行，不排队叠加动作。超时不能撤回已经进入 SolidWorks 的操作，客户端要核对现场并重启 MCP。当前版本使用严格的 late binding；遇到无法标记为方法的成员会返回错误，不尝试无参数误调用。

## 来源

[代码复用与许可](../THIRD_PARTY_NOTICES.md)记录精确来源、提交、复用范围及修改。

官方说明：[SolidWorks COM API](https://help.solidworks.com/2026/english/SolidWorks/sldworks/c_solidworks_api.htm?id=3.26)、[MCP SDK 1.x](https://py.sdk.modelcontextprotocol.io/v1/)、[OpenCode MCP](https://opencode.ai/docs/mcp-servers/)、[Skills](https://opencode.ai/docs/skills/)。

## 0.13.0 自动流程边界

默认不等待人工复核；旧requires_review/review_flags指证据需继续分析，无法补全就在结论说明风险。chain-review已从自动发现目录移除，旧工具仅保留兼容。引用数据、匹配算法、工具、skill分别维护。0.14.0已独立实现目标图适配与局部匹配；旧比较工具仍要求来源绑定的body_map，不负责生成对应。匹配报告不是比较工具的真值输入。

29个skill仅入口信息常驻；references按需加载。usd-core通过templates extra可选安装；目录查询无需USD，解析工具不启动CAD，生产工具也不下载参考原始大文件。

## 0.14.0 数据流

原始采集与离线证据 → chain dossier → target graph → local template hypotheses。每层重放已有来源并核对哈希；target图可不包含所有几何，但缺失要显式保留。一个叶实例对应一个节点，不提前合并。目标图处理坐标/证据标准化；搜索只读取标准字段，名称/角色只作上下文。

搜索按模板连通窗口分配状态预算，beam剪枝与返回数量裁剪分别记录。采用连接支持与相对无向轴角作排序；具体权重和公式随结果保存，类型、轴点、行程和传动比不被宣称已恢复。测试与验收脚本中的参考派生控制不作为目标CAD独立准确率。
