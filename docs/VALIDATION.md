# 验证状态

当前 MCP 0.5.0，17 个工具、11 个功能 skill。只维护 Windows。新增修复与分组的实机标准见 [0.5.0 验收](MCP_ACCEPTANCE.md#050修复与组件分组)。

## 用户提供的真实反馈

用户截图：SolidWorks 2025，测试 STEP 导入为装配，CLI 直连旧版 cadkin 的 15 个工具。提交 SHA、完整原始 JSON 与逐项人工窗口证据未提供。

| 结果 | 工具 |
| --- | --- |
| 11 项 API 通过 | session_status、open_document、active_document、component_tree、set_view、select_component、clear_selection、rebuild、zoom_to_fit、get_component_visibility、component_spatial |
| 2 项失败 | get_display_state、set_display_visibility；pythoncom.LoadTypeLibEx 不存在 |
| 2 项部分通过 | set_component_visibility 实际生效但超时；spatial_inventory 小范围/单件一致，全量 254 组件读取超时 |
| 错误路径 | DOCUMENT_CHANGED、INVALID_ARGUMENTS 正确且 MCP 保持可用；NO_ACTIVE_DOCUMENT/NOT_ASSEMBLY 尚未实测 |

截图的 15 工具/60 秒上限早于 0.4.0 的 16 工具/180 秒配置。0.5.0 修正真实接口调用、删除设置后的重复全树遍历/强制重绘、采用空间分页；没有仅凭增加时限判定问题解决。启动及本次真实分组准确性仍待用户电脑验证。

## 自动检查与边界

| 范围 | 证据与边界 |
| --- | --- |
| 90 项测试 | 原有测试保留；新增真实 pywin32 类型库读取、一次遍历/不强制重绘、254 实例分页/汇总、签名变化与错误保留、候选/冲突/范围/人工复核/文件保护等回归。本地执行时跳过 2 项 Windows 专属检查；Windows 执行时跳过 1 项非 Windows 报错检查。 |
| 真实 MCP stdio | 使用官方 SDK 完成握手、17 工具目录、分页、单页分组拒绝、生成/读回分组文件与错误后服务仍可用；CAD API 成功调用使用显式替身，协议真实不代表 SolidWorks 实机通过。 |
| Windows CI | Python 3.10/3.12；真实 pywin32 加载 Windows stdole2.tlb 并提取枚举，检查 cVars/memid/value 和 LoadTypeLib 入口；保留进程查询/注册解析测试。CI 没有安装 SolidWorks，不能验证 swconst.tlb 的实际安装或大装配耗时。 |
| 工作流复核 | 按独立分组流程实际运行 CLI，读回独立演示数据结果并检查哈希、叶实例覆盖、重复实例和待确认项；未把名称候选改为人工确认，未连接 COM。演示输出不提交仓库、不冒充测试升降机结果。 |
| 分层与资产 | 工具/分组代码、COM 适配和 skill 分开；分组离线运行，空间汇总复用分页工具。STEP/JPG 原字节及来源不变，未重新引入 ZIP。 |

[当前 Actions](https://github.com/leixn01/3dmodel-rcgn/actions) 的对应提交检查为准。真实参数、返回、耗时和人工窗口记录保存到 outputs 新目录，逐项标记“通过 / 失败 / 部分通过 / 阻塞 / 未测试”。
