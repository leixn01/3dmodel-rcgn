# 3DModel-RCGN

用 OpenCode + MCP 操作 SolidWorks，逐步实现工业数模自动拆解。当前 **0.19.0 / 45 个工具**：读取证据、生成机构候选、补采与更新草案；现可从组件最近点自动筛选具体面、安排有限面探测，并记住已尝试结果。测试STEP已在examples中。

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
python scripts/verify_face_planning.py --output outputs/verify-0.19
```

预期`passed: true`、30项检查。报告和原始调用保存在指定目录；重复运行换新目录。使用显式模拟CAD，不代表升降机实测。也可告诉OpenCode：

> 按docs/MCP_ACCEPTANCE.md的0.19.0步骤，用当前草案check和最新证据索引，自动规划、执行具体面探测并建立新索引。按功能加载skill，详细说明按需读取；保留阈值依据、竞争面和预算，停止时报告剩余风险，不设置人工复核。

38个功能skill与工具代码隔离。**已接通面候选→有限面测量→索引复用；局部间隙仍是候选证据，尚未自动回填关节草案、求解运动或生成拆卸路径，也未取得该升降机完整实机结果。**

[详细验收](docs/MCP_ACCEPTANCE.md#0190自动面候选与有限面探测任务) · [使用与排错](docs/OPENCODE_START.md) · [模型进度](docs/MODEL_PROGRESS.md) · [下一步](docs/DEVELOPMENT_PLAN.md) · [工具接口](docs/TOOL_CONTRACTS.md) · [来源许可](THIRD_PARTY_NOTICES.md)
