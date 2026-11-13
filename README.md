# 3DModel-RCGN

用 OpenCode + MCP 操作 SolidWorks，逐步实现工业数模自动拆解。当前 **0.23.0 / 46 个工具**：根据约束缺口补采、回灌重算并保留历史，防止重复扫描；模板可选。测试STEP已在examples中。

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
python scripts/verify_constraint_followup.py --output outputs/verify-0.23
```

预期`passed: true`、38项检查；原始调用与报告保存在指定目录，重跑换新目录。使用合成CAD，不代表升降机实测。也可告诉OpenCode：

> 按 docs/MCP_ACCEPTANCE.md 的0.23.0流程，用已有check和约束报告安排有界补采。沿用最新索引，按功能加载skill并按需读细节；完成采集、回填和约束重算后列出新增依据、剩余未知及停止原因，不设置人工复核。

39个功能skill与工具代码隔离。**已能形成有来源的局部约束候选；尚未求解整机自由度、验证实际运动或生成拆卸路径，也未取得该升降机完整实机结果。**

[详细验收](docs/MCP_ACCEPTANCE.md#0230约束缺口自动补采与重算) · [使用与排错](docs/OPENCODE_START.md) · [模型进度](docs/MODEL_PROGRESS.md) · [下一步](docs/DEVELOPMENT_PLAN.md) · [工具接口](docs/TOOL_CONTRACTS.md) · [来源许可](THIRD_PARTY_NOTICES.md)
