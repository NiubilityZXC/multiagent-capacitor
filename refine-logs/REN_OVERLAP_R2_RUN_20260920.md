# R2 全量重叠审计启动记录

2026-09-20 11:11 +08:00。ARIS experiment-bridge / run-experiment / monitor-experiment。

## 放行依据

沿用 REN_OVERLAP_R2_APPROVAL_20260917.md，仅一次新 R2。fresh GPT-5.6-Sol xhigh 整体复审 PASS，无阻断；same-family provisional engineering，不是科学结果审查。主执行者重算报告中的全部 35 项 SHA-256，与当前文件完全一致，旧 29 项未变。

完整复审在 ignored `data/raw/ren_scs/r2_integration_review_20260920.md`，SHA-256 `f959de0b0054c917913b15b8d64dd37bca023d11393468b00a51aeeccedc71d3`。完整请求/响应保存于 `.aris/traces/experiment-bridge/2026-09-20_run01/001-r2-integration-review`。公开 release 为 REN_OVERLAP_R2_RELEASE_20260920.json 及同内容固定别名 REN_OVERLAP_R2_RELEASE.json。

测试：主执行者必测 218 passed / 0 skipped；reviewer 75 passed / 0 skipped；一般回归 683 passed / 58 skipped。未限定目录的首次回归收集失败单独记于 REN_OVERLAP_R2_RESUMPTION_20260920_110520.md，不隐去。

## 实际启动

```text
.venv-ren-p1r1/bin/python experiments/audit_cap/ren_overlap_fleet_r2.py --launch --project-root /home/user/multiagent-capacitor
```

launcher 实际 exit 0，返回 `LAUNCHED_NOT_COMPLETED`。supervisor PID 1650298，实际审计 child PID 1650299；STARTED.started_unix=1789873867.3613317。首次复核时 supervisor PPID=1，child 正在运行，约 11 秒 CPU，尚无终止回执。

本地 CPU，复用 `.venv-ren-p1r1`；无新安装、GPU、API 或模型。stdout/stderr 指向普通持久文件，不经过 tee。单次扫描按 frozen 113 组 / 233 文件 / 1,633 表 / 104,190,778 行执行。固定候选预算 1,000,000；40 GiB 起始空间门槛不变。总耗时尚无可靠实测，不把早期组速度线性外推成承诺。

本地 ignored job 目录：`data/raw/ren_scs/overlap_fleet_20260917_r2_job`，含 REQUEST、STARTED、runtime.log；终止后应有 RETURNED。ignored 数据目录：`data/raw/ren_scs/overlap_fleet_20260917_r2`。公开结果目录：`data/audit/ren_scs/overlap_fleet_20260917_r2`。

## 完成标准与下一步

本文件只证明启动，不证明数据处理成功。需真实 RETURNED.child_returncode=0、完整 SUMMARY/COMPLETE 与独立结果对账。任何失败保留现场并停下，不自动重试。v1 的 BLOCKED 和半成品完整保留。

即使 overlap 完成，Data Gate 仍需身份、容量目标可推导性、终止/删失、whole-unit split 的证据裁决。主任务为电容量/容量 SOH；ESR 固定 NA，RUL 单独 Gate，不能以它们缺失无条件阻断容量任务。此轮不生成数值目标，也不运行 P2。

固定 tracker/MANIFEST 的 Update File 受当前 bwrap 故障影响未更新；本文件及带日期恢复记录提供最新状态，旧文件保留为历史。
