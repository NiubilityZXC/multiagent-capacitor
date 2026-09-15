# Ren Data Gate 修复进展

时间：2026-09-15 10:57 +08:00。ARIS experiment-bridge。

## 已完成的真实数据审计

全量 schema 与时序运行已完成并独立对账：113 来源命名候选组、233 文件、1,633 record 表、104,190,778 条记录；时序日志实际退出码0。编号重复/回退/缺口、无效 key、cycle 回退和同工步时间下降均为0。详见 REN_CHRONOLOGY_RESULTS_20260914.md。旧结果、seals和失败记录保持不变。

## 当前实现状态

跨组重叠纯内核 ren_overlap.py 已经独立复审通过，精确32行公共测量投影的候选保证不等于设备重复结论。

新 Workbook 适配层首次独立复审发现 schema 被标为 step/cycle 时可能漏读记录表。已修复为先核对每张实际表的 name/nrows/ncols，再决定跳过；加入4个对抗组合。R2独立复审PASS，无阻断，原BLOCKED与未复审候选提交ab6c3ea保留。历史pending_init状态已经结束。

R2隔离必测164通过无跳过；独立目标套件42通过；一般回归631通过56跳过（所需xlrd路径已在隔离环境实际通过）。详细修复、两轮审查响应哈希及边界见 REN_MEASUREMENT_STREAM_R2_20260914.md。

## 下一执行单元

整体集成 ignored 磁盘索引、全组/续片原始位置、候选匹配回读与逐值确认、单位/目标语义计数和caller持久化重建。完成端到端对抗测试及整体独立pre-run review后再建运行release；当前没有真实重叠审计进程，不重跑已完成的archive/schema/时序。

Data Gate仍pending：跨组测量重叠、结合来源与行证据的设备身份、容量/ESR资格、终止与删失、whole-unit切分尚未全部核验。作者源码rated=True下0.903实际为F阈值，不可直接当90.3%初始SOH。没有数值目标、模型/API、RUL、GPU或P2实验。最终Gate后仍需按原计划冻结新P2seal并批准。

## 9月15日新增：磁盘索引与有界回读确认

ren_overlap_index.py 已实现每组事务、跨组指纹全枚举、8行seed逐值核验与32行匹配确认、energy缺失/冲突计数及跨文件位置映射。17项新增测试包含合成BIFF8到索引/回读的小型端到端。隔离181测试通过无跳过，一般647通过57跳过；独立复审PASS，额外15,625种位置组合通过。详见 REN_OVERLAP_INDEX_INCREMENT_20260915.md。

这是集成helper，不是真实运行入口：trusted原始位置回读、全量覆盖/索引独立重建、结果持久化与失败记录、单位/目标统计和整体pre-run release仍待完成。当前没有真实重叠审计或预测实验进程。旧Gate状态未改变。
