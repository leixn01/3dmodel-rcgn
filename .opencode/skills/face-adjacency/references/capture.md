# 读取与边界

sw_read_face_adjacency必填expected_document_token、boundary_path，可选max_edges=64（1–256）。原始boundary必须完整；计划固定64，不因失败自动扩容。持久面/配置/实例位姿及已存边界在前后核对。

IEdge.GetTwoAdjacentFaces2返回两槽；null保留，缝边的两个相同面仍是缝边。ISldWorks.IsSame核对所选面与同一body，每个非空邻面持久ID做round-trip，读取descriptor，再完整回读邻接。如果上下文或拓扑改变，整批按现有规则失效，不采用先前成功读取。

邻接是同体拓扑事实。平面法向/位置只描述无限平面，未读取该端面的有限轮廓、跨组件接触或干涉。不是轴向保持或行程证据。目录不含该邻面也可有持久引用，但不可伪造catalog索引供其他工具使用。
