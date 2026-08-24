# Result-to-claim adjudication

**Review independence:** same-family  
**Acceptance status:** provisional  
**Integrity status:** WARN; numerical/hash integrity is PASS.  
**Overall confidence:** high for the stated scope boundaries.

> [INTEGRITY: WARN] — audit flagged potential issues. These concern scope, unverified physical identity, self-attested chronology, and quick-simulation eligibility—not numerical corruption.

| Claim | Verdict | Confidence | Overstatement severity |
|---|---|---|---|
| C1 | **yes** | high | High if “sanity scope” is omitted |
| C2 | **no** | high | Critical |
| C3 | **no** | high | Critical |
| C4 | **no** | high | Critical |
| C5 | **partial** | high | Moderate |

## C1 — Deterministic harness operation and reproducibility

**claim_supported: yes**

**Supporting evidence**

- `RUN_SUMMARY.json` records `prediction_rows=1296`, `maturity_rows=1296`, `prediction_failure_rows=0`, `failure_rows=0`, `causal_barrier_status="PASS"`, and `verification_status="VERIFIED"` for context 4.
- Its online barrier is explicitly `per_origin_append_fsync_hash_checkpoint_before_reveal`; the seal was verified before maturity.
- The final results report records 1,512 / 1,296 / 1,080 matured predictions for contexts 3/4/5, with zero prediction/scoring failures. The 144 context-3 ineligible Ridge/window-4 tuning evaluations were preserved as failures rather than silently relabeled.
- The same-code context-4 reproduction produced 11 byte-identical stable artifacts.
- The design harness completed 3,000 planned repeats: 2,987 analyzable and 13 explicit missingness failures. All analyzable rows were reconstructed from archived raw unit losses with zero mismatches, and four sealed scientific artifacts reproduced byte-for-byte.
- The experiment audit reports numerical/hash integrity PASS and 32 passing tests, including causal-lineage tamper rejection and truth-blind decision tests.

**Contradicting or limiting evidence**

- The six Stress-2 columns are only surrogate units; physical-device identity and duplicate structure are unverified.
- The causal barrier is same-process, self-attested software evidence rather than externally timestamped or WORM-anchored chronology.
- The audit is same-family and provisional.
- The low-level design function flags rather than hard-blocks `N<12`; current outputs remain safely hard-gated downstream as `NOT_ELIGIBLE_QUICK_SANITY`.
- Hashes and deterministic reproduction establish implementation reproducibility, not scientific accuracy.

**Narrowest defensible wording**

> On the verified Stress-2 six-column surrogate fixture, the deterministic parser, nested surrogate-LOCO rolling replay, append/fsync causal ledger, explicit failure accounting, and truth-blind quick-design simulator executed reproducibly within their frozen implementation-sanity scope.

**Evidence needed to upgrade**

Independent cross-family review and reproduction in a separate environment; externally anchored chronology; hard enforcement of all eligibility checks; and equivalent parser/replay validation on identity-resolved Benchmark-L data.

**Severity if overstated:** High if presented as physical-device independence, external causal proof, or model accuracy.

## C2 — General Ridge superiority

**claim_supported: no**

**Supporting evidence for only a much narrower observation**

- In context 4, Ridge has the lowest observed macro MAE among the six executed candidates for all six target/horizon cells. Examples include capacity h=1 `0.0070735759` and ESR h=1 `0.0125820740`.
- The results report states that Ridge had the lowest observed macro MAE in all 18 executed target × horizon × context cells.

**Contradicting evidence**

- `RUN_SUMMARY.json` explicitly records `claim_prohibited=true` and `claim_status="NOT_ELIGIBLE_BENCHMARK_S_SANITY_ONLY"`.
- The evaluation contains one 11×6-column dataset, and the columns are not proven to be six independent physical capacitors.
- `N=6` is below the confirmatory minimum; overlapping origins are not independent samples.
- Context changes alter eligible origins and selected configurations, so the sensitivity results are not one paired estimand.
- The same dataset informed harness development; there is no identity-safe independent Benchmark-L or external evaluation.
- There is no physical-time, cross-condition, deployment, or general capacitor population evidence.

