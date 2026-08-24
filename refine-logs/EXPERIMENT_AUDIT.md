# Experiment Audit Report — Final H0/H1

**Date**: 2026-08-20 17:04:17 +0800  
**Auditor**: fresh GPT-5.6-Sol ultra agent, with two independent sub-audits  
**Review independence**: same-family  
**Acceptance status**: provisional  
**Overall verdict**: WARN  
**Numerical and hash integrity**: PASS

No fabricated ground truth, prediction-derived score normalization, phantom result, hidden prediction/scoring failure, or numerical mismatch was found. `WARN` reflects evidence and evaluation-scope limits, not corrupted results.

## A–F checks

- **A. Ground-truth provenance — WARN.** Stress-2 capacity and ESR targets are direct deterministic transforms of the verified MAT observations. The six columns are only column-surrogate units; the archive does not prove six independent physical devices or their duplicate relationships. Design truth is explicitly synthetic.
- **B. Score normalization — PASS.** Stress MAE/RMSE are raw, MASE uses outer-training first differences, and relative skill uses the separately executed last-value baseline. Design effects use the prespecified incumbent comparator and retain raw unit losses.
- **C. Result existence and numeric match — PASS.** Every final2 manifest entry, byte count, SHA-256, `COMPLETE` binding, CSV/JSONL hash chain, and visible-field-to-hashed-payload relation verified.
- **D. Dead code — WARN, non-claiming only.** All claimed metric and decision paths execute. Unused helpers do not affect results.
- **E. Scope — WARN.** Stress is one 11×6-column dataset, two targets, three horizons and contexts, six deterministic model families, one seed, and a deterministic reproduction. Design is 15×200 quick simulation, not the frozen formal Gate requiring at least 2,000 repeats per cell and 10,000 for required anchors.
- **F. Evaluation classification — PASS.** Stress is `real_gt` with surrogate-group qualification; design is `simulation_only`.

## Independent reconstruction

- Stress context 3/4/5 contains 1,512 / 1,296 / 1,080 prediction and maturity rows, with zero prediction/scoring failures. Context 3 has 144 explicit, unselected Ridge/window=4 inner-tuning failures. Every unit and aggregate metric was recomputed; maximum serialization-level discrepancy was approximately `4e-15`.
- All 3,000 design repeats were reconstructed: 2,987 analyzable and 13 explicit QT2 missingness failures. Regenerated raw losses, seeds, effects, paired tests, confidence intervals, Holm/runner-up decisions, correlations, cell rates, and Clopper–Pearson intervals had zero mismatches.
- The truth-blind boundary is enforced: model selection cannot receive `true_effect`; synthetic truth enters only data generation and post-decision diagnostic scoring.
- The current 32-test suite passes. Fresh reruns reproduced all 11 Stress stable artifacts and all four design sealed scientific artifacts byte-for-byte.

## Final2 lineage

- Code: `36f8a0af273cfbe606f08383a6ea8594d6bf93d5f96d7f6094d60e3e7f240e90`
- Stress protocol: `3b1b447172466fecdab63b4595124d53d3d9f2a0becf73886affb25334d873dc`
- Design protocol: `316c67f74d746102c52577e09bd2645934c753f9d91ea413ca6697707d2ca623`
- Stress primary manifest / prediction ledger / seal: `630529883af0c5ee5751df5aca7567834cf329a4e94eda996e69012a631cf459` / `d18599d0068074d784a89ce9aa16e5fcc2a4adc191dfe4dfbf30358d96f2984a` / `867470e36ccbfea8811e8c357b79336879419ccd94d134c908a3e74c9789dc28`
- Design primary manifest: `70de02aa9afaf670ac5d17fe31b827d5c556091b002e038e6bdd526877aef21a`
- Design repeat ledger / seal: `b3b2353f9253127b8be997dbe0d54a86ce37be80aa92f2e5a4597af5b0182609` / `d20a90445693717a668c2ce5aacadf47c058d6c7a77ccae17cddda130d0504d4`
- Design cell ledger / seal: `c49e94d893c3c76885ae1dcc6df3c9fe4871a00329e5ae5cf563930cf21fcad1` / `f5d48e9b49c775d7482fb9325ffb00ee546fbb9185bde71eb9369237356b325d`

## Round-1 remediation

- `DESIGN_CODE_PROTOCOL_LINEAGE_MISSING` — RESOLVED
- `DESIGN_RAW_UNIT_LOSSES_NOT_ARCHIVED` — RESOLVED
- `MISLEADING_DESIGN_SEAL_STATUS` — RESOLVED
- `REVIEW_INDEPENDENCE_UNEVIDENCED` — RESOLVED as a full trace; review remains same-family and provisional
- `LOCAL_SOURCE_PROVENANCE_ONLY` — RESOLVED for independent byte-source corroboration; no signed upstream checksum exists
- `UNVERIFIED_PHYSICAL_UNIT_IDENTITY` — UNRESOLVED, permanent for Stress-2
- `CAUSAL_BARRIER_SELF_ATTESTED` — UNRESOLVED, permanent: same-process software evidence is not an external/WORM timestamp

One contained implementation warning remains: `N<12` design selection is flagged rather than hard-blocked inside the low-level decision function. Every present quick output is nevertheless hard-gated `NOT_ELIGIBLE_QUICK_SANITY`; downstream consumers must honor eligibility.

## Claim impact

Supported: deterministic parser/replay/simulation operation, raw Stress-2 descriptive metrics, explicit failure accounting, internal hash chains, deterministic reproduction, and simulation-only quick-design diagnostics.

Unsupported: model superiority, independent-device LOCO, RUL accuracy, calibrated intervals, cross-condition robustness, deployment readiness, formal Design Gate, Benchmark L, or multi-agent advantage.

The unabridged auditor response and request are preserved under `.aris/traces/experiment-audit/2026-08-20_run01/`.
