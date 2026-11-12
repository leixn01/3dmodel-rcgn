# 当前版本 MCP 实机验收

目标：在安装 SolidWorks 的 Windows 电脑，通过 OpenCode 实际调用当前工具（31个既有工具＋3个离线模板工具），核对返回值与 SolidWorks 窗口。离线测试及模拟后端不能作为实机通过证据。

## 准备与连接

1. 在仓库根目录执行 `git pull --ff-only`，按 README 安装或更新 `.[solidworks,templates]`，退出并重启 OpenCode。先完成 0.6.0 的 Conda 环境核对；SolidWorks 未运行时再按 0.4.0 启动，无需手动提前打开。
2. 运行 `opencode mcp list`，确认 `solidworks` 已连接；进入 OpenCode，确认 MCP 工具目录包含当前 34 个工具。客户端可能给工具名添加服务器前缀。
3. 记录提交 SHA（`git rev-parse HEAD`）、Windows/Python/OpenCode/SolidWorks 版本。MCP 已连接仅代表协议可用，必须继续检查 `sw_session_status`。

用户最新反馈：在 SolidWorks 2025、STEP 导入装配的环境对旧版 15 个工具逐项调用，11 项 API 通过，2 项失败（辅助对象显示），2 项部分通过（组件隐藏实际生效但超时、空间清单小范围正确而全量超时）。原图报告 254 个组件、60 秒超时，未提供提交 SHA 或原始 JSON；该反馈不等于 0.5.0 已验收。0.4.0 起已有第 16 个启动工具、180 秒调用上限；本次修复不能仅靠调高超时宣称成功。先完成下面 0.5.0 复测。

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

0.7.0 新增第 20 个工具 `cad_component_relations`，流程独立于角色分组和 COM 读取。先按下方 Conda 命令更新并重新启动 OpenCode，核对版本 **0.12.0 / 31 个工具**（本节保留 0.7.0 新增项）。软件启动/显示修复、空间和圆柱的实机核对仍分别执行原有清单。

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

当前版本应为 0.12.0，工具数 31（本节保留 0.6.0 新增项）。升级后要从同一已激活终端重新启动 OpenCode。调用 `sw_session_status({})`，核对 runtime.python_executable 与终端打印路径一致、matches_conda_prefix=true；软件未运行时 connected=false 也应带这些字段。与目标 Conda 不符即本项失败，不继续把其他环境的测试当作通过。配置不硬编码环境名称或机器路径。

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

本节保留 0.5.0 的修复验收项；当前更新应显示 0.12.0、31 个工具（0.5.0 时为 17 个）。退出并重新启动 OpenCode，确认含 `cad_group_components`。若仍为 15 个工具或仍报旧的 60 秒上限，先核对所用目录、解释器与 MCP 进程。使用已有打开的测试装配，记录 SHA、软件版本、PID、当前文档/配置/token，以及修改前的选择/显隐/dirty。不要为测试关闭有未保存工程的会话。

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

> 按 docs/MCP_ACCEPTANCE.md，在当前 Windows 和 SolidWorks 上逐项验收 31 个 MCP 工具。测试模型已在 examples/three_servo_lift/3X Lift Assembly.STEP。串行调用，记录真实参数、原始返回和需要我核对的窗口现象；重建使用 outputs 下的新工作副本，不保存覆盖原始输入。将结果存入 outputs 的新目录，不把模拟测试、协议连通或部分结果写成实机全部通过。

当前仓库已验证离线逻辑和真实 stdio 协议；用户已反馈旧版 15 个工具的实测状态，修复、分组、证据读取和本次关系候选仍需目标 SolidWorks 与 OpenCode 客户端验证。零件移动、配合编辑、CAD 文件保存/导出及机械运动副确认不在当前 34 个工具范围内；已包含几何关系候选；空间结果 JSON 可由客户端或 CLI 保存。

后续每次功能变更都在此追加对应版本的操作、预期返回、人工核对和失败标准。每条记录注明提交 SHA、工具参数、原始返回文件、窗口核对者与结论；没有证据不沿用上版“通过”。
