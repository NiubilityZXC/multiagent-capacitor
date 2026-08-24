# Experiment Tracker: AUDIT-Cap v0.2

**Updated**：2026-08-20 17:07:00 +0800  
**Execution policy**：按物理器件、严格因果回放；Data/Design Gate 未通过的结果族保持 BLOCKED 或 NA。

| Run ID | Milestone | Purpose | System / Variant | Split | Metrics / Artifact | Priority | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| R000 | M0 | 官方大包下载与字节核验 | resumable raw download | N/A | bytes, headers, SHA-256 | MUST | COMPLETE | 5,038,942,729 B；ZIP SHA-256 `2e998398…ad98`；来源见 SOURCE_PROVENANCE latest |
| R001 | M0 | ZIP 完整性 | ZIP CRC | N/A | unzip -t, member manifest | MUST | COMPLETE | 4 members；全成员 CRC 通过；总解压 5,167,611,427 B |
| R002 | M0 | MAT 完整性与容器识别 | ES10/12/14 | N/A | streamed/extracted SHA-256, HDF5 open | MUST | COMPLETE | 三个提取 MAT 与 ZIP 内解压字节流 SHA-256 精确一致；HDF5 均可读 |
| R003 | M0 | HDF5 schema 与数值审计 | recursive inventory + bounded scan | N/A | 24,018 objects；23,932 dataset rows | MUST | COMPLETE_SCOPE | 20,353 datasets 完整数值扫描；3,579 reference dtype 按规则跳过；范围见两个 audit report |
| R004 | M0 | 物理器件/事件/终止审计 | canonical provisional ledgers | duplicate/identity unresolved | UNIT/MODALITY/TERMINATION/DUPLICATE ledgers | MUST | BLOCKED | 24 provisional EIS labels、23 transient；identity/termination/duplicate group 未证；Data Gate=partial_integrity_only |
| R010 | M1 | Stress-2 parser/标签 sanity | deterministic canonicalizer | six column-surrogates | 6×11；5 C intervals；0 ESR events | MUST | COMPLETE_SANITY_ONLY | verified raw hashes；canonical events/endpoints 已写入三组正式回放；物理身份仍未证 |
| R011 | M1 | 因果 rolling replay | context 4, h=1/2/3 | 6-fold surrogate-LOCO | prediction/checkpoint/reveal/maturity ledgers | MUST | COMPLETE_SANITY_ONLY | context=4 计 1,296 prediction/maturity；42 checkpoints、66 reveals；barrier PASS；0 prediction/scoring failure |
| R012 | M1 | 泄漏与时序哨兵 | failure/lineage/reveal controls | group-disjoint surrogate | invariant and fault-injection tests | MUST | COMPLETE_TEST_SCOPE | 32 tests PASS；selector/state/predict/maturity、suffix、lineage、重链篡改、truth-blind decision 均覆盖；不等于数值精度证据 |
| R013 | M1 | 上下文敏感性与复现 | context 3/4/5 + duplicate run | surrogate-LOCO rolling | byte hashes, unit-macro metrics | MUST | COMPLETE_SANITY_ONLY | final2 code `36f8a0af…240e90`；c3/c4/c5=1,512/1,296/1,080 predictions；c3 显式拒绝 144 个 window=4 调参评估；同代码 c4 的 11 个稳定工件逐字节一致 |
| R020 | M2 | 快速设计仿真 | v2 truth-blind；200 repeats × 15 cells | physical-unit simulation | raw-loss lineage + implementation diagnostics | MUST | COMPLETE_NOT_EVALUATED | 3,000 planned；2,987 OK、13 explicit missingness FAIL；全部可分析行由 raw unit losses 零误差重建；四个封存科学工件复跑逐字节一致；Design Gate 固定 NOT_EVALUATED |
| R021 | M2 | 正式设计仿真 | ≥2,000 repeats/grid | physical-unit simulation | power/coverage/champion diagnostics | MUST | BLOCKED | 参数须由可建模数据结构与 Freeze B 冻结；当前不执行 |
| R022 | M2 | 最终实验完整性审计 | fresh same-family + two sub-audits | all final2 artifacts | A–F, recomputation, hashes, claim ceiling | MUST | COMPLETE_WARN | numerical/hash integrity PASS；overall WARN；identity、同进程因果自证、quick-only scope 为永久限制；见 `EXPERIMENT_AUDIT.md` |
| R030 | M3 | 锚点基线 | last-value | nested surrogate-LOCO rolling | unit-macro metrics | MUST | COMPLETE_SANITY_ONLY | 原始 MAE/RMSE/MASE 已落账；只可作 Benchmark S harness 描述 |
| R031 | M3 | 长历史漂移 | held-unit prefix drift | nested surrogate-LOCO rolling | unit-macro metrics | MUST | COMPLETE_SANITY_ONLY | event-index；未使用未来真实时刻；不作优越性声明 |
| R032 | M3 | 局部线性 | k∈{2,3,4} | inner-LOCO select | unit-macro metrics | MUST | COMPLETE_SANITY_ONLY | common-origin keys；配置选择仅用 outer-train inner folds |
| R033 | M3 | 指数趋势 | log-linear | inner-LOCO select | unit-macro metrics | MUST | COMPLETE_SANITY_ONLY | 正值 ratio；预注册方向约束候选已回放 |
| R034 | M3 | 状态空间 | causal local-trend KF | inner-LOCO select | unit-macro metrics | MUST | COMPLETE_SANITY_ONLY | filter only；禁止 RTS；全局参数不在 held-out 后缀重估 |
| R035 | M3 | 传统 ML | ridge causal increment | inner-LOCO select | unit-macro metrics | MUST | COMPLETE_SANITY_ONLY | observed MAE 最低仅为 6 列 harness 观察；冠军/泛化/精度优势均禁止 |
| R040 | M4 | 大包 C/ESR 锚点 | last-value | within-condition LOCO | frozen primary + secondary | MUST-COND | BLOCKED | C/Cp/Cs 与 ESR 派生规则、身份/重复、ES12 对齐、Freeze B 未通过 |
| R041 | M4 | 大包趋势基线 | best simple trend | within-condition LOCO | frozen primary + secondary | MUST-COND | BLOCKED | 外层结果不得调参 |
| R042 | M4 | 大包状态空间 | selected KF | within-condition LOCO | frozen primary + secondary | MUST-COND | BLOCKED | 测试期仅状态更新 |
| R043 | M4 | 大包 ridge | causal ridge | within-condition LOCO | frozen primary + secondary | MUST-COND | BLOCKED | 等待 sample/design gate |
| R050+ | M5 | 条件测量桥/Agent 扩展 | frozen challenger | separate estimand | shadow evaluation | NICE | BLOCKED | 需要新的人工检查点；当前未调用外部模型 API |

## 当前 Gate 摘要

- 大包字节、容器和限定数值扫描已完成；这不证明物理语义或独立器件身份。
- 所有 23×2 个瞬态 VL/VO 数组都含 NaN；ES12 Serial_Date 比信号多 4 行，禁止静默截断。
- 大包没有可证的 termination/censor/SOH/RUL 字段，Benchmark L 与 RUL 保持 RED/BLOCKED。
- Fresh final code review 已放行 Stress-2/quick sanity；final2 持久运行、敏感性、确定性复跑和独立逐行重建均完成；最终 lineage 与 claim ceiling 见 `EXPERIMENT_RESULTS_20260820_165023.md`。
- Stress-2 的六列不是已证独立物理器件，RUL/区间为 NA；任何 observed model ordering 均不得升级为主方法精度主张。
- Quick design 固定为 `NOT_EVALUATED_QUICK_SANITY`；当前小 N/K=5 功效诊断不支持冠军裁决。
- 最终审计为 overall `WARN`、numerical/hash integrity `PASS`；Benchmark L、正式 Design Gate、RUL 和 Agent 拓扑比较仍停在人工检查点。
