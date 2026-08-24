# AUDIT-Cap H0/H1 Final CPU Sanity Results

**Generated**: 2026-08-20 16:19 CST  
**Status**: reproducible implementation sanity complete; accuracy champion, Benchmark L, RUL, intervals, cross-condition claims, and Design Gate remain blocked  
**Claim class**: descriptive only; all Stress summaries retain `claim_prohibited=true`  
**Supersedes**: `EXPERIMENT_RESULTS_20260820_155512.md` for executable/artifact lineage only; the numerical tables are unchanged

## Final run inventory

| Run | Role | Size | Result |
|---|---|---:|---|
| `results/audit_cap/stress2_context4_final_20260820_161607` | primary context=4 sanity | 1,296 predictions/maturities | causal barrier PASS; 0 prediction/scoring failures |
| `results/audit_cap/stress2_context3_final_sensitivity_20260820_161607` | context=3 sensitivity | 1,512 predictions/maturities | barrier PASS; 144 rejected window=4 tuning evaluations disclosed |
| `results/audit_cap/stress2_context5_final_sensitivity_20260820_161607` | context=5 sensitivity | 1,080 predictions/maturities | barrier PASS; 0 prediction/scoring failures |
| `results/audit_cap/stress2_context4_final_repro_20260820_161607` | deterministic reproduction | 1,296 predictions/maturities | 11 stable artifacts byte-identical |
| `results/audit_cap/design_quick_final_20260820_161607` | design quick v2 | 15 cells / 3,000 repeats | 2,987 OK; 13 explicit missingness FAIL; Gate NOT_EVALUATED |
| `results/audit_cap/design_quick_final_repro_20260820_161607` | design reproduction | 15 cells / 3,000 repeats | all four sealed scientific artifacts byte-identical |

The earlier six run directories remain immutable audit history. They are not deleted or silently overwritten.

## Frozen lineage

- Stress protocol SHA256: `3b1b447172466fecdab63b4595124d53d3d9f2a0becf73886affb25334d873dc`.
- Design protocol SHA256: `316c67f74d746102c52577e09bd2645934c753f9d91ea413ca6697707d2ca623`.
- Final package code hash recorded in every new Stress prediction and both design seals: `6860ffbf1479e4b2e55ee492a186c1d5233607769d44f75ea3035650dc5b7542`; it matches the current package.
- Primary Stress manifest: `5f2b01c62c111ff12618fac0118d7e907678a3a3f7567ee5b2a99f0796b95989`.
- Primary Stress prediction ledger: `c2c7a7daf8dc0fd70ccc9ffa978d774e6973b7507f9a89ea8687706a6c42c36e`; seal: `88edd6118afdcffb4707b6a6d56acc80971eeeaa90178d3733e4f7cc41c26fc3`.
- Design manifest: `d43b766b3d39e6a4d36f8ecc13ee49d5ba65c8cf14c259e60feec800b78b6aec`.
- Design repeat ledger: `b3b2353f9253127b8be997dbe0d54a86ce37be80aa92f2e5a4597af5b0182609`; seal: `b1a44d6442adf01bc5ada1fa4ffabd2be7c9a27a405e445a9e99b49a8599e927`.
- Design cell summary remains numerically identical, SHA256 `c49e94d893c3c76885ae1dcc6df3c9fe4871a00329e5ae5cf563930cf21fcad1`; new lineage-bearing seal: `4da26b324b01a32f30f6c9be93e134a09a045ec5de103688417ef79c2c77c961`.

Every final manifest entry, prediction/repeat/cell hash chain, seal, and `COMPLETE` binding was recomputed successfully. The reproduction runs differ only in path/time-bearing run metadata where expected.

## Numerical results unchanged

The final context=4 `AGGREGATE_METRICS.csv` is byte-identical in values to the previously reported 36-row table. The canonical raw sources are now:

- `results/audit_cap/stress2_context4_final_20260820_161607/AGGREGATE_METRICS.csv`
- `results/audit_cap/stress2_context4_final_20260820_161607/UNIT_METRICS.csv`
- `results/audit_cap/stress2_context4_final_20260820_161607/PREDICTION_LEDGER.csv`
- `results/audit_cap/stress2_context4_final_20260820_161607/MATURITY_LEDGER.csv`

For orientation only, the observed context=4 Ridge macro MAE/skill values remain:

