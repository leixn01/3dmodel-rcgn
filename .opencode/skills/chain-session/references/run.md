# 配置与调用

在仓库根目录使用已激活Conda的python。CLI使用与MCP相同的工具服务和STA；不另起MCP客户端，不并行执行另一组CAD任务。SolidWorks与目标装配应由对应能力打开；本入口只读当前装配。

将配置保存为outputs下新JSON。字段：

| 字段 | 规则 |
| --- | --- |
| expected_document_token | 当前sw_active_document返回的24位token |
| occurrence_paths | 当前树的2–20个唯一叶实例完整路径 |
| chain_name | 说明范围的名字；不证明识别成功 |
| reference_occurrence_path | 必须属于所选路径；相对参考，不是物理固定 |
| characteristic_length_mm | 0.001–1000000；依据该链实际尺度选择并说明 |
| distance_tolerance_mm | 正有限毫米公差；示例0.1不代表该模型已校准 |
| angle_tolerance_deg | (0,5]度；示例0.1不代表已校准 |
| capture_profile | 可选geometry_and_mates（默认）或root_mates；后者首轮仅采增强根配合，不扫描圆柱 |
| inventory_path | 可选已有完整空间清单路径；身份/姿态仍由原保护校验 |

```powershell
python -m cadkin chain-session outputs/chain-session-config.json --output outputs/chain-session-0.27.json
```

缺inventory_path时分页采集完整清单，默认不读取全量包围盒。2N+2个保护加一次根配合和N个圆柱扫描正好占初始3N+3任务预算；具体任务仍由原规划器决定，缺失/不可采集不补造。每批20步、30秒软预算；继续的是同一计划尚未执行的步骤，不是重新扫描。之后最多一次增强配合补采，与全项目4轮历史共享。

完整原始调用、配置哈希、receipt、index和分析放在报告同名-files目录。stdout只输出摘要。`workflow_complete=true`表示受限流程正常结束，未知仍可能很多；不等于机构已识别或可以运动。查看solution_summary的coverage和每个snapshot，必要时按solution路径读细节。

## 只读配合模式

首次只分析原生配合可在配置加capture_profile="root_mates"。v5初始计划执行一次include_reference_geometry=true的sw_mate_inventory，预算为2N+3：前后文档与每个实例保护共2N+2，加一次采集。其后仍用原基线/索引/分析/求解工具；通常一轮，基础模式默认行为不变。

该模式不会自动退回圆柱扫描。无配合、失败或partial保留未知和尝试，不重采；后续需要几何能力时按缺口另行规划并沿用最新index。已有receipt/check/index不能通过切模式重置历史。有现成原始配合与空间清单时可先交接root-mate-review离线处理，避免重采。
