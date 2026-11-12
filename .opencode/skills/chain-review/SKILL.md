---
name: chain-review
description: 将用户明确给出的连接确认、否定、待查或冲突意见，绑定到现有机构链清单并离线生成新复核记录。用于“记录我的连接判断”“应用已填写复核文件”；不代替用户作机械确认、不编辑 CAD。
---

# 机构链人工复核

输入：原始chain dossier和明确人工意见/已填写复核JSON。输出：绑定清单哈希的新复核结果。

1. 核对用户实际给出的逐对结论；没有明确结论时保留pending，不能凭模型名称、几何候选或演示测试代填confirmed/rejected。
2. 将意见写为来源绑定的review JSON，保留实际reviewer、带时区时间、理由和本对evidence_id；只记录已有决定，不额外请求已获授权的确认。
3. 调用 cad_apply_chain_review，输出使用新文件；清单或源文件变动时重新核对，不能更改哈希或按索引迁移旧决定。
4. 分别报告human_review_complete与来源complete；人工confirmed不代表cad_verified，也不清除partial、未知区域或自动创建刚体/运动副。

编写复核文件或解释状态时读 [复核格式](references/details.md)。已有有效review文件时直接应用，不启动CAD、不强制重新加载采集skill。
