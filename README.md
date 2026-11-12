# 3DModel-RCGN

用 OpenCode + MCP 操作 SolidWorks，逐步实现工业数模自动拆解。当前 **0.17.0 / 43 个工具**：读取模型证据、生成机构候选、检查草案，并执行一轮只读补采、兼容证据回填和前后比较。测试STEP已在examples中。

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
python scripts/verify_evidence_execution.py --output outputs/verify-0.17
```

预期`passed: true`、30项检查。报告、原始调用及结果保存在指定目录；重复运行换新目录。使用显式模拟CAD，不代表升降机实测。也可告诉OpenCode：

> 按docs/MCP_ACCEPTANCE.md的0.17.0步骤，执行已有升降链补采计划，回填兼容证据并比较前后草案。按功能加载skill，详细说明按需读取，不设置人工复核；报告实际采集、已回填、补充上下文和剩余风险。

36个功能skill与工具代码隔离。**已支持一轮有界补采闭环；面目录和单实例约束仍需后续关联才能参与关节判断。尚未实现整机自动划链、运动求解或拆卸路径，也未取得该升降机完整实机结果。**

[详细验收](docs/MCP_ACCEPTANCE.md#0170只读补采执行证据回填与比较) · [使用与排错](docs/OPENCODE_START.md) · [模型进度](docs/MODEL_PROGRESS.md) · [下一步](docs/DEVELOPMENT_PLAN.md) · [工具接口](docs/TOOL_CONTRACTS.md) · [来源许可](THIRD_PARTY_NOTICES.md)
