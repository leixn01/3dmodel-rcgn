# 3DModel-RCGN

用 OpenCode + MCP 操作 SolidWorks，逐步实现工业数模自动拆解。当前 **0.18.0 / 44 个工具**：读取模型证据、生成机构候选、补采并更新草案；已采集的约束和面目录可关联、复用，后续规划会明确继续或停止。测试STEP已在examples中。

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
python scripts/verify_observation_reuse.py --output outputs/verify-0.18
```

预期`passed: true`、26项检查。报告和原始调用保存在指定目录；重复运行换新目录。使用显式模拟CAD，不代表升降机实测。也可告诉OpenCode：

> 按docs/MCP_ACCEPTANCE.md的0.18.0步骤，用当前草案检查和已有补采记录建立证据索引，再携带索引规划下一轮。按功能加载skill，详细说明按需读取；不要重复采集已有观测，不设置人工复核，报告继续或停止的原因与剩余风险。

37个功能skill与工具代码隔离。**已支持补采、兼容回填、证据关联与有界复用；面目录还不能自动选出接触面，约束上下文不等于求解出的运动副。尚未实现整机自动划链、运动求解或拆卸路径，也未取得该升降机完整实机结果。**

[详细验收](docs/MCP_ACCEPTANCE.md#0180证据关联复用与停止) · [使用与排错](docs/OPENCODE_START.md) · [模型进度](docs/MODEL_PROGRESS.md) · [下一步](docs/DEVELOPMENT_PLAN.md) · [工具接口](docs/TOOL_CONTRACTS.md) · [来源许可](THIRD_PARTY_NOTICES.md)
