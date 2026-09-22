# 容量资格审计 Workbook 适配器

2026-09-22。ARIS experiment-bridge；恢复 09-21 额度中断工作。不是完整 fleet caller、真实数据 release 或 Data Gate。

## 已实现范围

`experiments/audit_cap/ren_target_workbook.py` 只接受已经隔离的 Workbook 字节、允许 BIFF 集合和来源绑定 schema，无文件读取 CLI。复用冻结 BIFF 防护，核对流哈希、表数量/次序/尺寸和原生表头。

输出 record、step、cycle 三类 canonical 事件，保留 sheet index/name 与一基 XLS 行号。支持两类工步表（有/无电压端点）、两类周期表（有/无 energy）及 8/9 列记录表；记录 energy 独立保留。时间转整数微秒，mAh 保持 mAh，不推导 F、SOH 或 RUL。

row/cell 两路独立重建每个字段；非有限值、错误类型、警告、未知表、尺寸/哈希/重建不符时失败。早停和晚到错误释放资源。下游必须完整消费全部输入，并自行绑定外层 source identity；部分事件不代表完成。

## 合成验证

- 适配器及逐字段对抗测试：50 passed，0.25 秒（09-21 专用审计环境）。
- 全部 Ren 审计与持久日志测试：456 passed，11.21 秒，无跳过。
- 09-22 一般回归：721 passed、108 skipped，41.64 秒。较前轮多出的 50 个跳过来自一般环境缺少 xlrd；它们已在专用环境实测，不以跳过冒充通过。
- fresh GPT-5.6-Sol xhigh 独立复审 PASS，无阻断；定向 50 passed（0.26 秒），依赖 78 passed（1.43 秒）。same-family / provisional，仅限组件，不是实际数据放行。
- 完整报告 ignored：`data/raw/ren_scs/target_workbook_review_20260921.md`；SHA-256 `ce08c351275af7c99e2a1e0351c649dbcca4485814ae2b872310c0c6338f2731`。trace 在 `.aris/traces/experiment-bridge/2026-09-21_run02/`，昨日中断 ERROR 与今日 OK 分别保存。

## 精确版本

- implementation：`9767b88af726c2456897360ae3ce0c0a94f4cadbf3d175de52ae49a02f5cdc42`。
- integration tests：`b635ddbe1f344c3b9314ecf86dd5f5547697f93ef261056ef3b723733604a9f9`。
- adversarial tests：`a306036b843f84bba603c22d961129a62ee9a935b5082b0e5df2684236108789`。

下一步仍须完成 source-bound group/fleet caller、跨片位置与 energy 对照、cycle 汇总/终止证据、独立字段重建和整体 pre-run review。现有两个 reducer/join 组件可复用。不更改 R2 seals，不重复原始全量 overlap；不运行模型/API/P2。
