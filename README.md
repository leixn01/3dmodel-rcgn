# 3DModel-RCGN

工业数模自动拆解项目。MCP 0.11.0 提供 29 个工具：SolidWorks 启动、文档/组件树、选择/显隐、空间读取、组件分组、配合/圆柱证据、面身份核对，以及组件距离、具体面目录、局部面间隙/法向与接触候选。STEP 测试模型已在 examples 中。

## 在 Windows 上使用

在仓库根目录的 PowerShell 中激活你已有的 Conda 环境（替换环境名；已有仓库先更新）：

```powershell
conda activate 你的环境名
git pull --ff-only
python -m pip install -e ".[solidworks]"
opencode mcp list
opencode
```

仅面向 Windows + 桌面版 SolidWorks，Python 3.10+。无需提前启动 SolidWorks，无需解压模型。项目使用当前 Conda 环境的 python；升级后退出并重新启动 OpenCode。

本次可直接告诉 Agent：

> 启动或复用 SolidWorks，打开仓库测试 STEP，按 docs/MCP_ACCEPTANCE.md 的 0.11.0 清单验收。先选两个真实零件，读取少量面，探测一对平面或圆柱面上的测点间隙和法向，再离线复核。只加载当前任务对应 skill，按需读取参考文件；保存原始返回，列出需要我在窗口核对的结果，不自动确认接触或运动副。

## 导出与分组

模型打开后执行（输出需用新文件名）：

```powershell
python -m cadkin spatial-export --page-size 5 --output outputs/spatial.json
python -m cadkin group outputs/spatial.json --output outputs/groups.json
```

第一条收齐空间分页；第二条离线生成角色候选供复核。若只做名称分组、包围盒很慢，可用新文件名加 `--without-boxes`；邻近筛选需要包围盒。

[0.11.0 验收步骤](docs/MCP_ACCEPTANCE.md#0110具体面间隙与法向)包含新工具参数、测点核对、部分结果和只读检查。局部测点间隙不是全局最小距离；装配级切除不在本次面探测范围内。

23 个功能 skill 保持简短入口、references 按需读取；执行代码独立放在工具/COM 层。当前不含零件移动、配合编辑或自动运动关系确认。

[模型拆解进度与已用工具](docs/MODEL_PROGRESS.md) · [下一步](docs/DEVELOPMENT_PLAN.md) · [实机验收](docs/MCP_ACCEPTANCE.md) · [使用与排错](docs/OPENCODE_START.md) · [工具接口](docs/TOOL_CONTRACTS.md) · [分层](docs/ARCHITECTURE.md) · [开源来源](THIRD_PARTY_NOTICES.md)
