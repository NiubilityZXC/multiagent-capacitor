# N0+ 专用模型执行追踪器草案

**时间**：2026-09-04 13:46:14 +08:00
**状态**：`DRAFT_ONLY / ALL_RUNS_BLOCKED`
**计划**：`refine-logs/SPECIALIZED_MODEL_N0_PLUS_PRESEAL_DRAFT.md`

| Run ID | Milestone | Purpose | System / Variant | Scope | Metric / Artifact | Priority | Status | Next Gate / Stop |
|---|---|---|---|---|---|---|---|---|
| N0P-SN0-001 | SN0 | approve draft scope | N0+ finite policy | human gate | exact approval token | MUST | BLOCKED_HUMAN_GATE | `APPROVE_N0_PLUS_POLICY` |
| N0P-SN0-002 | SN0 | candidate registry | Tier A/B/C typed manifests | offline | IDs、roles、NA/failure/tie rules | MUST | BLOCKED_SN0-001 | no model fit |
| N0P-SN0-003 | SN0 | environment seal | package/source/version lock | offline | lockfile、binary/artifact hashes | MUST | BLOCKED_SN0-001 | no dependency install before approval |
| N0P-SN1-001 | SN1 | classical causal fixtures | ETS/ARIMA/Theta | synthetic prefix | suffix invariance、determinism、failure | MUST | BLOCKED_SN0 | code review PASS |
| N0P-SN1-002 | SN1 | online SSM fixtures | RLS/RELS/PF | synthetic prefix | state update、quantiles、seed、degeneracy | MUST | BLOCKED_SN0 | code review PASS |
| N0P-SN1-003 | SN1 | small-ML fixtures | Elastic Net/HGB | synthetic units | fold-local scaler/features/tuning | MUST | BLOCKED_SN0 | leakage tests PASS |
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

当前表中没有 `RUNNING` 或 `COMPLETE` 的真实模型任务；它不能被引用为实验结果。
