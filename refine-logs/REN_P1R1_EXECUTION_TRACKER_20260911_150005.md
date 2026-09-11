# Ren Data Gate 修复进展

时间：2026-09-11 15:00:05 +08:00。ARIS：experiment-bridge。

## 本轮实际结果

首文件只读行级试跑已成功，进程 exit 0，状态为 FIRST_MEMBER_SCHEMA_AUDITED_DATA_GATE_PENDING。不是全数据集 Data Gate PASS。

- 文件按旧 233 份已验证静态报告的 member_path 字典序固定选择：batch1/1.xls；不依据模型或预测结果选择。
- 读取 5 张表，合计 211,256 个存储行（包含每张表的表头；不能称为 211,256 个独立样本）。
- step：20,001 行；cycle：10,002 行；record_1 / record_2：各 65,536 行；record_3：50,181 行。
- 数字/日期单元格非有限计数为 0。这不等于缺失值、异常值、完整性或时间顺序全部通过。
- 仅将唯一 Workbook 流交给 xlrd 2.0.2；VBA/对象流不作为读者输入。未执行公式、宏、模型、API、RUL 或 P2。

命令：`.venv-ren-p1r1/bin/python experiments/audit_cap/ren_row_pilot.py --project-root /home/user/multiagent-capacitor`

公开工件：data/audit/ren_scs/row_pilot_20260910_v1/SUMMARY.json 与 COMPLETE.json。目录名沿用冻结候选版本日期，真实执行日期为 2026-09-11，没有修改冻结代码以重命名版本。

原始文本提示只存 ignored staging：data/raw/ren_scs/row_pilot_20260910_v1/SCHEMA_ROWS.json。SHA-256：488310967c7fe22c1cc8661183271fad3fdb6fcf202b2bad2569b3e9cfc450ee。

## 审查和测试

上一轮会话中断后无已保存复审结论，且无存活 reviewer；本轮重新派发 fresh GPT-5.6-Sol xhigh，未声称恢复了不存在的 PASS。新审查结论 PASS_FIRST_MEMBER_ROW_PILOT，无 BLOCKING；完整响应 SHA-256 为 8dcf3c647c55c8e2f8fe2970e899693e19a9bc25a606711a21b6a16f8c37a463。七项代码/测试/政策哈希与 release 一致。该结论是 same-family provisional 工程审查，不是科学有效性验证。

- 主执行者定向审计测试：31 passed in 0.50s，无跳过。
- 独立 reviewer 定向审计测试：31 passed in 0.24s，无跳过。
- 全项目回归：552 passed, 2 skipped in 40.61s。两项真实 xlrd 合成集成测试只在缺少该依赖的通用模型环境跳过，在上述隔离审计环境均实际通过。
- trace：.aris/traces/experiment-bridge/2026-09-11_run01/001-ren-row-pilot-prerun-pass；原始 request/response 均 ignored。
- release：refine-logs/REN_ROW_PILOT_RELEASE_20260911_145842.json 与固定最新副本。

没有重做下载、archive test 或解压。既有恢复 verifier 对原有证据重新核验后才进入试跑；旧失败目录、BLOCKED_ROW_PARSE、seals 和审查记录均保持不变。

## 从真实 schema 得到的下一步约束

1. 首文件 step / record 的 capacity 表头单位为 mAh；cycle 表含 charge_capacity(mAh)、discharge_capacity(mAh)。这是电荷容量字段，不可仅因英文名 capacity 就标作 F。原计划的 derived capacitance 仍待电压范围、工步和推导依据核验，不能擅自替换已冻结 target。
2. record 表有 cycle、step、status、record_number、record_time、voltage(V)、current(mA)、capacity(mAh)；已观察的文本时间提示存在归零，不能当成全局单调老化时间。需要核验它与工步边界及跨 sheet/file 延续的关系，而不是排序后静默修复。
3. 两张 record 表达到 XLS 的 65,536 行上限；这不是已证实截断。必须检查跨 sheet 的记录编号、工步、cycle 连续性与重叠，再判断是否完整。
4. 本次输出中未建立物理电容身份。不能把文件名或 sheet 数当设备数，也不能因出现 cycle 列就宣布整电容 LOCO 成立。

## 接续任务与实验起点

下一版本复用已验证的 Workbook-only 读取边界，对全部 233 文件进行只读 schema/row 审计，形成表头/单位、行数/类型/缺失、连续性、重复和身份证据账本；补齐独立重建与对抗测试并经过该版本的 pre-run review 后执行。范围仍是原 P1-R1，不需要重复批准已完成的归档恢复。

只有全量 R1E 与 R1F 的物理身份、时间、目标、重复及切分证据成立，才能冻结具体 P2 数据/目标/切分 seal，按既有人工节点进入预测实验。目前完成 1/233 文件的 schema pilot，R1F 尚未完成；没有可诚实承诺的模型实验开始日期。所有候选实验路线（直接 LLM Agent、LLM+专用模型、专用模型基线）均保留，不用审查意见代替真实数值测试。
