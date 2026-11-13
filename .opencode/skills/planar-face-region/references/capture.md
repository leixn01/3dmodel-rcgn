# 参数与支持范围

sw_read_planar_face必填expected_document_token、adjacency_path、face_reference（原始encoding/scope/id对象）；可选max_loops=8（1–8）、max_edges=64（3–128，总边数）。文件必须是完整sw_read_face_adjacency envelope，所选面必须为该圆柱的同体真实平面邻面；不能用同名零件或别的来源引用替代。

前后核对持久面/descriptor/位姿/同体、圆柱原边界及全部已存邻接。GetLoops/GetLoopCount与每环GetEdges/GetEdgeCount核对；不假设线边的返回顺序或方向。完整圆用GetCurveParams3参数跨度和首尾点验证，不仅看CircleParams。区域面积与GetArea比较；闭合/平面公差1e-8m、面积相对容差1e-6与绝对1e-12m²，均不是接触容差。

支持一个外圆及至多一个同心圆孔，或单一无孔凸直边环。分段圆弧、复杂曲线、非凸轮廓、多孔、偏心孔、断环、面积不符或预算截断保留partial/未知。不用AABB、显示网格或采样填补准确边界；混合圆/多边形后续比较仍未知。

一次调用只读一个邻面，原始loop数据与派生region同时保存。来源变化按现有fatal策略停止，失败/partial仍索引，不改变旧来源或复位轮数。
