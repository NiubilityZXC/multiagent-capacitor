# Ren 重叠首两组真实试跑边界

原P1-R1范围。仅冻结来源命名顺序的batch1/1、batch1/2，复用已恢复数据及schema/chronology前置证据，不重做archive或解压。此为pilot，不是113组全量重叠或Data Gate。先整体独立pre-run review和单独hash-matched release，后读取真实数据；release缺失先停止。

Workbook-only测量流逐条对照预期member/sheet/Excel行位置；一个组的跨表/续片流连续送入固定K8/window25筛选。token和optional energy以49-byte固定记录写入ignored spool，原位映射依据冻结schema spans。source生成流完整消耗、写入摘要与落盘摘要一致后才接受；不得把提前EOF或晚期异常当成功。落盘量为原始测量表示，不是新容量/SOH/RUL目标。

SQLite逐组事务索引。以落盘token的独立window-min实现逐项重建全部指纹，核验遗漏/额外/位置/值。所有跨组同指纹候选逐值回读并核验energy，匹配保留ignored明细；公开只有计数和工件绑定。随后用独立有界数组比较逻辑重建匹配明细、计数，并再次核验spool、group记录和索引。相同来源位置映射约定和字节编码是共享边界，不宣称独立XLS解析器。

固定候选pair预算1,000,000，超出即BLOCKED，不截断后宣称PASS。磁盘预检2GiB。仅单CPU本地任务，无依赖新增、网络、模型/API、GPU或数值预测。既有seals、旧失败记录不修改。新目录append-only，异常保留BLOCKED和部分证据，不自动重试或续写。

确认区间仅为至少32条、最多56条的精确公共投影重叠，不是最大重复事件；多个anchor可能对应同一片段，公开计数不是独立重复事件数。短片段、近似复制、状态/时钟变换不在保证内；energy缺失不证明完整行一致。所有身份、目标、P2、自动下一阶段标志均false。正式全量运行需pilot收取/复核后新放行，不能用本次release放行全量。
