---
name: cad-intake
description: 检查 STEP 或 ZIP 模型的文件清单、来源、校验值和 STEP 文本统计。在用户要求模型体检、确认输入内容或排查损坏时使用；不负责 SolidWorks 连接、装配实例导出或运动推断。
---

# CAD 输入体检

以下命令均在仓库根目录执行；文档链接相对于本文件。

1. 确认输入路径。指定升降机 STEP 已在 `examples/three_servo_lift/3X Lift Assembly.STEP`，直接使用；不要求下载或解压。原 ZIP 不随仓库保存；来源与校验值保留在样例配置。
2. 调用现有工具：`python -m cadkin inspect "examples/three_servo_lift/3X Lift Assembly.STEP"`。其他输入替换最后一个参数，含空格的路径加引号。
3. 需要保存时附加 `--output outputs/intake.json`；文件已存在时选择新文件名，不覆盖已有结果。工具只读 ZIP，不执行解压。
4. 核对来源时读取 [样例配置](../../../configs/three_servo_lift.source.json)；本地文件按 `bundled_files` 校验；顶层 SHA-256 对应源 ZIP，不能用于校验 STEP。
5. 报告输入、扫描层级、实体统计、单位声明、异常和结果位置。明确这是文本扫描；PRODUCT/NAUO 不是展开后的组件实例数量，不能据此认定 Mate、运动副或行程。

工具实现位于 `cadkin/tools/intake.py`。API 调用失败或输入不合法时报告实际错误，不生成替代结果。需要 SolidWorks 运行时信息时转到对应功能，不在这里追加 COM 代码。
