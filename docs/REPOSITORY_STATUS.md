# 仓库与开发约定

- 正式仓库：[leixn01/3dmodel-rcgn](https://github.com/leixn01/3dmodel-rcgn)。
- 默认分支：`main`。
- 项目名称：3DModel-RCGN；Python 包名 `3dmodel-rcgn`，导入包 `cadkin`。
- 代码、方案、任务清单与验证记录直接在该仓库维护。
- 第一阶段范围：输入体检、运动关系数据契约、开发基线；完整自动识别与 SolidWorks 导入适配仍在待开发范围。
- 模型来源与校验值保存在 `configs/`，原始资产由下载命令取得。
- 实际提交记录以仓库 Commits 页面为准，持续集成以 Actions 页面为准。

STEP 是 SolidWorks 可读取的数模格式。开发时先检查真实导入结果，再决定已有约束解析、模板和几何推断分别承担哪些工作。
