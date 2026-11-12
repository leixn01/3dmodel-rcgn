# 3DModel-RCGN

用 OpenCode + MCP 操作 SolidWorks，逐步实现工业数模自动拆解。当前 **0.13.0 / 34 个工具**：已有组件与几何证据采集、分组/机构链汇总；新增8个真实资产的结构参考、USD关节提取和图结构评分。测试STEP已在examples中。

## 更新与使用

在仓库根目录、你已有的 Conda 环境中执行：

```powershell
conda activate 你的环境名
git pull --ff-only
python -m pip install -e ".[solidworks,templates]"
opencode mcp list
opencode
```

Windows + Python 3.10+ + 桌面版SolidWorks；不需要.venv。升级后重启OpenCode。操作模型时可自动启动SolidWorks；模板工具可独立离线运行。

## 验证这次新增功能

```powershell
python scripts/verify_reference_templates.py --output outputs/verify-0.13
```

应返回 `passed: true`、17项检查；报告及原始结果保存在指定目录。再次运行换新目录名。也可告诉OpenCode：

> 按docs/MCP_ACCEPTANCE.md的0.13.0步骤验收参考模板功能。按任务加载对应skill，详细说明按需读取。不设置人工复核节点，不确定处在结论说明风险。

27个功能skill与工具代码隔离。**本轮完成参考模板基础设施；尚未将模板自动匹配到升降机，也未实现刚体合并、零件移动或拆卸路径验证。**

[详细验收](docs/MCP_ACCEPTANCE.md#0130参考模板与图结构评分) · [使用与排错](docs/OPENCODE_START.md) · [模型进度](docs/MODEL_PROGRESS.md) · [下一步](docs/DEVELOPMENT_PLAN.md) · [工具接口](docs/TOOL_CONTRACTS.md) · [来源许可](THIRD_PARTY_NOTICES.md)
