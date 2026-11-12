# 3DModel-RCGN

用 OpenCode + MCP 操作 SolidWorks，逐步实现工业数模自动拆解。当前 **0.21.0 / 45 个工具**：读取目标证据、整理关系草案、补采与更新；默认不需要模板，参考结构仅作可选类比。测试STEP已在examples中。

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
python scripts/verify_target_evidence.py --output outputs/verify-0.21
```

预期`passed: true`、27项检查。报告和原始调用保存在指定目录；重复运行换新目录。合成目标配真实参考资产，不代表升降机实测。也可告诉OpenCode：

> 从已有rigid candidates重新生成不使用模板的目标关系草案，再检查并规划必要补采。按docs/MCP_ACCEPTANCE.md的0.21.0步骤验收；按功能加载skill、按需读细节。模板只在需要类比时使用，不把参考关节类型或自由度复制给目标；未知保留风险，不设置人工复核。

38个功能skill与工具代码隔离。**已接通目标关系、具体面测量、草案更新与防重复续轮；关节类型和自由度仍需目标约束/运动证据，尚未求解运动或生成拆卸路径，也未取得该升降机完整实机结果。**

[详细验收](docs/MCP_ACCEPTANCE.md#0210目标证据优先与可选模板) · [使用与排错](docs/OPENCODE_START.md) · [模型进度](docs/MODEL_PROGRESS.md) · [下一步](docs/DEVELOPMENT_PLAN.md) · [工具接口](docs/TOOL_CONTRACTS.md) · [来源许可](THIRD_PARTY_NOTICES.md)
