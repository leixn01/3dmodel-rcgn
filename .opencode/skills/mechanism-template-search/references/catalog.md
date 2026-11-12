# 目录说明

cad_list_mechanism_templates 参数：query（可选英文子串，最长200字符），include_heldout（默认false）。中文需求可映射为 lifting、linear_motion、clamping、shaft、bearing、gear、rotation；查询不命中可省略query列出参考项。目录查询不依赖usd-core、不连接SolidWorks、不下载数据。

六个reference项含四个有关节参考和两个无关节负例。planetary_gearbox、bar_clamp 两个heldout留作后续结构匹配评测；查看或参与调参后不能声称仍是未见测试。

expected 是源模型作者的已标注数量，不是物理真实性保证。资产名称、标签不能替代实际关节字段；轴系/齿轮套件无关节时不能补造。原始完整模型的地址在asset_url，本仓库仅保留轻量结构摘录。