| Target | h | Macro MAE | Macro RMSE | Macro MASE | Skill vs last value |
|---|---:|---:|---:|---:|---:|
| capacity ratio | 1 | 0.007074 | 0.008958 | 0.336912 | 0.731710 |
| capacity ratio | 2 | 0.007976 | 0.009886 | 0.379453 | 0.854030 |
| capacity ratio | 3 | 0.008634 | 0.010210 | 0.412125 | 0.893783 |
| ESR ratio | 1 | 0.012582 | 0.015922 | 0.239754 | 0.679470 |
| ESR ratio | 2 | 0.017384 | 0.019553 | 0.331297 | 0.786325 |
| ESR ratio | 3 | 0.014161 | 0.016264 | 0.269925 | 0.890871 |

This ordering remains only a six-column harness observation. It is not a winner, significance, independent-device, or generalization claim. The complete raw 36-row table and all 15 design cells are also rendered in `EXPERIMENT_RESULTS_20260820_155512.md`; their values remain valid, while its older code/run hashes are superseded here.

## Design integrity remediation

Round-1 audit found that the original design artifact could reproduce but could not prove its historical code/protocol lineage or independently reconstruct per-repeat effects. Design schema v2 now:

- stores `incumbent_unit_losses_json` and `candidate_unit_losses_json` inside every sealed repeat row;
- records package code hash, frozen design-protocol hash, seed, repeats, schema, command, Python, dependencies, platform, and thread environment;
- uses the truthful seal status `SEALED_AFTER_SYNTHETIC_ANALYSIS_BEFORE_REPORTING`;
- writes a JSON `COMPLETE` marker binding the run manifest and both seals.

All 2,987 analyzable rows were independently recomputed from the archived raw unit losses: effect estimate, primary paired difference, one-sided p-value, confidence limits, and realized correlation had zero mismatches. The 13 failed rows retain explicit null-containing raw losses and remain in the planned denominator. Design v2 did not change any cell statistic.

## Reproducibility

- Final Stress context=4 reproduction: aggregate, unit, tuning, prediction, maturity, checkpoint, reveal, failure, canonical-event, endpoint, and seal artifacts are byte-identical. Summary/manifest/COMPLETE differ only because they record their own path/time.
- Final design reproduction: repeat ledger/seal and cell ledger/seal are byte-identical. Summary/manifest/COMPLETE differ because the command/output path and completion time are intentionally recorded.
- Current full suite: 31 tests passed.
- The full round-1 integrity-review request/response is preserved at `.aris/traces/experiment-audit/2026-08-20_run01/`; positive semantic judgments remain same-family and provisional.

## Permanent evidence limits

1. Stress-2 has six column-surrogate trajectories, not six proven independent physical capacitors; duplicate relationships are unknown.
2. The rolling barrier is durable, hash-bound same-process software evidence. It is not an external trusted timestamp, separate security domain, signed service, or WORM proof against a malicious executor.
3. Stress-2 termination reason is unknown; RUL and survival scores remain NA. Prediction intervals remain NA because independent calibration units are insufficient.
4. Benchmark L has no proven physical IDs/duplicates/termination or direct ESR field, and its EIS target/time mapping is not frozen. It remains blocked.
5. The quick design has only 200 repeats/cell and cannot pass the formal Design Gate. Small-N and K=5 power diagnostics explicitly favor `NO_CHAMPION`.
6. No multi-agent topology, feature, Skill, LLM-generated code path, or dynamic router has earned numerical promotion.

## Supported and unsupported claims

Supported:

- Public-file byte integrity for the recorded local downloads and deterministic execution of the parser/replay/design harness.
- Real observed capacity/ESR trajectory scoring under surrogate-column nested LOCO, with raw ledgers and same-process causal ordering.
- Reproducible quick-simulation diagnostics with archived raw losses and explicit failures.

Unsupported:

- Any model superiority or best-accuracy claim.
- Any physical-device-independent, cross-condition, RUL, calibrated-interval, deployment, or formal Design Gate claim.
- Any claim that the large pack passed the target/identity/outcome gates.

## Next allowed work

At the human checkpoint, the evidence-backed next slice is the large-pack reference-aware parser and target-definition Freeze B: resolve event/replicate linkage, acquisition-time ordering, 20-token-to-18-column mapping, frequency/fit rule, ES12 off-by-four alignment, physical identity/duplicates, and outcome semantics. Until those gates pass, do not run Benchmark L models or call an external LLM to choose a champion.

No Volcengine Ark or other external model service was used in these numerical runs.
