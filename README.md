# 3DModel-RCGN

用 OpenCode + MCP 操作 SolidWorks，逐步实现工业数模自动拆解。当前 **0.28.0 / 52 个工具**：读取证据、批量补采、单链瞬时约束分析；新增无配合模型的几何连接解释与定向距离补采。模板可选，测试STEP已在examples中。

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
python scripts/verify_geometric_connections.py --output outputs/verify-geometric-connections-0.28
```

预期`passed: true`、44项检查；使用合成装配，不代表升降机实测。重跑换新验收目录。实机可告诉OpenCode：

> 复用当前候选链的target/check及最新index，分析几何连接的竞争解释。缺距离时定向补采，已有近距离则按需探测有限面，沿用保护和四轮历史。报告依据、未验证条件和风险，不强制套模板。

45个功能skill与工具代码隔离。**已能运行单链证据分析流程；尚未验证该升降机实际运动、整机自由度或拆卸路径。**

[几何连接分析](docs/GEOMETRIC_CONNECTIONS.md) · [单链联调](docs/CHAIN_SESSION.md) · [详细验收](docs/MCP_ACCEPTANCE.md#0280几何连接解释与定向补采) · [使用与排错](docs/OPENCODE_START.md) · [模型进度](docs/MODEL_PROGRESS.md) · [下一步](docs/DEVELOPMENT_PLAN.md) · [工具接口](docs/TOOL_CONTRACTS.md) · [来源许可](THIRD_PARTY_NOTICES.md)
