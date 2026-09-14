# Ren 测量流 R2 修复记录

2026-09-14 晚间继续执行。原候选提交 ab6c3ea 和首次独立 BLOCKED 审查保留；之前 pending_init 为历史快照，不是当前结论。

独立复审发现真实覆盖漏洞：schema 记录表名称被改成 step/cycle 后，旧适配层在读取实际表之前跳过该项。双表合成复现会漏掉第一张记录表而不报错。这是新适配层缺陷，旧全量时序运行的原始 schema、seals 和结果未改动；不能据本缺陷臆称旧结果已被污染。

R2 将实际 sheet 读取、name/nrows/ncols 与 schema 对比移至任何 step/cycle 跳过之前；跳过的汇总表也经 finally 卸载。新增4个回归组合：第一/第二张记录表各自被标成 step/cycle，均必须抛错，不能接受部分输出。

隔离全审计套件实际164 passed in2.66s，无跳过，退出码0。修复仍需复审确认；没有新运行 release 或真实数据执行。磁盘索引、回读确认、目标语义统计和完整 caller 仍待集成。

首次完整审查响应：ignored data/raw/ren_scs/measurement_stream_review_response_20260914.md，SHA-256 7600463858a0a486b3c3e0fbc5e7628a8d70df4c6cc3805c561a860f66943078。ARIS trace 已保存。R2 复审另存新文件，禁止覆盖首次 BLOCKED。

R2 正式复审：PASS — PRIOR COVERAGE BLOCKER FIXED; NO BLOCKING DEFECTS FOUND。独立目标套件42 passed in0.30s，无跳过；四个原漏洞组合均拒绝。新响应 measurement_stream_r2_review_response_20260914.md 的 SHA-256 为 ae415055bfa01a1396c90b3714d45ed6747caa71c878c702ff065c86e15712f0；新 trace 已保存。same-family provisional，仅适配层工程复核，不是整个执行器放行。

修复后一般回归631 passed,56 skipped in40.04s，退出码0；其中新增/修复的21项适配层测试均在隔离164项套件执行，非跳过替代验证。没有新依赖、真实数据运行或模型/API调用。
