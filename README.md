# 3DModel-RCGN

用 OpenCode + MCP 操作 SolidWorks，逐步实现工业数模自动拆解。当前 **0.31.0 / 59 个工具**：读取证据、批量补采、单链瞬时约束分析；新增有限端面区域、孔区扣除与接触方向候选分析。模板可选，测试STEP已在examples中。

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
python scripts/verify_planar_contacts.py --output outputs/verify-planar-contacts-0.31
```

预期`passed: true`、82项检查；使用合成装配，不代表升降机实测。重跑换新验收目录。实机可告诉OpenCode：

> 复用当前engagement报告、同check和最新index，检查真实邻接端面的有限区域重叠及接触方向。保留孔区和复杂轮廓未知，只补缺失区域，批次执行并沿用四轮历史。

52个功能skill与工具代码隔离。**已能运行单链证据分析流程；尚未验证该升降机实际运动、整机自由度或拆卸路径。**

[有限端面](docs/PLANAR_CONTACTS.md) · [表面补证](docs/SURFACE_ENGAGEMENT.md) · [有限范围分析](docs/FINITE_CONNECTIONS.md) · [几何连接分析](docs/GEOMETRIC_CONNECTIONS.md) · [单链联调](docs/CHAIN_SESSION.md) · [详细验收](docs/MCP_ACCEPTANCE.md#0310有限端面区域与方向) · [使用与排错](docs/OPENCODE_START.md) · [模型进度](docs/MODEL_PROGRESS.md) · [下一步](docs/DEVELOPMENT_PLAN.md) · [工具接口](docs/TOOL_CONTRACTS.md) · [来源许可](THIRD_PARTY_NOTICES.md)
