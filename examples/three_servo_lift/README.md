# 三独立伺服升降机测试样例

直接在 SolidWorks 中打开 [3X Lift Assembly.STEP](<3X Lift Assembly.STEP>)，无需解压。参考图为 [Bosch SSS 08.JPG](<Bosch SSS 08.JPG>)。普通 Git 克隆即可取得完整文件，无需 Git LFS。

| 文件 | 大小 | 用途 |
| --- | --- | --- |
| `3X Lift Assembly.STEP` | 7,777,725 bytes | 开发与实机验收输入 |
| `Bosch SSS 08.JPG` | 95,271 bytes | 原包参考图 |
| `three_servo_lift.zip` | 1,095,163 bytes | 保留原始来源，日常使用不需要解压 |

STEP 与 JPG 从原包提取，保持原文件名、编码及全部字节。源文件来自 [CzcBZSH/3d-model](https://huggingface.co/datasets/CzcBZSH/3d-model)，固定 revision 为 `10a7c112226e9caeeab5b12c4d6c3a80cc66b436`；完整 SHA-256、大小与包内路径见 [来源配置](../../configs/three_servo_lift.source.json)。CI 会验证仓库文件与原包成员逐字节一致。

原始输入保持不变，需要编辑的工作副本和验收结果放在 `outputs/`。STEP 的实际导入类型与装配层级以 SolidWorks 实机结果为准，验收方法见 [MCP 验收清单](../../docs/MCP_ACCEPTANCE.md)。

按项目所有者要求纳入该测试样例。资产权利仍归原权利人，项目代码许可不覆盖该模型；来源页面未确认独立许可，状态保留在来源配置中。
