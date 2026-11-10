# 来源与选型核查记录

核查日期：2026-11-09。

## 项目背景

已阅读用户提供的两份交接文档：`粘贴的 Markdown (2).md` 和 `粘贴的 Markdown (1)(2).md`。本项目提炼与机械建模直接相关的需求，不复制其中无关工程的源码变量、历史准确率和私人上下文。

## 样例资产

- [指定模型页面](https://huggingface.co/datasets/CzcBZSH/3d-model/blob/main/%E4%B8%89%E7%8B%AC%E7%AB%8B%E4%BC%BA%E6%9C%8D%E5%8D%87%E9%99%8D%E6%9C%BA.zip)
- 固定源 revision 与 SHA-256 见配置。
- 实际下载并读取 ZIP 和 STEP 文本；JPG 已查看。
- 按项目所有者的明确要求，将指定原 ZIP 逐字节纳入 examples/three_servo_lift/；来源和校验值保持不变，模型独立许可状态仍为未核实。

## sw2robot

- [仓库](https://github.com/jsk-ros-pkg/solidworks_urdf_exporter2)
- [检查的提交](https://github.com/jsk-ros-pkg/solidworks_urdf_exporter2/commit/7996271877071667edf180c8ece36cff7aeb2106)
- README blob SHA：02fbf0fa5a0654da4db6661d76d9417d83f2b92f。
- 已阅读 README：原生提取依赖 Windows＋SolidWorks COM；编辑/构建可跨平台；graph.json 包含原始约束及显式关节；作者给出了从代码构建图的接口。
- 仓库元数据及 README 标示 Apache-2.0。本次没有引入上游代码，集成前仍需核对固定版本 LICENSE 和依赖许可证。
- 本次未安装、未在指定模型运行；未验证其闭环表达、所有默认值或与 FreeCAD 的互通。
- 对本 STEP 样例，先验证 SolidWorks 导入、工作副本与可用配合，再评估 sw2robot 提取或编辑/导出适配；不能宣称未测试的 STEP 入口已经可用。

## SolidWorks 的 STEP 支持

- [STEP 文件帮助](https://help.solidworks.com/2026/english/SolidWorks/Sldworks/c_Step_Files.htm)：官方资料说明 STEP 导入与装配相关选项。
- [3D Interconnect](https://help.solidworks.com/2026/english/SolidWorks/sldworks/c_sw_3d_interconnect.htm)：官方列出 STEP AP203、AP214、AP242 支持。
- [导入 API 接口](https://help.solidworks.com/2024/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IImport3DInterconnectData.html)：官方说明导入装配需要保存为 SolidWorks 装配以创建可编辑副本。
- 上述资料支持选择 SolidWorks 作为 STEP 输入通道，不证明本样例的原设计 Mate 被完整保留。本次没有 Windows＋SolidWorks 导入实测。

## 其余候选

| 项目 | 拟用职责 | 当前核查状态 |
| --- | --- | --- |
| [FreeCAD](https://github.com/FreeCAD/FreeCAD) | 装配导入、几何检查与可编辑载体 | 交接文档中的候选；本次未完成版本/API/几何导入验证 |
| [OCCT](https://github.com/Open-Cascade-SAS/OCCT) | B-Rep 与装配实例读取、几何计算 | 作为输入质量决定的候选；具体绑定、版本和许可证待集成核验 |
| [JoinABLe](https://github.com/AutodeskAILab/JoinABLe) | 学习型局部装配候选研究 | 第一版不依赖；本次未重跑或核对权重许可 |
| PS/OIP 等运行平台 | 经确认模型的运行与信号反馈 | 适配接口预留；本次不承诺现成无损转换 |

文档能力、源码实现、本机执行、用户工程验收分别记录，不能相互替代。

## MCP 第一版（2026-11-10）

核查并复用 [d-veloping/SW_MCP](https://github.com/d-veloping/SW_MCP) 固定提交 `6ea475b14924f4bc85298fc17bd1f873024e8f6b` 的 COM 成员访问与视图编号片段，修改为失败即返回错误。Apache-2.0 LICENSE/NOTICE 已保留；精确复用与修改范围见 [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)。没有引入上游全部工具，也没有把上游实测版本直接认定为本项目实测版本。

同时检查过 AvishakeAdhikary/solidworks-mcp-server 的连接代码与 MIT 声明，其连接策略包含自动新建实例的路径；本项目没有复用该连接实现。最终采用已有会话连接、独立 STA 调度和固定工具目录。

官方 MCP Python SDK 使用维护线 1.29.0，按 [官方 1.x 文档](https://py.sdk.modelcontextprotocol.io/v1/)固定版本，避免无意升级到接口不同的 2.x。OpenCode 项目配置使用官方说明兼容的 V1 格式；工具协议已由真实 MCP 客户端测试，OpenCode 与 SolidWorks 的现场联调仍待完成。
