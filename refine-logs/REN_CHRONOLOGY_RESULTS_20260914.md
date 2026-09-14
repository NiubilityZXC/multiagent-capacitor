# Ren 全量记录时序审计结果

2026-09-14。运行版本 record_chronology_20260911_v1。原 Ren P1-R1 范围，ARIS experiment-bridge / monitor-experiment。

## 实际执行结果

任务已完成，持久化日志最后记录 child_returncode=0；不是凭 COMPLETE 文件推测退出码。113 条进度连续覆盖 1..113，记录扫描累计 1,869.6 秒（约 31.2 分钟，不含前置核验）。

| 项目 | 结果 |
|---|---:|
| 来源命名候选组 | 113 |
| 文件 | 233 |
| record 表 | 1,633 |
| 数据记录（不含表头） | 104,190,778 |
| 文件内表边界 / 跨文件续片边界 | 1,400 / 120 |
| 编号重复、回退、前向缺口 | 均为 0 |
| 无效 key、cycle 回退、同工步时间下降 | 均为 0 |
| 工步变化 / 时间下降 | 3,009,887 / 3,009,887 |

全部相邻有效记录对为 104,190,665，恰为记录数减 113 个组；不跨组连边。所有时间下降都发生于 cycle/step/status 三元组变化处；这里的“工步变化”按该三元组定义，不能据此声称已验证设备物理工况或全局物理时钟。

四批记录数依次为 5,073,621、7,793,294、45,778,038、45,545,825。status 0/1 分别 50,423,380 / 53,767,398 条；本审计未擅自将代码映射为充电/放电物理含义。

## 对账与测试

主执行者重新读取全部 113 组 ignored 证据和公开回执，重算证据哈希与边界/聚合统计，并与 SUMMARY、COMPLETE 和完整运行日志对账一致。收取记录见 data/audit/ren_scs/CHRONOLOGY_COLLECTION_20260914.json；这是持久化重建，不是第二个 XLS 解析器或全量原始行重跑。

运行后必测套件再次执行：122 passed in 2.58s，退出码 0，无跳过。命令为隔离 .venv-audit-cap/bin/python -m pytest -q tests/test_ren_chronology.py tests/test_ren_fleet_schema.py tests/test_ren_workbook_reader.py tests/test_ren_row_pilot.py --basetemp data/raw/ren_scs/chronology_postrun_parent_tests_20260914。

- SUMMARY SHA-256：90600e3546069a0be49d3599ecf41a91ab6205d77f91b98c332305994147fe40。
- COMPLETE SHA-256：3440a45453065dca7daee3418ceef70e22917878050c9dc1fce69d4c2e82330f。
- ignored runtime log SHA-256：e5af66e44adda576fde7351d85669723d33f5030438ae18b1e6f0fa9cda1f4a3。

## 裁决边界

状态仍为 FULL_CHRONOLOGY_OBSERVATIONS_DATA_GATE_PENDING。没有目标值、模型/API、RUL、GPU 或 P2。组内连续性不证明跨组测量独立性；113 个命名候选组尚未自动升级为 whole-device LOCO 单位。剩余证据与最短推进路径见 REN_R1F_REMAINING_EVIDENCE_20260914.md。

独立 post-run 审查单独保存；其结论不得替代物理身份、目标、删失和切分 Gate。

正式独立结论：PASS_CHRONOLOGY_POSTRUN_ENGINEERING_RECONCILIATION，无 blocking/non-blocking defect。fresh reviewer /root/chronology_postrun（gpt-5.6-sol xhigh）逐组独立重建边界与统计，核对全部旧 schema 覆盖、16 项 policy、SUMMARY/COMPLETE 及日志。属于 same-family provisional 工程复核，不是科研有效性判决。完整响应保留在 ignored data/raw/ren_scs/chronology_postrun_response_20260914.md，SHA-256 为 4093441915cb98fb795f8403af97d95b8a28b216c51054819c0c0cd0a5863b15。ARIS 完整请求/响应 trace 已保存。
