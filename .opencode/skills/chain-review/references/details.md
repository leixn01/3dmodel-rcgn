# 复核输入

cad_apply_chain_review 必填chain_path、review_path、output_path。chain_path须为cad_build_chain_evidence的原始结果，不能把已复核输出再当基础清单。工具会重放来源和清单，再应用意见。

review JSON格式：

```json
{
  "chain_review_input_schema_version": 1,
  "chain_sha256": "基础清单文件实际SHA256",
  "reviewer": "实际复核人",
  "reviewed_at": "2026-11-12T10:00:00+08:00",
  "decisions": [
    {
      "pair_id": "从该清单复制的pair_id",
      "decision": "pending",
      "relation_type": null,
      "reason": "用户实际提供的待查理由",
      "evidence_ids": [],
      "acknowledged_flags": []
    }
  ]
}
```

示例时间/人名/理由是格式占位，不能当作用户真实复核记录。用Get-FileHash -Algorithm SHA256读取哈希；每个pair_id最多一条。evidence_ids只能引用该对清单里的证据，可为空但必须有人工观察/判断理由。姓名与时间用于归属记录，工具不认证人员身份。

| decision | relation_type | 含义 |
| --- | --- | --- |
| confirmed | rigid_connection/revolute_joint/prismatic_joint/other_connection之一 | 人工声明认可此种关系，尚未验证轴线、限位或求解状态 |
| rejected | null | 人工不接受本条连接候选，不等于CAD证明两者无连接 |
| pending | null | 仍需检查 |
| conflict | null | 人工指出当前资料或解释存在冲突 |

confirmed/rejected需要在acknowledged_flags显式列出该对所有review_flags的code，并在reason解释判断依据；只复述code不能替用户决定。其他状态可以保留尚未处理的flags。用户没有对某一对给意见时直接省略，该对仍pending。

# 输出和边界

输出chain_review_schema_version=1，原始证据和边界联系保留；每对human_review包含reviewer/time/reason/basis=human_declaration，human_confirmed按声明设置，cad_verified=false、motion_parameters_verified=false。全局mechanical_relation_confirmed仍为false；不会移动、合并零件或创建配合。

human_review_complete只表示全部pairs没有pending/conflict；来源complete/partial仍独立。来源不完整时requires_review仍为true，人工意见不会消除缺失测量或证明几何。新清单/新源文件必须重新复核，不自动迁移旧确认。

INVALID_CHAIN_REVIEW：哈希/人员/时间/决定/引用有误；UNACKNOWLEDGED_CHAIN_FLAGS：最终决定未处理全部提示；EVIDENCE_MISMATCH：清单或原始证据被改动。均不写成功结果；错误后修复实际来源，不手改SHA256绕过。

```powershell
python -m cadkin review-chain outputs/chain.json outputs/chain-decisions.json --output outputs/chain-reviewed.json
```
