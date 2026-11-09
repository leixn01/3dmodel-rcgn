# 3DModel-RCGN｜自动数模运动关系构建

面向工业设备，把已有 CAD 装配转为可编辑、可追溯、可验证的刚体与运动约束模型，为 PLC 语义安全审查和机电联合验证提供机械侧基础。

**当前状态：项目初始化与输入体检。尚未实现或验收整机自动运动识别。**

## 首个样例

使用指定的 [三独立伺服升降机.zip](https://huggingface.co/datasets/CzcBZSH/3d-model/blob/main/%E4%B8%89%E7%8B%AC%E7%AB%8B%E4%BC%BA%E6%9C%8D%E5%8D%87%E9%99%8D%E6%9C%BA.zip)。2026-11-09 实际下载确认，包内是 STEP AP214 装配和 JPG，没有单独的 SLDASM/SLDPRT 文件。**STEP 是 SolidWorks 支持打开和导入的数模格式，可继续作为本项目的开发输入。**

首个样例优先验证 **SolidWorks 导入 STEP → 读取装配实例、位姿、几何与可用配合 → 机构模板和几何分析补全 → 编辑与运动校核**。FreeCAD/OCCT 保留为开源读取与交叉校验通道。

“SolidWorks 可以打开 STEP”和“导入后保留原设计的 Mate 配合”是两个不同的检查项。当前完成了文件文本体检，尚未在 SolidWorks 中导入验证，不能预先断言所有配合存在或不存在。有可靠配合就读取利用，缺失部分再推断并记录证据。

## 已准备

- 明确的项目范围、分阶段方案和逐项验收标准。
- 固定 Hugging Face revision、文件 SHA-256 与包内清单。
- 可运行的模型下载校验与 STEP 文本体检命令。
- 真实输入的文本体检结果；原始模型不提交 Git。
- 统一机电数据契约草案、开发任务清单、测试与 CI 配置。

## 快速开始

Python 3.10+；当前工具只使用标准库，不依赖 CAD 软件。

```bash
python -m pip install -e .
cadkin fetch --source configs/three_servo_lift.source.json --output data/raw/three_servo_lift.zip
cadkin inspect data/raw/three_servo_lift.zip --output outputs/intake.json
python -m unittest discover -s tests -v
```

也可免安装运行：

```bash
python -m cadkin inspect /path/to/model.step --output outputs/intake.json
```

`inspect` 是 STEP Part 21 文本体检，不是 B-Rep 求解器。实体定义数、装配引用记录数与展开后的实例数必须区分；本工具不会输出未经求解的自由度、行程或关节。

## 开发入口

- [开发方案](docs/DEVELOPMENT_PLAN.md)：当前建议路线与首轮交付。
- [样例体检](docs/ASSET_AUDIT.md)：真实文件、已知信息、未知信息。
- [数据契约](docs/DATA_CONTRACT.md)：实例、刚体、关节、证据与控制接口。
- [任务清单](docs/BACKLOG.md)：可转换为 GitHub Issues 的工作项。
- [来源与选型](docs/SOURCES.md)：工具版本、核查范围与适用边界。
- [仓库约定](docs/REPOSITORY_STATUS.md)：正式开发地址、默认分支与当前范围。

首个里程碑是：能准确选择 CAD 实例，查看候选刚体分组与运动轴，修正并保存证据，在经确认的范围内让一条升降链运动，再扩展到三条。三条轴是否独立、是否存在共享运动件和附属机构均需实际验证。

## 工程约定

正式仓库为 [leixn01/3dmodel-rcgn](https://github.com/leixn01/3dmodel-rcgn)，默认分支为 `main`。原始 CAD、STEP、图片、PLC 工程与电气工程留在外部资产源，通过版本与校验值关联。内部保持完整约束图；URDF、MJCF、FreeCAD 或 PS 输出是适配产物。

未提供的机械限位、控制软限位、传动参数和信号映射保留为未知。动画可运行不等于真实机构已还原；可视化演示不等于 PLC 安全审查已通过。

代码许可状态见 [LICENSE.md](LICENSE.md)。依赖开源工具不代表原生 SolidWorks 通道不需要商业软件。
