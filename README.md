# 3DModel-RCGN

用 OpenCode + MCP 操作 SolidWorks，逐步实现工业数模自动拆解。当前 **0.27.0 / 51 个工具**：读取证据、批量补采、单链瞬时约束分析；原生配合可独立分析，新增只读配合的快速采集模式。模板可选，测试STEP已在examples中。

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
python scripts/verify_root_mates.py --output outputs/verify-root-mates-0.27
```

预期`passed: true`、54项检查；使用合成装配，不代表升降机实测。重跑换新验收目录。实机可告诉OpenCode：

> 打开examples中的升降机，先复用已有采集历史；若是首次单链分析，使用chain-session的root_mates模式，按实际实例路径生成配置。报告已建模约束、未知项、停止原因和调用耗时；无配合不补造关节，按功能逐层加载skill。

44个功能skill与工具代码隔离。**已能运行单链证据分析流程；尚未验证该升降机实际运动、整机自由度或拆卸路径。**

[配合独立分析](docs/ROOT_MATE_RELATIONS.md) · [单链联调](docs/CHAIN_SESSION.md) · [详细验收](docs/MCP_ACCEPTANCE.md#0270原生配合独立分析) · [使用与排错](docs/OPENCODE_START.md) · [模型进度](docs/MODEL_PROGRESS.md) · [下一步](docs/DEVELOPMENT_PLAN.md) · [工具接口](docs/TOOL_CONTRACTS.md) · [来源许可](THIRD_PARTY_NOTICES.md)
