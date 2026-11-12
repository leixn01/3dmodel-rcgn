# 验证状态

当前 MCP 0.11.0，29 个工具、23 个功能 skill。面间隙与法向见 [0.11.0 验收](MCP_ACCEPTANCE.md#0110具体面间隙与法向)，具体模型状态见 [拆解进度](MODEL_PROGRESS.md)。组件距离与近接触候选见 [0.10.0 验收](MCP_ACCEPTANCE.md#0100组件距离与近接触候选)。面身份核对见 [0.9.0 验收](MCP_ACCEPTANCE.md#090配合引用面核对)。配合状态与连接复核见 [0.8.0 验收](MCP_ACCEPTANCE.md#080配合状态与连接复核)。关系候选见 [0.7.0 验收](MCP_ACCEPTANCE.md#070组件关系候选)。只维护 Windows。Conda 与约束/轴线读取见 [0.6.0 验收](MCP_ACCEPTANCE.md#060conda与约束轴线证据)，原修复/分组仍保留 0.5.0 复测。

## 用户提供的真实反馈

用户截图：SolidWorks 2025，测试 STEP 导入为装配，CLI 直连旧版 cadkin 的 15 个工具。提交 SHA、完整原始 JSON 与逐项人工窗口证据未提供。

| 结果 | 工具 |
| --- | --- |
| 11 项 API 通过 | session_status、open_document、active_document、component_tree、set_view、select_component、clear_selection、rebuild、zoom_to_fit、get_component_visibility、component_spatial |
| 2 项失败 | get_display_state、set_display_visibility；pythoncom.LoadTypeLibEx 不存在 |
| 2 项部分通过 | set_component_visibility 实际生效但超时；spatial_inventory 小范围/单件一致，全量 254 组件读取超时 |
| 错误路径 | DOCUMENT_CHANGED、INVALID_ARGUMENTS 正确且 MCP 保持可用；NO_ACTIVE_DOCUMENT/NOT_ASSEMBLY 尚未实测 |

截图的 15 工具/60 秒上限早于 0.4.0 的 16 工具/180 秒配置。0.5.0 修正真实接口调用、删除设置后的重复全树遍历/强制重绘、采用空间分页；没有仅凭增加时限判定问题解决。启动、修复、真实分组准确性、0.6.0 证据工具、0.7.0 关系候选、0.8.0 配合状态/连接复核、0.9.0 面身份核对、0.10.0 组件距离及 0.11.0 面探测均需用户电脑验收。

## 自动检查与边界

| 范围 | 证据与边界 |
| --- | --- |
| 219 项测试 | 0.11.0 新增有限平面/圆柱投影、持久面目录、方向/反射/缩放/嵌套变换、法向翻转、种子失败/预算、几何变化拒绝、源哈希/数值重算、离线 CLI 与真实协议； 0.10.0 新增距离单位/最近点一致性、重复/嵌套实例、无解/错误、配置/位姿/编辑模式保护、包围盒筛选与未知范围、预算、来源重算、距离分类、离线 CLI 和真实协议； 0.9.0 新增持久 ID 回读/失效、同几何异面、重复实例、配合引用面对应、预算、几何/引用变化拒绝、源哈希和无 COM 离线复核； 0.8.0 新增根配合状态、COM 身份映射、层级范围/预算/循环、状态与位姿变化拒绝、实例对关联/源哈希及真实协议； 0.7.0 新增同轴/平行、无向轴/轴点等价、明确公差、实例/配置/变换一致性、部分来源、预算、角色来源、离线 CLI/MCP 文件读写检查；原有测试保留；0.6.0 新增约束空值/失败/嵌套上下文、配合截断、圆柱坐标/缩放/重复实例/配置限制、PATH 解释器等回归；包含真实 pywin32 持久引用字节数组/ByRef 状态类型、类型库读取、一次遍历/不强制重绘、254 实例分页/汇总、签名变化与错误保留、候选/冲突/范围/人工复核/文件保护等回归。本地执行时跳过 4 项 Windows 专属检查；Windows 执行时跳过 1 项非 Windows 报错检查。 |
| 真实 MCP stdio | 使用官方 SDK 完成握手、29 工具目录、分页、单页分组拒绝、生成/读回分组文件与错误后服务仍可用；关系和连接复核工具使用生产服务器真实 stdio，读取演示 JSON，不连接 CAD；CAD API 成功调用使用显式替身，协议真实不代表 SolidWorks 实机通过。 |
| Windows CI | Windows 上的 Miniforge/Conda Python 3.10/3.12；安装与测试通过 conda run 运行并核对真实 CONDA_PREFIX/sys.prefix；真实 pywin32 检查距离返回的 ByRef VARIANT 数组类型（不调用 CAD），加载 Windows stdole2.tlb 并提取枚举，检查 cVars/memid/value 和 LoadTypeLib 入口；保留进程查询/注册解析测试。CI 没有安装 SolidWorks，不能验证 swconst.tlb 的实际安装或大装配耗时。 |
| 工作流复核 | 按独立分组流程实际运行 CLI，读回独立演示数据结果并检查哈希、叶实例覆盖、重复实例和待确认项；未把名称候选改为人工确认，未连接 COM。0.7.0 独立流程用 3 个演示实例实际运行 CLI，核对 1 条同轴/2 条平行候选及来源哈希；包含 FACE_LIMIT 的来源保持 partial/complete=false，即使 3/3 已读面配对全部完成。0.8.0 按独立连接复核流程实际离线运行，识别演示数据中的未知状态、特征警告与仅几何证据三类实例对，保留 partial，核对哈希及候选索引；未加载其他采集 skill 或启动 CAD。演示输出不提交仓库、不冒充测试升降机结果。 |
| 0.9.0 工作流复核 | 独立流程经官方 SDK 连接测试专用 stdio 服务器，按两个独立 skill 完成在线面核对与离线复核：6 个请求面中解析 5 个、比较 10 次、2 条配合具有准确面对应；缺失持久引用保持 partial，已知未抑制状态与特征警告分别保留。仅为演示替身，不是 SolidWorks 实测。 |
| 0.10.0 协议与数值边界 | 真实 SDK/stdio 完成空间采集、待测清单、两个组件对测量、离线复核、预算和错误恢复；CAD 后端为显式有限盒体替身。测试中的 0.05 mm/20 mm 为演示几何，不是升降机实测。ClosestDistance 的真实兼容、最近点坐标和耗时仍待实机验收。 |
| 0.10.0 独立工作流 | 按三个独立 skill 经真实 SDK/测试 stdio 完成筛选、最多两对距离、离线复核；演示 4 叶实例中 3 个有盒，6 个潜在对中检查 3 个可筛对、返回并测量 2 对，得到 1 个近接触候选/1 个已测间隔。缺盒实例与未筛入对仍未知，整体 partial；16 项来源/点距/调用数/文档状态核对通过。只读演示，无真实 SolidWorks 证据。 |
| 0.11.0 独立工作流 | 按三个新 skill 经官方 SDK/测试 stdio 执行5次工具调用；两个实例各限2面，两个根坐标种子的演示局部间隙均0.05 mm，法向相反且朝向点差，离线得到1个候选。FACE_LIMIT/SOURCE_INCOMPLETE 在全链保持 partial；原始 envelope、源哈希、预算、坐标/法向/间隙和否认确认标志复核通过。仅为隔离演示，不是 SolidWorks 实测。 |
| 分层与资产 | 工具/分组/关系代码、COM 适配和 skill 分开；分组离线运行，空间汇总复用分页工具；约束与圆柱读取各有独立适配器，共享目标校验与纯数学转换。STEP/JPG 原字节及来源不变，未重新引入 ZIP。 |

[当前 Actions](https://github.com/leixn01/3dmodel-rcgn/actions) 的对应提交检查为准。真实参数、返回、耗时和人工窗口记录保存到 outputs 新目录，逐项标记“通过 / 失败 / 部分通过 / 阻塞 / 未测试”。
