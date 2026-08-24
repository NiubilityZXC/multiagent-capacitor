# Final integrity audit

**Overall verdict: WARN**  
**Numerical/hash integrity: PASS**  
**review_independence: same-family · acceptance_status: provisional**

No fabricated GT, self-normalization, phantom result, hidden prediction failure, or numeric mismatch was found. WARN reflects evidence limits, not corrupted results.

## A–F

- **A. Ground-truth provenance — WARN.** Stress targets are direct transforms of the verified MAT arrays (`C`, `ESR`): [stress2.py](/home/user/multiagent-capacitor/experiments/audit_cap/stress2.py:84), with ZIP/MAT hashes `944cd228…accacfb` / `9db651a1…00cb4a3`. A fresh stream from the NASA legacy URL matched the ZIP hash, and the [NASA repository](https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/) identifies Stress-2 as 10-V capacitor data. However, six columns are not proven to be six independent devices. Design truth is explicitly synthetic.
- **B. Normalization — PASS.** Stress MAE/RMSE are raw; MASE uses outer-training first differences and skill uses the separately executed last-value baseline ([replay.py](/home/user/multiagent-capacitor/experiments/audit_cap/replay.py:1153)). Design effects use the prespecified incumbent comparator. All raw design losses are archived.
- **C. Result existence/numeric match — PASS.** Every manifest entry, byte count, SHA, `COMPLETE` binding, CSV/JSONL chain, and visible-field-to-hashed-payload relation verified.
- **D. Dead code — WARN (non-claiming only).** All claimed metric/decision paths execute. Unused helpers include design `_write_csv` and Stress `revealed_index`; neither affects results.
- **E. Scope — WARN.** Stress is one 11×6-column dataset, two targets, three horizons/contexts, six deterministic families, one seed and one reproduction. Design is only 15×200 quick simulation—not the ≥2,000/10,000-repeat formal Gate.
- **F. Classification — PASS.** Stress: `real_gt` with surrogate-group qualification. Design: `simulation_only`.

## Independent quantitative checks

Stress context 3/4/5 contained respectively **1,512/1,296/1,080** predictions and maturities, with zero prediction/scoring failures. Context 3’s **144 Ridge/window=4 tuning failures** were explicit, unselected, and disclosed. Every unit/aggregate metric was recomputed; maximum serialization-level difference was approximately `4e-15`.

Design reconstruction covered all 3,000 repeats: **2,987 analyzable; 13 explicit QT2 failures** (7 null, 6 at 10%). Regenerated losses, seeds, effects, t statistics, one-sided p-values, two-sided CIs, Holm/runner-up decisions, correlations, cell rates and Clopper–Pearson intervals had **zero mismatches**.

`decide_losses` cannot receive `true_effect` ([design_simulation.py](/home/user/multiagent-capacitor/experiments/audit_cap/design_simulation.py:188)); truth enters only generator creation and post-decision scoring at lines 251–323. One WARN remains: `N<12` selection is flagged, not hard-blocked, although every present output is gated `NOT_ELIGIBLE_QUICK_SANITY`.

Current tests: **32 passed** via `python -m pytest`. Fresh reruns reproduced all **11 Stress stable artifacts** and **4 design sealed scientific artifacts** byte-for-byte. Scientific outputs also matched the 15:50 and 16:16 generations.

## Final2 lineage

- Code: `36f8a0af…240e90`; Stress protocol: `3b1b4471…d873dc`; design protocol: `316c67f7…ca623`.
- Stress primary [directory](/home/user/multiagent-capacitor/results/audit_cap/stress2_context4_final2_20260820_164848): manifest `63052988…cf459`, ledger `d18599d0…2984a`, seal `867470e3…dc28`.
- Other Stress manifests: context-3 `eac6e761…d0ad`; context-5 `e415b070…3b32`; reproduction `cf6617f6…5f02`.
- Design primary [directory](/home/user/multiagent-capacitor/results/audit_cap/design_quick_final2_20260820_164848): manifest `70de02aa…e21a`, repeat ledger/seal `b3b2353f…82609` / `d20a9044…04d4`, cell ledger/seal `c49e94d8…fcad1` / `f5d48e9b…325d`.
- Design reproduction manifest: `e8b7a1af…4540`.

## Round-1 reason codes

- `UNVERIFIED_PHYSICAL_UNIT_IDENTITY` — **UNRESOLVED, permanent**
- `CAUSAL_BARRIER_SELF_ATTESTED` — **UNRESOLVED, permanent**
- `DESIGN_CODE_PROTOCOL_LINEAGE_MISSING` — **RESOLVED**
- `DESIGN_RAW_UNIT_LOSSES_NOT_ARCHIVED` — **RESOLVED**
- `MISLEADING_DESIGN_SEAL_STATUS` — **RESOLVED**
- `REVIEW_INDEPENDENCE_UNEVIDENCED` — **RESOLVED as traced**, but review remains same-family/provisional
- `LOCAL_SOURCE_PROVENANCE_ONLY` — **RESOLVED for byte-source corroboration**; no signed upstream checksum exists

Supported: deterministic parser/replay/simulation operation, raw Stress metrics, disclosed failures, internal chains, reproducibility, and simulation-only design diagnostics.

Unsupported: model superiority; independent-device LOCO; RUL, calibrated intervals, cross-condition robustness, deployment or formal Design Gate; Benchmark-L or multi-agent advantage.

```json
{
  "overall": "WARN",
  "numerical_integrity": "PASS",
  "checks": {"A":"WARN","B":"PASS","C":"PASS","D":"WARN","E":"WARN","F":"PASS"},
  "evaluation_types": ["real_gt_qualified", "simulation_only"],
  "review_independence": "same-family",
  "acceptance_status": "provisional",
  "permanent_warns": [
    "unverified_physical_unit_identity",
    "same_process_causal_self_attestation",
    "quick_design_not_formal_gate"
  ],
  "claim_impact": "sanity_and_simulation_claims_only"
}
```
