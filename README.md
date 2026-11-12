# 3DModel-RCGN

用 OpenCode + MCP 操作 SolidWorks，逐步实现工业数模自动拆解。当前 **0.20.0 / 45 个工具**：读取模型、生成机构候选、自动补采具体面，再把有效观测回填草案并比较变化。测试STEP已在examples中。

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
python scripts/verify_face_reintegration.py --output outputs/verify-0.20
```

预期`passed: true`、28项检查。报告和原始调用保存在指定目录；重复运行换新目录。使用显式模拟CAD，不代表升降机实测。也可告诉OpenCode：

> 按docs/MCP_ACCEPTANCE.md的0.20.0步骤，将本轮有效面测量回填草案，保留原阈值与旧证据，比较前后变化，再用更新后的check建立索引并继续有界规划。按功能加载skill、按需读细节；缺依据保留风险，不设置人工复核。

38个功能skill与工具代码隔离。**已接通面候选、测量、草案更新与防重复续轮；仍是证据支持的机构假设，尚未求解运动或生成拆卸路径，也未取得该升降机完整实机结果。**

[详细验收](docs/MCP_ACCEPTANCE.md#0200面证据回填与变化比较) · [使用与排错](docs/OPENCODE_START.md) · [模型进度](docs/MODEL_PROGRESS.md) · [下一步](docs/DEVELOPMENT_PLAN.md) · [工具接口](docs/TOOL_CONTRACTS.md) · [来源许可](THIRD_PARTY_NOTICES.md)
