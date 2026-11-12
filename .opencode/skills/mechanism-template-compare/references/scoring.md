# 输入与评分

cad_compare_mechanism_graphs 必填reference_path、candidate_path、correspondence_path、output_path。输入均为项目内JSON，输出为outputs下新文件。两图为mechanism_template_schema_version=1的raw graph。图节点id必须唯一，enabled为boolean，边必须有两个端点；未知关节kind=unsupported，未知端点frame_kind=unresolved。

对应格式：

```json
{
  "body_correspondence_schema_version": 1,
  "reference_sha256": "参考图文件实际SHA256",
  "candidate_sha256": "候选图文件实际SHA256",
  "body_map": [
    {"candidate_body": "候选图实际body id", "reference_body": "参考图实际body id"}
  ]
}
```

一对一，可不完整；本工具不生成映射。不把来自不同机器的同名节点视为相同零件。接入目标匹配器后由匹配器提供对应；当前接受已有上游对应/固定构造的评分测试。EVIDENCE_MISMATCH须核对变更后重新生成真实对应来源，不能只改哈希骗过校验。

connections比较无向端点对集合；typed_joints比较“端点对+类型”多重集合，平行的多关节不会被合并。precision=匹配数/候选数，recall=匹配数/参考数；未映射候选边计入额外边，未匹配参考边仍是漏边。disabled/unsupported/unresolved边显式排除，完整报告须同时呈现excluded与source_risks，不能只报分数。

静态Xform端点和world在拓扑评分中均视为ground，不评估其不同坐标。刚体覆盖来自输入映射，不证明合并正确；当前不评轴线位置/方向、行程限位、传动比或碰撞。图内容完全相同会提示SELF_COMPARISON；即使hash不同，复制再格式化的图也不能当识别准确率。