**Narrowest defensible wording**

> Ridge had the lowest observed macro MAE among six deterministic candidates in every executed cell of this six-column Stress-2 implementation-sanity harness; this is descriptive ordering only.

**Evidence needed to upgrade**

A frozen, reference-aware Benchmark-L parser; verified physical identities and duplicate groups; acquisition-time and target semantics; a preregistered primary comparison; identity-safe nested LOCO and separate leave-one-condition-out evaluation; adequate independent-unit support; clustered inference; and independent held-out or external replication.

**Severity if overstated:** Critical.

## C3 — Accurate/calibrated RUL and uncertainty prediction

**claim_supported: no**

**Supporting evidence**

- None for RUL accuracy or uncertainty calibration. The reported capacity/ESR point errors do not establish either claim.

**Contradicting evidence**

- `RUN_SUMMARY.json` records:
  - `rul_metrics_status="NA_unknown_termination_and_insufficient_independent_units"`
  - `prediction_intervals_status="NA_insufficient_independent_calibration_units"`
  - `termination_scope="unknown; RUL numeric scoring disabled"`
- `DESIGN_SIM_SUMMARY.json` records `rul_module="NA_outcome_and_termination_gate_unresolved"`.
- The large-pack audits found no defensible termination, censoring, SOH, RUL, or direct ESR target fields. Sequence end is explicitly not accepted as EOL or right censoring.
- The quick-design coverage values are synthetic decision-simulation diagnostics, not calibrated prediction intervals for real capacitors.

**Narrowest defensible wording**

> RUL and prediction-interval evaluation were deliberately disabled because termination, censoring, physical identity, and calibration-unit requirements are unresolved; only descriptive capacity/ESR point-forecast errors were computed on the surrogate sanity fixture.

**Evidence needed to upgrade**

Verified outcome and termination semantics; a frozen EOL/censoring construction; independently identified devices; adequate calibration units; preregistered RUL and interval estimands; censoring-compatible proper scores; 50/80/90% empirical coverage and sharpness results; and independent test evaluation.

**Severity if overstated:** Critical.

## C4 — Formal Design Gate or champion/topology selection

**claim_supported: no**

**Supporting evidence for only implementation diagnostics**

- The truth-blind quick simulator ran all 15 cells and preserved 13 explicit missingness failures.
- Some null/harmful point estimates are directionally reassuring, but they are simulation-only sanity diagnostics.

**Contradicting evidence**

- Every design cell and the summary are marked `NOT_ELIGIBLE_QUICK_SANITY` / `NOT_EVALUATED_QUICK_SANITY`.
- Current cells use 200 repeats; the formal protocol requires at least 2,000 per cell and 10,000 for required anchors.
- QT1 at 10% effect has 78.5% correct selection with lower 95% bound 72.15%, below the required 80% lower bound.
- QT3 at 10% effect has 52.0% correct champion probability with lower bound 44.84%, also far below 80%.
- Small-N 10%-effect comparison coverage is 89.0%–91.5%, below the required 93%–97% band.
- QT1 null promotion is 4.0%, but its 95% upper bound is 7.73%, exceeding the formal ≤5% upper-bound requirement.
- Benchmark-L unit count, candidate family, targets, and missingness structure are not frozen.
- Agent topology experiments remain blocked; no topology comparison or external model service contributed to these results.

**Narrowest defensible wording**

> The quick synthetic design harness is operational and exposes inadequate power or coverage in several scenarios; the formal Design Gate was not evaluated, and no model champion or Agent topology was selected.

**Evidence needed to upgrade**

Pass the Benchmark-L Data Gate; freeze independent-unit inventory, estimand, candidates, missingness rules, and tie rule; execute the formal simulation budget; satisfy every preregistered power, false-promotion, coverage, multiplicity, and bias criterion; then run eligible frozen outer evaluations. Agent topology requires a separate equal-budget hidden-task meta-evaluation.

