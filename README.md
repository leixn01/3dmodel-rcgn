# 3DModel-RCGN

用 OpenCode + MCP 操作 SolidWorks，逐步实现工业数模自动拆解。当前 **0.14.0 / 36 个工具**：可采集组件/几何证据、汇总机构链，并将目标实例图与8个参考资产中的局部结构匹配，输出候选映射和风险。测试STEP已在examples中。

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
python scripts/verify_template_matching.py --output outputs/verify-0.14
```

应返回 `passed: true`、18项检查；报告及原始结果保存在指定目录。再次运行换新目录名。脚本使用明确的模拟CAD和参考派生观测，不代表升降机识别准确率。也可告诉OpenCode：

> 按docs/MCP_ACCEPTANCE.md的0.14.0步骤验收目标实例图和模板匹配功能。按任务加载对应skill，详细说明按需读取。不设置人工复核节点，不确定处在结论说明风险。

29个功能skill与工具代码隔离。**本轮可对真实来源文件生成局部机构候选；尚未取得该升降机的实机匹配结果，未实现多零件刚体合并、运动或拆卸路径验证。**

[详细验收](docs/MCP_ACCEPTANCE.md#0140目标实例图与模板局部匹配) · [使用与排错](docs/OPENCODE_START.md) · [模型进度](docs/MODEL_PROGRESS.md) · [下一步](docs/DEVELOPMENT_PLAN.md) · [工具接口](docs/TOOL_CONTRACTS.md) · [来源许可](THIRD_PARTY_NOTICES.md)
