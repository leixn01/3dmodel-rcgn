---
name: mechanism-template-extract
description: 从选定的结构参考或项目内独立USD文件提取刚体、关节、坐标、轴线和限位，保留来源及不完整项。用于“读取这个参考模板的机构结构”“解析USD关节”；不负责检索、SolidWorks采集、目标匹配或仿真。
---

# 提取模板结构

输入：一个template_id或一个asset_path。输出：outputs下新的机构图JSON。

1. 调用 cad_extract_mechanism_template；两个输入只选其一，不覆盖已有结果。
2. 报告刚体/关节类型数量、complete及risks。字段缺失、未知耦合和无关节都保留，不从名称补造。
3. 轴线/限位仅描述参考资产；不能直接迁移到用户STEP。没有关节也输出已有刚体并说明风险，继续可独立完成的步骤。
4. 有比较需求时只交接原始图文件和哈希；不自动建立对应关系，不请求人工机械确认。

遇到单位、坐标、USD格式或依赖问题时读 [解析边界](references/extraction.md)。常规调用按工具Schema，不预加载其他skill。
