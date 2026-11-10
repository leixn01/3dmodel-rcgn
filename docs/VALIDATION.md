# 验证状态

更新：2026-11-10。当前 MCP 0.3.0；逐项实机标准见 [验收清单](MCP_ACCEPTANCE.md)。

| 范围 | 已有证据 | 尚未证明 |
| --- | --- | --- |
| 模型打开 | 用户反馈在另一台 Windows 电脑可用 | 未附软件版本与原始调用记录，不能代表其他工具通过 |
| 51 项离线/协议测试 | 新增 16 项空间测试，覆盖旋转/缩放/反射、根/父变换、单位、近似边界、缺失与部分结果、重复实例及只读状态；原测试继续通过 | 成功 CAD 操作使用显式测试替身，不代表真实 COM 兼容 |
| MCP stdio | 实际初始化、列出 15 个工具、调用单件与批量空间读取、部分结果与工具错误；保留原显示等流程 | 不是 OpenCode 客户端或窗口视觉验收 |
| 多平台 CI | Ubuntu/Windows、Python 3.10/3.12 四组检查覆盖当前测试与资产校验 | 对应提交状态见 Actions；Windows 测试仍使用替身，无真实 SolidWorks，跳过非 Windows 平台错误测试 |
| 打包与流程 | 0.3.0 wheel 包含空间适配器/计算模块及第三方许可，不含测试后端；9 个 skill 元数据检查 | 目标 SolidWorks 上的 API 绑定、嵌套坐标与包围盒仍须实测 |
| 测试资产 | STEP/JPG 原始字节、大小与 SHA-256 保持不变，CI 直接校验；源 ZIP 成员比对已在此前完成 | 文本体检不证明几何、配合或运动关系 |

[当前 Actions](https://github.com/leixn01/3dmodel-rcgn/actions) · [0.2.0 功能提交 CI](https://github.com/leixn01/3dmodel-rcgn/actions/runs/42811816927)

真实验收结果保存在 `outputs/` 的新目录，区分“通过 / 失败 / 部分通过 / 阻塞 / 未测试”。本轮空间读取没有目标 SolidWorks 实机通过证据；不将离线计算、测试替身或用户单项反馈写成全部实机通过。资产事实和来源见 [样例说明](../examples/three_servo_lift/README.md)。
