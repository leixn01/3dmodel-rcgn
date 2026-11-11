# 预算与失败分支

sw_mate_inventory 必填 expected_document_token；可选 max_features=2000（1–20000）、max_mates=200（1–1000）、max_entities=16（1–64）、max_depth=32（1–64）。先用默认预算；大模型可先小范围预算观察，但必须标记部分结果。

- FEATURE_LIMIT、FEATURE_DEPTH_LIMIT、MATE_LIMIT、MATE_ENTITY_LIMIT：保留已读记录，partial/truncated；按需求增加允许预算后另写文件，不能称已读完。
- FEATURE_REVISIT、特征遍历错误、MATE_INTERFACE_UNAVAILABLE：保留 partial，不能将未读内容解释为空。根遍历入口失败为 error。
- MATE_REFERENCE_UNRESOLVED：同名不能替代 COM 身份确认，保持未知；不通过手工填写路径绕过。
- COMPONENT_LOOKUP_INCOMPLETE：先核对树读取问题；本流程不自动解析或改配置。
- MATE_STATE_CHANGED、COMPONENT_CHANGED、DOCUMENT_CHANGED：丢弃混合结果，在模型稳定后重新采集。不修改证据 JSON 或盲目拼接旧结果。
- TIMEOUT：操作可能仍在 SolidWorks 内执行，先检查现场，再重启 MCP，不能盲目重复。

保存可使用已有 CLI：python -m cadkin sw sw_mate_inventory --arguments '<实际 JSON 参数>' --output outputs/<未使用名称>.json。PowerShell 引号由实际终端处理，不能传占位 token；优先 MCP 组织参数后保存原始 envelope。
