# 三独立伺服升降机测试样例

直接在 SolidWorks 中打开 [3X Lift Assembly.STEP](<3X Lift Assembly.STEP>)，无需解压。参考图为 [Bosch SSS 08.JPG](<Bosch SSS 08.JPG>)。普通 Git 即可取得完整文件，无需 Git LFS。

| 文件 | 大小 | 用途 |
| --- | --- | --- |
| `3X Lift Assembly.STEP` | 7,777,725 bytes | 开发与实机验收输入 |
| `Bosch SSS 08.JPG` | 95,271 bytes | 原包参考图 |

文件保持原名、编码及全部字节；原始 ZIP 已从当前版本移除。固定来源 revision、原包下载地址及 SHA-256 保留在 [来源配置](../../configs/three_servo_lift.source.json)，`bundled_files` 记录本地 STEP/JPG 的大小、SHA-256 和源包内路径。CI 直接校验本地文件，不下载原包。

## 输入事实

- STEP 文件头声明 AP214 / AUTOMOTIVE_DESIGN，由 SwSTEP 2.0 / SolidWorks 2012 导出；头部时间为 2012-11-16T21:41:52。
- 文本统计：46 个 PRODUCT、80 条 NEXT_ASSEMBLY_USAGE_OCCURRENCE、37 个 MANIFOLD_SOLID_BREP 定义。它们不是展开后的实例数或刚体数。
- 文件声明毫米长度单位，几何读取仍需验证各表示上下文及换算。用户已确认可以打开；导入类型、配合与运动关系尚待核验。
- 原包只包含 STEP 和 JPG，没有原生 SLDASM/SLDPRT、PLC/EPLAN/IO 工程。
- 名称提供导轨、滑块、电机、联轴器和丝杆线索，如 `Rail_HGR20R06601_30_0`、`Block_HGH20CAZ0C`、`SGMAH-04A_F4C`、`ZERO MAX-SC030R`、`Monocarrier-MCM06050H10K00-NSK`、`Slider-MCM06050H10K00-NSK`、`Screw-MCM06050H10K00-NSK`；不能仅凭名称确定型号参数或运动关系。
- 文本扫描未检出名称含 KINEMATIC/PAIR/ACTUATION 的简单实体，不代表导入后必然没有约束。参考图中的三组升降结构仅作人工辅助，固定件、移动件及行程仍需证据。

需要完整文本体检报告时，在仓库根目录重新生成到新文件（已存在则改名）：

```powershell
python -m cadkin inspect "examples/three_servo_lift/3X Lift Assembly.STEP" --output outputs/intake.json
```

工作副本和结果均放在 `outputs/`，原始 STEP 保持不变；实机步骤见 [验收清单](../../docs/MCP_ACCEPTANCE.md)。资产权利仍归原权利人，项目代码许可不覆盖模型；独立许可状态见来源配置。
