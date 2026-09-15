# Ren 磁盘重叠索引与回读确认增量

2026-09-15。ARIS experiment-bridge。仅合成验证，无实际数据/API/模型运行，无新 release。

新增 ren_overlap_index.py：SQLite 磁盘索引每组事务插入 (digest,gid,offset)，中途生成器失败或非法位置会整组回滚。旧路径拒绝覆盖。每个候选位置必须递增且落在组的8行shingle有效范围；长度至少32却无任何指纹会拒绝。索引本身不证明指纹覆盖完整，仍需caller将实际读取行数/位置和独立重建的索引与冻结schema对账。

跨组配对由磁盘等值联接逐条产出，不把所有候选积入Python列表、不限制前N项、不把同组重复当跨组匹配。调用方须完全消费后才可判定枚举完成；不能边写索引边读pairs。重复指纹的候选数可能平方增长，流式不意味着候选数量被压缩，也不能据此承诺运行时长。SQLite缓存设置8MiB、临时表落磁盘，不是整个进程内存上界。

confirm_anchor 接收可信原始位置readback回调，以8条seed为中心最多向前/后各24条逐值比较，足以确认包含该seed的任意32条精确公共投影片段。先确认seed，不会仅凭相同digest接受碰撞候选；再独立重读整个返回区间以核对匹配。返回的最长56条是有界确认区间，不是完整最大重复长度。energy双方均有时比较、不一致单独计数；任一方缺失单独计数。物理身份与最大重复范围始终未验证。

source_position 将全组偏移映射回ordered(member,sheet_index,sheet_name,row_count)中的Excel行号（首数据行为2）。span来源/顺序与总行覆盖必须由caller冻结并核对，不从文件名推断设备身份。

17项新测试覆盖错位复制、人为相同digest但值不同、optional energy、全部25种seed位置、31条短匹配、非法回读、事务回滚、已有路径拒绝、48个重复候选全部枚举、跨续片位置映射、缺失指纹拒绝。另含合成BIFF8→实际xlrd适配层→winnow→磁盘索引→确认的端到端小例：两组相同40条测量分别在20/20和13/27行处分表，仍识别到匹配。这不是真实数据审计。

隔离合并测试181 passed in2.86s，无跳过，退出码0。仍待最终运行caller、ignored原始测量位置回读实现、索引/结果独立持久化重建、覆盖失败记录、单位/目标语义统计、资源预算以及整体pre-run review。没有将合成端到端测试冒充完整真实执行器。

一般全回归647 passed,57 skipped in41.55s，退出码0；实际xlrd路径在隔离套件全部执行。fresh GPT-5.6-Sol xhigh独立复审PASS，无阻断；目标套件59 passed in0.57s，无跳过；额外15,625个精确32条复制的seed/prefix位置组合全部通过。审查为same-family provisional integration-helper review，不是整体运行放行。

完整响应ignored data/raw/ren_scs/overlap_index_review_response_20260915.md，SHA-256 1b99b7f4a1a878d78598e6a4c0eaafbee7936b5411fe0c21f25020997d200c1a。完整ARIS trace及原始测试记录已保存。原reader、适配层R2、重叠内核及旧审计seals均未改动。
