# 解析边界

必填output_path；template_id与asset_path恰有一个。结果文件是raw graph，MCP返回是envelope；比较工具读取output_path中的raw graph，不读取另存的envelope。

在用户已激活Conda中安装 `python -m pip install -e ".[solidworks,templates]"`。不创建.venv，不需要Isaac Sim。模板工具不启动SolidWorks。

自带摘录可直接解析。外部输入须在项目内，独立USD/USDA/USDC，不超过64MiB/20000 prim；外部reference/payload/sublayer、variants、instances、inherits、specializes被明确拒绝。不能为消除错误删除源结构；保留源文件，未来通过独立归一化能力处理。USD_DEPENDENCY_MISSING说明当前Conda缺usd-core；OUTPUT_EXISTS换新文件名；格式或来源不支持时说明边界并继续其他已有模板。

输出：bodies记录源ID、enabled、kinematic、根变换与geometry_members；摘录的geometry_members只是原始网格路径，不是已打包几何。joints记录fixed/prismatic/revolute（其他unsupported）、两端body/静态/world身份、局部四元数、世界轴线/锚点和限位。anchors/origin与平移限位为米，转角限位为度；源矩阵保持USD行向量与stage单位，不能当作CAD列向量米矩阵。世界方向仍在资产自身upAxis坐标中，不自动跨资产对齐。

complete仅说明本次解析覆盖，不保证机构物理正确。缩放/镜像/剪切轴线留空；不解算mimic/gear/tendon耦合；仅读默认时刻。NO_JOINTS、未知耦合等保留partial/risks，requires_human_review=false。
