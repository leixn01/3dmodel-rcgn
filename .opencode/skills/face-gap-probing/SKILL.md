---
name: face-gap-probing
description: 对两个不同实例上的指定平面或圆柱面，从明确根坐标种子查询有限面上的测点间隙和法向。用于“具体面靠近在哪里”“补面级几何证据”；只读局部探测，不宣称全局最小距离、接触或干涉。
---

# 局部面间隙探测

输入：两个原始面目录中的记录、当前 token、1–8 个有依据的根装配毫米坐标种子。输出：sw_probe_face_pair 原始 envelope。

1. 从源文件选择 body_index/face_index，使用 left/right 的 face_inventory_path 绑定；不凭旧索引或名字猜面身份。
2. 用已有测点、模型位置或用户指定位置作为 seed_points_root_mm，记录来源；不能把零件局部坐标当根坐标。缺少合理种子时只补所需空间/距离信息。
3. 调用 sw_probe_face_pair，一次一对面；保留完整返回和每个种子的错误/迭代状态，失败不补零。
4. 报告 sampled 间隙与局部法向，保持 global_minimum_proven=false。大间隙不能排除面上其他位置接近；零/小间隙不确认接触。复核另交原始文件。

解释坐标、种子、参数或失败时读 [探测细节](references/details.md)；只在缺输入时调用对应能力，不强制先跑组件距离或配合。
