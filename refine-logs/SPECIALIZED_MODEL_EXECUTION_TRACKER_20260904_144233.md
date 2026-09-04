# N0+ 专用模型执行追踪器

**时间**：2026-09-04 14:42:33 +08:00
**状态**：`SN1_SYNTHETIC_CONTRACT_COMPLETE / REAL_MODEL_RUNS_BLOCKED`
**计划**：`refine-logs/SPECIALIZED_MODEL_N0_PLUS_PRESEAL_DRAFT_20260904_134614.md`
**批准记录**：`refine-logs/N0_PLUS_APPROVAL_RECORD_20260904_141528.json`

| Run ID | Milestone | Purpose | System / Variant | Scope | Metric / Artifact | Priority | Status | Next Gate / Stop |
|---|---|---|---|---|---|---|---|---|
| N0P-SN0-001 | SN0 | approve draft scope | N0+ finite policy | human gate | approval record bound to proposal hash | MUST | COMPLETE | SN0 only |
| N0P-SN0-002 | SN0 | candidate registry | Tier A/B/C typed manifests | offline | 15 specs、10 selectable、Tier-C/RUL exclusion、registry hash | MUST | COMPLETE_VERIFIED | no model fit |
| N0P-SN0-003 | SN0 | environment seal | isolated Python 3.12 Tier-A lock | offline | exact versions、pip check、required imports | MUST | COMPLETE_VERIFIED | no Tier-B install before GPU gate |
| N0P-SN1-001 | SN1 | classical causal fixtures | ETS/ARIMA/Theta | held-out synthetic prefix | suffix invariance、determinism、one-attempt failure | MUST | COMPLETE_VERIFIED_SYNTHETIC | no accuracy/calibration claim |
| N0P-SN1-002 | SN1 | online SSM fixtures | RLS/RELS/PF | held-out synthetic prefix | PF alignment、state identity、quantile shape、seed | MUST | COMPLETE_VERIFIED_SYNTHETIC | no P2 reuse without replacement gates |
| N0P-SN1-003 | SN1 | small-ML fixtures | Elastic Net/HGB | disjoint synthetic units | prefix-only features、order invariance、immutable state | MUST | COMPLETE_VERIFIED_SYNTHETIC | residual intervals are not calibrated |
| N0P-SN1-004 | SN1 | modern fixtures | DLinear/N-HiTS | synthetic units | budget、3 seeds、same-input parity | MUST-COMPUTE | BLOCKED_GPU_GATE | separate compute approval |
| N0P-SN2-001 | SN2 | eligible primary data | Ren | audited raw rows | identity/target/chronology/split | MUST | BLOCKED_P1 | fail stops real prediction |
| N0P-SN2-002 | SN2 | Eval freeze | all eligible families | outer-train only | keys、metrics、margins、power、seeds | MUST | BLOCKED_SN2-001 | preseal review PASS |
| N0P-SN2-003 | SN2 | new generation seal | N0+ + Agent registry | no predictions | plan/code/data/env hashes | MUST | BLOCKED_SN2-002 | joint seal before score |
| N0P-SN3-001 | SN3/SB2 | Tier-A real replay | legacy/classical/SSM/small-ML | Ren sealed folds | MASE/WIS/coverage/failure/CPU | MUST | BLOCKED_SN2-003 | one joint unseal only |
| N0P-SN3-002 | SN3/SB4 | policy isolation | N0-v1/fixed-family/N0+/equal ensemble | same keys | paired unit effects、harm gates | MUST | BLOCKED_SN3-001 | no winner promotion |
| N0P-SN4-001 | SN4/SB3 | modern necessity | DLinear/N-HiTS | same sealed folds | same numeric/operational metrics | MUST-COMPUTE | BLOCKED_GPU_GATE | ≤2 GPU-hours each |
| N0P-SN4-002 | SN4 | TSFM stress | Chronos/TimesFM/Moirai | same sealed keys | zero-shot quality/coverage/runtime | OPTIONAL-SEPARATE | BLOCKED_ADDENDUM | not in N0+ champion |
| N0P-SN4-003 | SN4 | task-specific RUL | S4+RevIN/physics model | eligible endpoint only | RUL error/calibration/censoring | CONDITIONAL | BLOCKED_RUL_GATE | endpoint addendum required |
| N0P-SN5-001 | SN5/SB5 | external boundary | frozen N0-v1/N0+ | Patrizi separate LOCO | per-unit effect/uncertainty/failure | MUST-JOURNAL | BLOCKED_P1_EXTERNAL | never pool with Ren |
| N0P-SN5-002 | SN5 | integrity and claim audit | all completed runs | sealed artifacts | hashes、key parity、statistics、claims | MUST | BLOCKED_RESULTS | fail means no performance claim |

本追踪器的 SN1 `COMPLETE_VERIFIED_SYNTHETIC` 只表示 7 个 CPU 原型通过 44 项定向合成契约测试、5 项 manifest 测试、366 项项目回归和一次 fresh same-family provisional 二审。没有真实数据、accuracy/calibration score、RUL、GPU 或 API 运行；P2 仍需新的预封存和人工批准。
