# 3DModel-RCGN

用 OpenCode + MCP 操作 SolidWorks，逐步实现工业数模自动拆解。当前 **0.26.0 / 50 个工具**：读取证据、批量补采回填、单链瞬时约束分析，并提供首次单链联调与耗时报告。模板可选，测试STEP已在examples中。

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
python scripts/verify_chain_session.py --output outputs/verify-chain-session-0.26
```

预期`passed: true`、35项检查；使用合成装配，不代表升降机实测。重跑换新验收目录。实机可告诉OpenCode：

> 打开examples中的升降机，按chain-session流程选择一条小范围候选升降链，创建实际配置并完成首次联调。已有receipt/check/index时沿用历史。报告已知约束、未知项、停止原因和最耗时的工具，按功能加载skill，不设置人工复核。

43个功能skill与工具代码隔离。**已能运行单链证据分析流程；尚未验证该升降机实际运动、整机自由度或拆卸路径。**

[单链联调](docs/CHAIN_SESSION.md) · [详细验收](docs/MCP_ACCEPTANCE.md#0260首次单链联调) · [使用与排错](docs/OPENCODE_START.md) · [模型进度](docs/MODEL_PROGRESS.md) · [下一步](docs/DEVELOPMENT_PLAN.md) · [工具接口](docs/TOOL_CONTRACTS.md) · [来源许可](THIRD_PARTY_NOTICES.md)
