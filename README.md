# 3DModel-RCGN

用 OpenCode + MCP 操作 SolidWorks，逐步实现工业数模自动拆解。当前 **0.25.0 / 49 个工具**：读取证据、批量补采回填，并计算单条机构链的瞬时运动及闭环限制；模板可选。测试STEP已在examples中。

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

## 验证这次新增功能

```powershell
python scripts/verify_chain_constraints.py --output outputs/verify-chain-0.25
python scripts/verify_mcp_efficiency.py --output outputs/verify-speed-0.25
```

预期`passed: true`、分别43项、10项检查；原始调用与报告保存在指定目录，重跑换新目录。使用合成配合，不代表升降机实测。也可告诉OpenCode：

> 按 docs/MCP_ACCEPTANCE.md 的0.25.0流程，用已有约束报告计算单链剩余瞬时运动和闭环限制；补采优先有预算的批量执行。按功能加载skill、按需读细节，记录特征长度，保留来源和补采历史；结论说明缺失、冲突和风险，不设置人工复核。

41个功能skill与工具代码隔离。**已能求解有依据的单链瞬时约束；尚未求解整机自由度、验证实际运动或生成拆卸路径，也未取得该升降机完整实机结果。**

[详细验收](docs/MCP_ACCEPTANCE.md#0250单链约束与批量执行) · [使用与排错](docs/OPENCODE_START.md) · [模型进度](docs/MODEL_PROGRESS.md) · [下一步](docs/DEVELOPMENT_PLAN.md) · [工具接口](docs/TOOL_CONTRACTS.md) · [来源许可](THIRD_PARTY_NOTICES.md)