**Severity if overstated:** Critical.

## C5 — Route to Benchmark-L parser/target-definition work only

**claim_supported: partial**

**Supporting evidence**

- Both large-pack audits classify the current state as `partial_integrity_only`; Benchmark-L modeling and RUL remain blocked.
- A reference-aware parser is specifically required because event reference order is nonchronological, Header/Data must be paired by replicate index, and the inferred 20-token-to-18-column map is unverified.
- ES12 has an unresolved four-row timestamp/signal mismatch.
- All 46 transient VL/VO datasets contain NaNs; missingness geometry and causal masks are not frozen.
- Physical identity, duplicate groups, direct ESR derivation, target extraction, termination, and censoring remain unresolved.
- The results explicitly route next work to parser/schema, acquisition-time, identity, target, and outcome validation before modeling.

**Contradicting evidence**

- Calling the immediate parser/target-definition stage “Freeze B” is premature under the frozen protocol. The formal order is Data Gate → Design Gate → Freeze B.
- Freeze B additionally requires a frozen primary endpoint, horizon, estimand, comparison, eligibility gate, bounds, missingness rule, tie rule, and sealed-analysis lineage. Those inputs are not yet eligible to freeze.
- The formal Design Gate remains blocked pending the data structure and candidate inventory.

**Narrowest defensible wording**

> Proceed only to a separately frozen, reference-aware Benchmark-L parser and target-semantics/Data-Gate phase. Keep Benchmark-L modeling and all RUL work blocked. Enter the formal Design Gate and then Freeze B only after identity, duplicate, acquisition-time, target, missingness, and outcome/termination requirements are resolved.

**Evidence needed to upgrade**

Pass the parser/schema tests; resolve ES12 alignment and missingness rules; establish or explicitly quarantine identity and duplicates; freeze defensible capacity/ESR targets and acquisition-time availability; resolve outcome/censoring; run the formal design simulation; and only then complete formal Freeze B.

**Severity if overstated:** Moderate, because the safe routing is correct but the protocol-stage label is premature.

## Overall claim ceiling

The evidence establishes a reproducible deterministic implementation-sanity harness on Stress-2 column surrogates and a reproducible truth-blind quick synthetic design simulator with explicit failure accounting. It supports no claim of model accuracy or superiority, independent physical-device inference, RUL or interval calibration, cross-condition robustness, deployment readiness, formal Data/Design Gate passage, Benchmark-L eligibility, champion selection, or Agent-topology advantage.

## Publication-safe paragraph

On the verified NASA Stress-2 artifact, the deterministic implementation completed nested surrogate-LOCO rolling replay for six MAT columns, producing and maturing 1,296 context-4 predictions with zero prediction or scoring failures; a same-code rerun reproduced 11 stable artifacts byte-for-byte. A truth-blind quick synthetic decision simulator completed 3,000 planned repeats, retaining 2,987 analyzable repeats and 13 explicit missingness failures, and reproduced four sealed scientific artifacts byte-for-byte. These results establish implementation and bookkeeping sanity only. The six columns are not verified independent physical devices, the causal barrier is same-process software evidence, RUL and prediction-interval scoring are unavailable, and the formal Design Gate was not evaluated. We therefore make no model-superiority, calibration, RUL, champion, Benchmark-L, or Agent-topology claim.

## Forbidden claims

- Ridge, or any tested model, is generally the most accurate capacitor prognostics method.
- Six Stress-2 columns constitute six verified independent physical devices.
- The observed window-level counts provide an independent sample size larger than six.
- RUL, SOH lifetime, survival, or uncertainty intervals are accurate or calibrated.
- Sequence end is a failure or administratively right-censored outcome.
- Event-step results establish physical-time-horizon accuracy.
- Benchmark-L, its Data Gate, or its formal Design Gate has passed.
- The 24 provisional large-pack labels are 24 independent capacitors.
- The large pack provides a direct validated ESR or termination target.
- A model champion or Agent topology has been selected.
- Quick-simulation rates are formal Gate results or real-data accuracy evidence.
- Hashes or same-process seals establish external chronology, leakage freedom in deployment, or scientific validity.
- Cross-condition robustness, deployment readiness, or multi-agent advantage has been demonstrated.

