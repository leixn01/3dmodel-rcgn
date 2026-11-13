# 首次单链联调（0.26.0）

本版把首次“采集→建立来源→补充配合几何→单链瞬时求解→计时报告”串为一个可执行入口。CLI复用同一套MCP工具服务和STA；新MCP工具cad_create_chain_baseline只做离线初始化。工具、启动/选范围/流程说明仍分别组织。当前50工具、43个功能skill。

## 在本机使用

在已有Conda环境中更新安装，重启OpenCode。让agent使用当前树选择2–20个叶实例组成一个小范围候选链，记录选择依据；这一步不宣称链已自动识别。若未启动/打开模型，由独立启动和文档能力完成。首次入口只读当前装配，不移动、重建、保存或关闭模型。

可直接给OpenCode：

> 打开examples中的升降机，按chain-session流程选择一条小范围候选升降链，用当前实例路径和token创建配置并完成首次联调。已有这条链的receipt/check/index时沿用历史，不重新采集。报告已知约束、未知项、停止原因和最耗时的工具；模板可省略，不设置人工复核。

配置文件由agent根据实际树创建，不需要用户手填。示例仅展示字段，token/路径/尺度/公差必须取自当前任务：

```json
{
  "expected_document_token": "当前24位token",
  "chain_name": "本次选择的候选升降链",
  "occurrence_paths": ["实际叶实例路径A", "实际叶实例路径B"],
  "reference_occurrence_path": "实际叶实例路径A",
  "characteristic_length_mm": 100,
  "distance_tolerance_mm": 0.1,
  "angle_tolerance_deg": 0.1
}
```

```powershell
python -m cadkin chain-session outputs/chain-session-config.json --output outputs/chain-session-0.26.json
```

参考实例只是相对坐标选择，不证明物理接地。尺度100mm、公差0.1mm/0.1度是示例，不是已校准的升降机参数。可选inventory_path复用已有完整空间清单；否则自动分页，跳过较慢的全量包围盒。目标实例的前后姿态保护仍保留。

## 执行和输出

初始空证据链使用原规划器，任务预算为3N+3（N个实例的前后保护、两次文档保护、根配合及N个圆柱采集）；不修改任务。按每批20步/30秒软预算串行执行，完成后离线创建首次关系/连接基线和index。现有回填只能更新已有兼容来源，本工具补齐了首次“还没有来源”这一入口。

至少两个完整圆柱envelope才建立现有关系基线，允许真实的完整空扫描，不伪造无圆柱。完整根配合还需关联到该基线；不足时记录未应用采集和未知。完整/失败/partial尝试都进入原索引，首轮计为1/4。最多再执行一次有依据的增强配合补采，通常1–2轮，不自动使用剩余轮数去盲扫。没有配合不会补造关节。

| 返回字段 | 含义 |
| --- | --- |
| workflow_complete | 受限流程正常结束；不是机械识别完成 |
| stop_reason | 无新支持采集、已有增强尝试等停止原因 |
| handoffs | 最新check、index、constraints、solution等路径及哈希 |
| evidence_summary | 可复用观测和保留失败尝试数量 |
| remaining_findings_summary | 尚存未知/风险数量 |
| solution_summary | 各源快照支持的瞬时约束结果；未知仍为null |
| report_source | 完整运行报告；原始调用另存在同名-files目录 |

performance.stage_tool_timings记录入口调用及离线派生耗时；cad_capture_tool_timings记录批次内部每个CAD工具耗时。前者包含后者，不能相加。计时包含工具校验/STA/COM，不是单个API纯耗时，也不包含agent思考/网络。

## 续跑和边界

已有结果使用最新check/index/constraints交接原规划器，不能换新输出名重跑初始化清掉历史。中断按最后完整call日志/原receipt继续；空白report表示中断，不能当成功。TIMEOUT不表示原COM取消，先核对软件状态；文件占用时不删文件盲目重试。保护失败禁止与旧快照回填。CLI错误返回非零退出码。

本入口不自动恢复进程崩溃，也不扫描全目录猜测其它会话历史。原始STEP及所有输入不覆盖。框架能跑通，不代表这台升降机已有真实链级结果。下一步仍需在用户SolidWorks上取得原始report，按缺口补充几何推断/配合类型，再开发受控运动与干涉检查。

## 本版验收

```powershell
python scripts/verify_chain_session.py --output outputs/verify-chain-session-0.26
```

35项检查使用显式合成装配与生产编排逻辑，覆盖闭环、无配合、增强失败、超时、历史与计时；不连接真实SolidWorks，不代表实机识别率。完整验收见[MCP_ACCEPTANCE.md](MCP_ACCEPTANCE.md#0260首次单链联调)。
