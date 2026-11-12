# 参数与范围

cad_proximity_candidates 必填 inventory_path、output_path、max_box_gap_mm（毫米，非负）。可选 occurrence_paths 为 2–200 个唯一叶实例路径；未传时用清单全部叶实例，最多 5000 个。默认 max_pairs=20000（上限 200000）、max_candidates=200（上限 2000）。

输入为 sw_spatial_inventory 完整 envelope；推荐 spatial-export 收齐所有页，不能使用 --without-boxes。collection_complete/hierarchy_complete 必须为 true 且无层级截断。几何缺失允许进入结果，但对应实例列于 unranked_occurrences，并保留 partial。

先选择一条链的少量实际叶实例。没有工程阈值时可将 5 mm 明确标记为探索筛选值，不能称工程公差。box_gap_hint_mm 是近似根坐标轴对齐盒间的间隔提示；盒重叠不等于模型接触，提示不能代替精密测量。

max_pairs 按稳定实例路径顺序检查前缀，然后在已检查范围内按提示排序；预算截断时不是全局最近邻。max_candidates 只保留已检查范围内较近的提示。coverage 同时保留 scope_pairs、eligible_pairs、checked_pairs、matching_hints_before_output_limit 与 returned_candidates。

- INCOMPLETE_INVENTORY：补齐空间层级/分页，不拼接不一致快照。
- UNRANKED_OCCURRENCES：缺盒、错误单位/派生值或未解析实例，保留名单，不能把它们当远离。
- PROXIMITY_PAIR_LIMIT / PROXIMITY_CANDIDATE_LIMIT：partial/truncated；缩小显式范围或合理调整预算，不能宣称覆盖整机。
- OUTPUT_EXISTS / INVALID_PATH：outputs 内新文件，不覆盖。

CLI：python -m cadkin proximity <spatial.json> --max-box-gap-mm 5 --output outputs/<新文件>.json；显式范围用 --occurrences <路径A> <路径B>。本工具离线，不需要装配仍打开；后续测量必须使用同一稳定模型上下文。
