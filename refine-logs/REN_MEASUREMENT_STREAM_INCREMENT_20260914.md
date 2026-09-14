# Ren Workbook 测量流适配层增量

2026-09-14。ARIS experiment-bridge。没有真实测量读取、运行 release、模型或数值目标。

新增 ren_measurement_stream.py，复用冻结的 BIFF guard 与 schema Workbook SHA。只向 xlrd 传独立 Workbook bytes；逐 record 表核对名称、索引、维度、8/9 列表头及类型。每行五字段 key 由两条访问路径一致重建；测量列须为有限 numeric cell，不能接受数值字符串；公共投影 token 通过独立 struct 路径重建一致后才输出。可选 energy 保留，供后续完整行确认，不参与筛选。

流输出只供本地审计 caller 消费：(0-based sheet index, sheet name, 1-based XLS row, canonical token, optional energy)。首数据行为 Excel 第 2 行；并未写出文件或上传测量值。后续 caller 负责附 member/group/全组偏移，不得在表或续片处重置 winnow。

生成器必须完整消费才可能视为完成。异常、提前关闭与正常结束都释放工作簿资源；数据已部分 yield 不意味着该文件审计通过。合成两表案例明确覆盖第二表失败：第一条已读后仍会抛错，caller 不得捕获后当 EOF。caller 尚未实现，不能声称端到端关闭链已完成。

17 项新增适配层测试（真实 xlrd 解析合成 BIFF8），覆盖 8/9 列、位置/energy、坏类型/时间/非有限值、schema 漂移、独立 token 篡改、提前关闭资源回收、40 行跨表筛选和晚期失败。初次测试收集因 fixture import path 写成顶级模块失败；已改为项目 tests 包路径后重新执行。合并隔离套件 160 passed in 2.69s，无跳过；未安装新依赖。

下一步仍为 ignored 磁盘索引、全组位置映射、候选片段回读与逐值确认、合并单位/目标语义计数和完整 caller 对抗测试。只有完整集成的 fresh pre-run review 与新 release 才允许下一轮真实数据读取。

一般全项目回归 631 passed, 52 skipped in 40.68s，退出码0。新增17项 xlrd 依赖测试在一般环境跳过，但均在上述160项隔离套件实际通过。原始测试记录保留 ignored measurement_stream_parent_tests_20260914.md。

独立复审状态：PENDING。任务 /root/measurement_stream_review 已提交 gpt-5.6-sol xhigh；主执行者检查任务状态为 pending_init，尚未获得正式响应。不能记为独立 PASS，没有创建运行 release。代码和测试作为待复审候选提交，不代表部署。
