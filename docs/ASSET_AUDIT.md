# 三独立伺服升降机：输入体检

检查日期：2026-11-09。范围：实际下载、ZIP 清单、STEP 文本检查、参考图查看。未使用 CAD 内核验收几何或运动。

| 项目 | 实测结果 |
| --- | --- |
| Hugging Face 仓库 | CzcBZSH/3d-model |
| revision | 10a7c112226e9caeeab5b12c4d6c3a80cc66b436 |
| ZIP 大小 | 1,095,163 bytes |
| ZIP SHA-256 | 52b487fd8d48807d4352d71d2fe609d004d9a0602ba9b7d898e85ffd5417a64b |
| STEP 文件 | temp/3X Lift Assembly.STEP，7,777,725 bytes |
| 参考图片 | temp/Bosch SSS 08.JPG，95,271 bytes |
| 文件头 | STEP AP214 / AUTOMOTIVE_DESIGN |
| 导出软件声明 | SwSTEP 2.0 / SolidWorks 2012 |
| 文件头时间声明 | 2012-11-16T21:41:52；不是本次检查时间 |
| PRODUCT 简单实体定义 | 46 |
| NEXT_ASSEMBLY_USAGE_OCCURRENCE 记录 | 80 |
| MANIFOLD_SOLID_BREP 定义 | 37 |
| SI 长度单位声明 | 毫米；仍需按每个表示上下文验证与转换 |
| SolidWorks 输入 | STEP 可在 SolidWorks 中打开/导入；本包没有单独的 SLDASM/SLDPRT |
| 导入后的配合 | 尚未在 SolidWorks 实测，待枚举并区分源约束与新建配合 |
| PLC/EPLAN/IO 表 | ZIP 内没有 |

**定义数、装配引用记录数、展开实例数、实体数、刚体数不是同一口径。** 重复子装配展开后可产生更多实例，尚未进行几何内核级核对。

存在以下名称线索：`Rail_HGR20R06601_30_0`、`Block_HGH20CAZ0C`、`SGMAH-04A_F4C`、`ZERO MAX-SC030R`、`Monocarrier-MCM06050H10K00-NSK`、`Slider-MCM06050H10K00-NSK`、`Screw-MCM06050H10K00-NSK`。名称可用于检索与候选分类，不直接证明型号、参数或运动关系。

当前文本扫描未检出名字含 KINEMATIC/PAIR/ACTUATION 的简单实体。该扫描不能证明所有语义均不存在，也不能代替 SolidWorks 导入后的配合检查。STEP 可被 SolidWorks 打开，文件格式与原设计 Mate 是否保留应分别验证。

参考图可见三组类似竖直升降结构；具体固定基体、移动件归属、额外自由度、方向、零位、限位和传动比仍待分析。图片仅作人工辅助，几何事实以 STEP 及后续测量为准。

机器可读完整统计见 `reports/three_servo_lift.intake.json`；数据源与固定下载地址见 `configs/three_servo_lift.source.json`。指定原 ZIP 已作为 `examples/three_servo_lift/three_servo_lift.zip` 纳入 Git；STEP 与 JPG 也已按原始字节提取到同目录，可直接使用；文件名保持原名。
