# Experiment Tracker: Hybrid-Agent Capacitor Forecasting v0.3

**Updated**：2026-08-24 12:20:33 +0800  
**Policy**：真实精度只由严格 rolling 数值 Eval 裁决；Stress-2 仅 sanity；Benchmark-L target gate 前不运行预测；`AUTO_PROCEED=false`。  
**Legacy**：AUDIT-Cap v0.2 完整运行历史保存在 `EXPERIMENT_TRACKER_20260820_171423.md`。

| Run ID | Milestone | Purpose | System / Variant | Scope | Metric / Artifact | Status | Next Gate |
|---|---|---|---|---|---|---|---|
| H000 | M0 | causal request/decision schema | strict JSON v1 | synthetic | taint/origin/weights/types | COMPLETE | — |
| H001 | M0 | topology core | single/fixed/parallel/dynamic | synthetic | call count, convex hull, fallback | COMPLETE | — |
| H002 | M0 | AgentPlan client preview | ArkCLI + Kimi-K3 logical ID | synthetic dry-run | network=blocked, stateless plan lane | COMPLETE_DRY_RUN | H010 |
| H003 | M0 | regression suite | P1 + Stress-2 + design + hybrid | local | 64 pytest | COMPLETE | — |
| H004 | M0 | hybrid protocol/plan | v0.3-draft | docs | human checkpoint | COMPLETE_DRAFT | approval |
| P100 | P1 | reference-aware parser | Benchmark-L Data Gate generator | synthetic HDF5 | 11 tests | COMPLETE_CODE_ONLY | optional real P1 |
| P101 | P1 | independent verifier | manifests/golden/downstream locks | synthetic HDF5 | 19 focused; 51 pre-hybrid full | COMPLETE_CODE_ONLY | optional real P1 |
| H010 | M1 | one-call capability smoke | Kimi-K3 strict schema | synthetic | model/version, usage, latency, fallback | BLOCKED_HUMAN_GATE | secure env |
| H011 | M1 | accessible model snapshot | AgentPlan resources | account | exact callable IDs | BLOCKED_AUTH | secure auth/env |
| H020 | M2 | numeric controls | C0/C1/C2 | six frozen Stress-2 origins | raw MAE + system ledger | TODO_AFTER_H010 | shadow protocol |
| H021 | M2 | direct LLM control | A1 single direct | same six origins | raw point error only | TODO_AFTER_H010 | direct schema |
| H022 | M2 | hybrid main | A2 single Agent + experts | same six origins | raw error, weights, fallback | TODO_AFTER_H010 | scorer pass |
| H023 | M2 | fixed hierarchy | A3 | Stress-2 sanity | error/cost/latency | BLOCKED_STAGE_GATE | A2 > A1/C2 |
| H024 | M2 | parallel debate | A4 | Stress-2 sanity | error/cost/latency | BLOCKED_STAGE_GATE | A3 > A2 |
| H025 | M2 | dynamic route | A5 | Stress-2 sanity | error/calls/Pareto | BLOCKED_STAGE_GATE | static multi-agent useful |
| H030 | M3 | full Stress-2 shadow | C0/C1/C2/A1/A2 only first | all causal origins | descriptive metrics | BLOCKED_H020 | no champion |
| H040 | M4 | formal capacity comparison | C0/C1/C2/A1/A2 | Benchmark-L physical LOCO | Freeze-B primary | BLOCKED_DATA_GATE | G00–G07/G10 + Design |
| H041 | M4 | formal ESR/SOH comparison | same | Benchmark-L | Freeze-B primary | BLOCKED_DATA_GATE | G08 + Design |
| H042 | M4 | RUL | none | Benchmark-L | interval-censored score | BLOCKED | G09 + Design + Freeze B |
| H050 | M5 | formal topology tournament | A3→A4→A5 staged | Benchmark-L | paired unit loss + cost | BLOCKED_H1 | H1 supported |

## Current checkpoint

- P1 generator/verifier code is complete and tested; the real 5.04 GB P1 run was intentionally not launched after the research priority changed.
- Hybrid no-network core and ArkCLI client preview are complete; no real API request or token usage occurred.
- H010/H020 require a new explicit approval and a rotated API key supplied through `ARK_API_KEY`/`ARK_BASE_URL` environment variables.
- Other AgentPlan models remain `BLOCKED_UNAVAILABLE` until a callable resource snapshot is obtained.

