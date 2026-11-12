# 3DModel-RCGN

用 OpenCode + MCP 操作 SolidWorks，逐步实现工业数模自动拆解。当前 **0.15.0 / 38 个工具**：采集组件/几何证据、匹配参考机构，生成多零件刚体候选和关节参数草案。测试STEP已在examples中。

## 更新与使用

在仓库根目录、你已有的 Conda 环境中执行：

```powershell
conda activate 你的环境名
git pull --ff-only
python -m pip install -e ".[solidworks,templates]"
opencode mcp list
opencode
```

Windows + Python 3.10+ + 桌面版SolidWorks；不需要.venv。升级后重启OpenCode。操作模型时可自动启动SolidWorks；候选分析可使用已有来源离线运行。

## 验证这次新增功能

```powershell
python scripts/verify_rigid_drafts.py --output outputs/verify-0.15
```

预期`passed: true`、24项检查；报告及原始结果保存到指定目录。重复运行换新目录。脚本使用显式模拟CAD，不代表升降机识别准确率。也可告诉OpenCode：

> 按docs/MCP_ACCEPTANCE.md的0.15.0步骤，对当前升降链生成刚体候选和关节草案。按任务加载skill，详细说明按需读取。不设置人工复核节点，在结论保留竞争解释和风险。

31个功能skill与工具代码隔离。**现在可提出“哪些零件可能共同运动、组间可能是什么关节”；尚无该升降机的实机分组/关节结果，未完成刚体或运动确认、拆卸路径验证。**

[详细验收](docs/MCP_ACCEPTANCE.md#0150刚体候选与关节参数草案) · [使用与排错](docs/OPENCODE_START.md) · [模型进度](docs/MODEL_PROGRESS.md) · [下一步](docs/DEVELOPMENT_PLAN.md) · [工具接口](docs/TOOL_CONTRACTS.md) · [来源许可](THIRD_PARTY_NOTICES.md)
