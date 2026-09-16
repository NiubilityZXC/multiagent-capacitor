# Ren 全量重叠审计启动记录

2026-09-16 14:44 +08:00，沿用P1-R1批准范围，ARIS experiment-bridge。旧pilot和全部历史审查保留。

独立pre-run响应 `data/raw/ren_scs/overlap_fleet_prerun_response_20260915.md`（ignored）裁决 `PASS_OVERLAP_FULL_FLEET`，SHA256 `080db7e5decdc54ab767cb837a16909687b2a65a0dccba4fb12ae0eb07afaa3a`。主执行者在9月16日重新核验其29项policy map与当前文件逐项一致，未编辑冻结代码，生成独立全量release。审查属于same-family provisional engineering，不是科学结果接受性。

此前主执行者必测209通过、0跳过，独立复审209通过、0跳过；一般回归674通过、58跳过（必需XLS路径由隔离套件实际覆盖）。未把测试用合成数据称作科学结果。

启动命令的实际子进程：

```bash
.venv-ren-p1r1/bin/python experiments/audit_cap/ren_overlap_fleet.py --project-root /home/user/multiagent-capacitor
```

外层launcher保存开始时间、真实child_returncode和elapsed_seconds，日志位于ignored `data/raw/ren_scs/overlap_fleet_runtime_20260916.log`。开始unix时间1789541066.6281743。run ID沿用已复审的 `overlap_fleet_20260915_v1`，不能因实际启动日期变化修改已冻结代码。14:44:44已观察到1/113组完成，尚无完成或成功声明。

运行目标：113来源命名组、233文件、1633 record表、104190778条记录。只读已恢复来源，写ignored spool/index/matches；启动空间门槛40GiB，候选预算1000000，超限fail closed。没有archive重跑、下载、解压、模型/API、GPU、数值target或RUL。

后续收取必须以实际退出码、SUMMARY/COMPLETE和独立对账为准。Data Gate仍待全量重叠结果、身份、主target资格、终止/删失和split裁决。主计划已固定ESR为NA，RUL独立Gate；不把缺失ESR当作新增的主电容预测放行门槛。
