# 证据边界

- 重放目标图→链→连接/距离/面复核→原始配合及几何；修改原始哈希或派生字段会拒绝。文件重放不证明来源真实或采集原子性。
- 精确组件引用来自IsSame。新引用面直接从MateEntity.Reference读取，根装配持久引用回读并以IsSame核对；这些引用只在该原始文件和文档上下文中解释，不能凭ID字节猜测跨次CAD身份。
- reference_type_code是选择类型，2只表示面。平面/圆柱分类由该引用面的GetSurface检查；point和direction来自EntityParams的所属根装配坐标，不重复乘Transform2。
- 根坐标参数、面引用、配合类型/对齐和LockRotation会再次读取以发现变化；未承诺原子快照或完整拓扑版本。只读GetDefinition/LockRotation，不调用AccessSelections、ModifyDefinition、Rebuild或运动接口。
- 根MateGroup没有子装配内部配合。非两实体、根/未知引用及对外连接不投影成一个简单二元约束；多个根mate源分开输出snapshots，缺失不会被另一份的“好结果”覆盖。
- 距离、局部面间隙与几何轴继续保留geometry_context；它们描述几何观测，不代替实际约束。参考模板不参与此工具。
