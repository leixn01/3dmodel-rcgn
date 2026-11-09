# 三独立伺服升降机测试样例

本目录直接保存 [three_servo_lift.zip](three_servo_lift.zip)，为指定来源原 ZIP 的逐字节副本，只改了仓库中的文件名。克隆后可本地解压，普通 Git 即可，无需 Git LFS。

| 项目 | 值 |
| --- | --- |
| 来源 | [CzcBZSH/3d-model](https://huggingface.co/datasets/CzcBZSH/3d-model) |
| 原文件名 | 三独立伺服升降机.zip |
| 固定 revision | 10a7c112226e9caeeab5b12c4d6c3a80cc66b436 |
| ZIP 大小 | 1,095,163 bytes |
| ZIP SHA-256 | 52b487fd8d48807d4352d71d2fe609d004d9a0602ba9b7d898e85ffd5417a64b |
| 包内数模 | temp/3X Lift Assembly.STEP，7,777,725 bytes |
| 包内参考图 | temp/Bosch SSS 08.JPG，95,271 bytes |

在仓库根目录的 Windows PowerShell 中：

```powershell
Expand-Archive -LiteralPath .\examples\three_servo_lift\three_servo_lift.zip -DestinationPath .\outputs\three_servo_lift
```

随后在 SolidWorks 中打开 `outputs/three_servo_lift/temp/3X Lift Assembly.STEP`。目录已解压时使用已有文件，不重复覆盖工作副本。

可用下面的命令校验原 ZIP：

```powershell
Get-FileHash .\examples\three_servo_lift\three_servo_lift.zip -Algorithm SHA256
```

按项目所有者要求纳入该测试样例。资产的权利仍归原权利人，项目代码许可不覆盖该模型；来源页面未确认独立许可，状态保留在 `configs/three_servo_lift.source.json`。
