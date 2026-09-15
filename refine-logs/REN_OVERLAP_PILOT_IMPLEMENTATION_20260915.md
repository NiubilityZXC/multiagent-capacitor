# Ren 首两组重叠试跑实现

2026-09-15，ARIS experiment-bridge，原P1-R1批准内。新caller与pipeline实现完毕，当前预运行复审未收取，不视为已放行或真实运行。

固定试跑batch1/1与batch1/2；前期schema元数据重建6张record表，362,703条记录。仅49byte spool预计17,772,447bytes（不含索引/日志），入口要求至少2GiB磁盘余量。候选pair预算固定1,000,000，超额强停止，不作结果截断。完整113组需另行放行，不可扩用此pilot release。

新pipeline验证逐行member、sheet、Excel行号与完整输入消耗，生成ignored测量spool和SQLite索引；源流写入摘要与spool回读摘要相同。另一路window-min实现从spool重建全指纹序列，独立比较原索引。匹配以逐值seed/扩展法生成，然后用有界数组法独立重建明细与计数；再次对账spool/组/索引后写SUMMARY/COMPLETE。不是单纯信任内存中的完成标志。

新测试含完整pipeline持久化、少行/多行/乱位置/晚期异常、篡改确认结果、索引遗漏、候选预算强停止、release缺失先停、原始位置几何、spool截断、synthetic BIFF8到真实xlrd适配层再到磁盘/确认。仅preflight和OLE剥离在caller小例使用替身；没有读实际XLS。初次3项失败属于合成样本仅1个fingerprint导致测试未触发预期预算/遗漏分支，以及旧strict JSON异常类型断言不符；将样本扩至80行并匹配既有RecoveryError后重跑。

隔离合并测试193 passed in2.99s，无跳过。全部旧seals与已审查组件不修改。新代码、测试、policy将由单独release绑定，release不存在时真实入口先停止。所有身份/目标/P2/自动下一阶段标志false，匹配计数是可能重复覆盖的anchor确认区间，不是独立设备或重复事件数。
