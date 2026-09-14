# Ren 记录时序审计启动记录

2026-09-14，沿用原 Ren P1-R1 批准范围。运行版本名保留 record_chronology_20260911_v1（候选建立日期）；实际启动日期为 2026-09-14。

ARIS experiment-bridge fresh pre-run review：PASS_RECORD_CHRONOLOGY_AUDIT，无阻断。审查者 /root/chronology_prerun，gpt-5.6-sol xhigh，same-family provisional 工程审查。原始请求/响应保留在 ignored data/raw/ren_scs/；响应 SHA-256 为 45b0383bb3c0577bb3206f4eed2caca354d2104bf9261e342f8f2e17a1a13f4b。

16 项代码、测试和既有 .gitignore 的哈希重新核对一致，放行绑定见 REN_CHRONOLOGY_RELEASE_20260914_111800.json 与固定副本。必测套件主执行者 122 passed / 0 skipped，独立审查者 122 passed / 0 skipped；一般回归 610 passed / 35 skipped，xlrd 相关必测在隔离审计环境实际执行。

真实本地 CPU 任务已启动，session 45594。命令为 .venv-ren-p1r1/bin/python experiments/audit_cap/ren_chronology_gate.py --project-root /home/user/multiagent-capacitor；外层 subprocess.run 将真实 child_returncode 写入 ignored chronology_runtime_20260914.log，管道开启 pipefail。

范围：113 个来源命名候选组、233 文件、1,633 个 record 表、104,190,778 条记录的五字段时序观察。逐表双路径字段重建、逐组持久化对账；不计算容量目标、不执行作者代码、模型、API、RUL 或 P2。

本记录仅证明启动，不证明完成。收取 COMPLETE、全部 receipts 与实际退出码后才能记录运行结果。异常计数不自动判定错误、修复数据或批准 Data Gate；物理身份、跨组局部重叠、目标定义和切分仍需核验。旧失败记录及 seals 保留。
