# Experiment Tracker: AUDIT-Cap v0.2

**Updated**：2026-08-20 15:36:23 +0800  
**Execution policy**：按物理器件、严格因果回放；Data/Design Gate 未通过的结果族保持 BLOCKED 或 NA。

| Run ID | Milestone | Purpose | System / Variant | Split | Metrics / Artifact | Priority | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| R000 | M0 | 官方大包下载与字节核验 | resumable raw download | N/A | bytes, headers, SHA-256 | MUST | COMPLETE | 5,038,942,729 B；ZIP SHA-256 `2e998398…ad98`；来源见 SOURCE_PROVENANCE latest |
| R001 | M0 | ZIP 完整性 | ZIP CRC | N/A | unzip -t, member manifest | MUST | COMPLETE | 4 members；全成员 CRC 通过；总解压 5,167,611,427 B |
| R002 | M0 | MAT 完整性与容器识别 | ES10/12/14 | N/A | streamed/extracted SHA-256, HDF5 open | MUST | COMPLETE | 三个提取 MAT 与 ZIP 内解压字节流 SHA-256 精确一致；HDF5 均可读 |
| R003 | M0 | HDF5 schema 与数值审计 | recursive inventory + bounded scan | N/A | 24,018 objects；23,932 dataset rows | MUST | COMPLETE_SCOPE | 20,353 datasets 完整数值扫描；3,579 reference dtype 按规则跳过；范围见两个 audit report |
| R004 | M0 | 物理器件/事件/终止审计 | canonical provisional ledgers | duplicate/identity unresolved | UNIT/MODALITY/TERMINATION/DUPLICATE ledgers | MUST | BLOCKED | 24 provisional EIS labels、23 transient；identity/termination/duplicate group 未证；Data Gate=partial_integrity_only |
| R010 | M1 | Stress-2 parser/标签 sanity | deterministic canonicalizer | six column-surrogates | 6×11；5 C intervals；0 ESR events | MUST | TEST_PASS_RUN_PENDING | parser 与标签测试通过；等待最终独立代码放行后执行持久 run |
| R011 | M1 | 因果 rolling replay | context 4, h=1/2/3 | 6-fold surrogate-LOCO | prediction/checkpoint/reveal/maturity ledgers | MUST | TEST_PASS_RUN_PENDING | per-origin fsync/hash checkpoint barrier 已实现；等待 fresh final review |
| R012 | M1 | 泄漏与时序哨兵 | failure/lineage/reveal controls | group-disjoint surrogate | invariant and fault-injection tests | MUST | TEST_PASS | selector/state/predict/maturity failure、suffix invariance、train-set commitment、tamper/reveal barrier 已覆盖；不等于数值结果 |
| R020 | M2 | 快速设计仿真 | 200 repeats × 15 cells | physical-unit simulation | implementation/error diagnostics | MUST | READY_NOT_RUN | 静态/定向测试通过；无论结果如何均 NOT_EVALUATED_QUICK_SANITY |
| R021 | M2 | 正式设计仿真 | ≥2,000 repeats/grid | physical-unit simulation | power/coverage/champion diagnostics | MUST | BLOCKED | 参数须由可建模数据结构与 Freeze B 冻结；当前不执行 |
| R030 | M3 | 锚点基线 | last-value | nested surrogate-LOCO rolling | unit-macro metrics | MUST | READY_NOT_RUN | 只可作为 Benchmark S harness 描述性结果 |
| R031 | M3 | 长历史漂移 | held-unit prefix drift | nested surrogate-LOCO rolling | unit-macro metrics | MUST | READY_NOT_RUN | event-index；禁用未来真实时刻 |
| R032 | M3 | 局部线性 | k∈{2,3,4} | inner-LOCO select | unit-macro metrics | MUST | READY_NOT_RUN | common-origin keys |
| R033 | M3 | 指数趋势 | log-linear | inner-LOCO select | unit-macro metrics | MUST | READY_NOT_RUN | 正值 ratio；方向约束为预注册候选 |
| R034 | M3 | 状态空间 | causal local-trend KF | inner-LOCO select | unit-macro metrics | MUST | READY_NOT_RUN | filter only；禁止 RTS |
| R035 | M3 | 传统 ML | ridge causal increment | inner-LOCO select | unit-macro metrics | MUST | READY_NOT_RUN | Benchmark S 仅 harness；不可据 6 列宣称优越 |
| R040 | M4 | 大包 C/ESR 锚点 | last-value | within-condition LOCO | frozen primary + secondary | MUST-COND | BLOCKED | C/Cp/Cs 与 ESR 派生规则、身份/重复、ES12 对齐、Freeze B 未通过 |
| R041 | M4 | 大包趋势基线 | best simple trend | within-condition LOCO | frozen primary + secondary | MUST-COND | BLOCKED | 外层结果不得调参 |
| R042 | M4 | 大包状态空间 | selected KF | within-condition LOCO | frozen primary + secondary | MUST-COND | BLOCKED | 测试期仅状态更新 |
| R043 | M4 | 大包 ridge | causal ridge | within-condition LOCO | frozen primary + secondary | MUST-COND | BLOCKED | 等待 sample/design gate |
| R050+ | M5 | 条件测量桥/Agent 扩展 | frozen challenger | separate estimand | shadow evaluation | NICE | BLOCKED | 需要新的人工检查点；当前未调用外部模型 API |

## 当前 Gate 摘要

- 大包字节、容器和限定数值扫描已完成；这不证明物理语义或独立器件身份。
- 所有 23×2 个瞬态 VL/VO 数组都含 NaN；ES12 Serial_Date 比信号多 4 行，禁止静默截断。
- 大包没有可证的 termination/censor/SOH/RUL 字段，Benchmark L 与 RUL 保持 RED/BLOCKED。
- Stress-2 正式 sanity 与 quick design 仅在 fresh final code review 明确放行后运行；任何输出均不得升级为主方法精度主张。
