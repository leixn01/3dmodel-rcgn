# 3DModel-RCGN

用 OpenCode + MCP 操作 SolidWorks，逐步实现工业数模自动拆解。当前 **0.29.0 / 54 个工具**：读取证据、批量补采、单链瞬时约束分析；新增有限圆柱面边界读取、轴向范围比较与定向补采。模板可选，测试STEP已在examples中。

## 更新与使用

在仓库根目录、你已有的 Conda 环境中执行：

```powershell
conda activate 你的环境名
git pull --ff-only
python -m pip install -e ".[solidworks,templates]"
opencode mcp list
opencode
```

Windows + Python 3.10+ + 桌面版SolidWorks；不需要.venv。升级后重启OpenCode。打开模型任务可自动启动SolidWorks；已有证据可离线分析。

## 验证本次新增功能

```powershell
python scripts/verify_finite_connections.py --output outputs/verify-finite-connections-0.29
```

预期`passed: true`、47项检查；使用合成装配，不代表升降机实测。重跑换新验收目录。实机可告诉OpenCode：

> 复用当前geometry报告、check和最新index，分析候选圆柱面的有限轴向范围；缺边界时只补指定面，沿用保护和四轮历史。报告重叠或分离及未知，不把范围当行程或已确认运动副。

47个功能skill与工具代码隔离。**已能运行单链证据分析流程；尚未验证该升降机实际运动、整机自由度或拆卸路径。**

[有限范围分析](docs/FINITE_CONNECTIONS.md) · [几何连接分析](docs/GEOMETRIC_CONNECTIONS.md) · [单链联调](docs/CHAIN_SESSION.md) · [详细验收](docs/MCP_ACCEPTANCE.md#0290有限圆柱边界与轴向范围) · [使用与排错](docs/OPENCODE_START.md) · [模型进度](docs/MODEL_PROGRESS.md) · [下一步](docs/DEVELOPMENT_PLAN.md) · [工具接口](docs/TOOL_CONTRACTS.md) · [来源许可](THIRD_PARTY_NOTICES.md)
