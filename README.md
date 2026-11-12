# 3DModel-RCGN

用 OpenCode + MCP 操作 SolidWorks，逐步实现工业数模自动拆解。当前 **0.22.0 / 46 个工具**：读取目标证据、组合局部约束、生成关系候选并补采更新；模板可选。测试STEP已在examples中。

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
python scripts/verify_constraint_analysis.py --output outputs/verify-0.22
```

预期`passed: true`、35项检查；原始调用与报告保存在指定目录，重跑换新目录。使用合成CAD，不代表升降机实测。也可告诉OpenCode：

> 用已有目标图做0.22约束组合分析，不使用模板。按功能加载skill、按需读细节。逐组件对列出配合与具体面依据、固定/旋转/滑动候选、冲突和缺失信息。读取失败不默认成可旋转；候选不写成最终类型或自由度。按docs/MCP_ACCEPTANCE.md的0.22.0验收，不设置人工复核。

39个功能skill与工具代码隔离。**已能形成有来源的局部约束候选；尚未求解整机自由度、验证实际运动或生成拆卸路径，也未取得该升降机完整实机结果。**

[详细验收](docs/MCP_ACCEPTANCE.md#0220目标约束组合分析) · [使用与排错](docs/OPENCODE_START.md) · [模型进度](docs/MODEL_PROGRESS.md) · [下一步](docs/DEVELOPMENT_PLAN.md) · [工具接口](docs/TOOL_CONTRACTS.md) · [来源许可](THIRD_PARTY_NOTICES.md)