## Next experiment decision

Proceed with **parser/Data-Gate work only**:

1. Freeze and test Header/Data replicate linkage, acquisition-time parsing and sorting, the 20-token-to-18-column mapping, frequency rules, and replicate aggregation.
2. Resolve ES12’s four-row mismatch without silent truncation and freeze causal NaN/missingness masks.
3. Perform content-level duplicate checks and resolve or explicitly quarantine physical identity.
4. Freeze scientifically defensible capacity and ESR target extraction without inspecting candidate outer results.
5. Keep Benchmark-L modeling, RUL, formal champion selection, and Agent topology evaluation blocked.
6. After the Data Gate passes, parameterize and run the formal Design Gate; complete formal Freeze B only afterward.

**Ablation plan warranted now:** **No.** The only supported positive claim is implementation sanity. Performance ablations would be premature without an eligible benchmark, target, independent-unit structure, or performance claim.

```json
{
  "review_independence": "same-family",
  "acceptance_status": "provisional",
  "integrity_status": "warn",
  "numerical_integrity": "pass",
  "overall_claim_ceiling": "deterministic Stress-2 surrogate replay and quick synthetic-design implementation sanity only",
  "claims": {
    "C1": {
      "claim_supported": "yes",
      "confidence": "high",
      "narrow_wording": "The deterministic parser, surrogate-LOCO replay, causal ledger, failure accounting, and truth-blind quick simulator are operational and reproducible on the frozen sanity fixtures.",
      "missing_to_upgrade": "independent cross-family/environment reproduction, external chronology, identity-resolved Benchmark-L validation",
      "overstatement_severity": "high_if_scope_removed"
    },
    "C2": {
      "claim_supported": "no",
      "confidence": "high",
      "narrow_wording": "Ridge had the lowest observed macro MAE in all executed Stress-2 surrogate cells; this is descriptive ordering only.",
      "missing_to_upgrade": "identity-safe preregistered Benchmark-L and independent external evaluation",
      "overstatement_severity": "critical"
    },
    "C3": {
      "claim_supported": "no",
      "confidence": "high",
      "narrow_wording": "RUL and interval scoring were disabled; only descriptive capacity/ESR point errors were computed.",
      "missing_to_upgrade": "verified termination/censoring, independent units, frozen RUL estimand, calibration and proper-score evaluation",
      "overstatement_severity": "critical"
    },
    "C4": {
      "claim_supported": "no",
      "confidence": "high",
      "narrow_wording": "The quick simulator is operational, but the formal Design Gate was not evaluated and no champion or topology was selected.",
      "missing_to_upgrade": "formal-repeat budget, all preregistered criteria, eligible frozen real-data evaluation, separate topology meta-eval",
      "overstatement_severity": "critical"
    },
    "C5": {
      "claim_supported": "partial",
      "confidence": "high",
      "narrow_wording": "Proceed to frozen reference-aware parser and target-semantics/Data-Gate work only; run the formal Design Gate and Freeze B afterward.",
      "missing_to_upgrade": "identity/time/target/missingness/outcome gates plus formal Design Gate completion",
      "overstatement_severity": "moderate"
    }
  },
  "forbidden_claims": [
    "general_model_superiority",
    "physical_device_independence",
    "rul_accuracy",
    "interval_calibration",
    "cross_condition_robustness",
    "deployment_readiness",
    "benchmark_L_or_formal_gate_pass",
    "model_champion",
    "agent_topology_advantage"
  ],
  "next_experiment": {
    "decision": "parser_and_data_gate_only",
    "benchmark_L_modeling": "blocked",
    "rul": "blocked",
    "formal_design_gate": "blocked_pending_data_gate",
    "ablation_plan_warranted": false
  }
}
```
