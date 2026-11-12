# 3DModel-RCGN

用 OpenCode + MCP 操作 SolidWorks，逐步实现工业数模自动拆解。当前 **0.16.0 / 40 个工具**：采集模型证据、匹配参考机构、生成刚体/关节候选，并检查草案冲突、规划只读补采任务。测试STEP已在examples中。

## 更新与使用

在仓库根目录、你已有的 Conda 环境中执行：

```powershell
conda activate 你的环境名
git pull --ff-only
python -m pip install -e ".[solidworks,templates]"
opencode mcp list
opencode
```

Windows + Python 3.10+ + 桌面版SolidWorks；不需要.venv。升级后重启OpenCode。操作模型时可自动启动SolidWorks；已有证据可离线分析。

## 验证这次新增功能

```powershell
python scripts/verify_evidence_planning.py --output outputs/verify-0.16
```

预期`passed: true`、24项检查。报告和原始结果保存到指定目录；重复运行换新目录。使用显式模拟CAD，不代表升降机实测。也可告诉OpenCode：

> 按docs/MCP_ACCEPTANCE.md的0.16.0步骤检查已有升降链关节草案，再生成补采计划。按任务加载skill，详细说明按需读取。不设置人工复核，结论说明冲突、竞争解释与能力缺口。

33个功能skill与工具代码隔离。**本轮会生成准确的采集参数、依赖和前后校验步骤；计划本身不执行CAD调用，也未实现自动回填或运动/拆卸路径验证。尚无该升降机的实机草案结果。**

[详细验收](docs/MCP_ACCEPTANCE.md#0160草案检查与补采规划) · [使用与排错](docs/OPENCODE_START.md) · [模型进度](docs/MODEL_PROGRESS.md) · [下一步](docs/DEVELOPMENT_PLAN.md) · [工具接口](docs/TOOL_CONTRACTS.md) · [来源许可](THIRD_PARTY_NOTICES.md)
