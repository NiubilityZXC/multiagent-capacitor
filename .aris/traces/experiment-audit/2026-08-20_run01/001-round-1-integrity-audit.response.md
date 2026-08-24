# Round-1 Experiment Integrity Audit

**Overall verdict: WARN**

**Assurance:** same-family fresh-agent review; provisional.  
**Project files changed:** none.

No evidence was found of fabricated numerical results, model-derived Stress-2 ground truth, self-output/max normalization, omitted prediction failures, duplicate prediction keys, or mismatch between the recorded Stress-2 code hash and present code. The published numerical tables reproduce from the supplied artifacts.

The WARN is driven by provenance and evidentiary limitations:

- Physical identities and duplicate relationships of the six Stress-2 columns are not established.
- The causal barrier is internally consistent but not externally time-anchored or process-isolated.
- Design-simulation artifacts omit code/protocol lineage and raw unit-loss denominators.
- The design seals incorrectly say `SEALED_BEFORE_LABEL_ACCESS` even though they are written after synthetic-truth analysis.
- “Independent reviewer” process claims lack a supplied reviewer trace.

Reason codes:

- `UNVERIFIED_PHYSICAL_UNIT_IDENTITY`
- `CAUSAL_BARRIER_SELF_ATTESTED`
- `DESIGN_CODE_PROTOCOL_LINEAGE_MISSING`
- `DESIGN_RAW_UNIT_LOSSES_NOT_ARCHIVED`
- `MISLEADING_DESIGN_SEAL_STATUS`
- `REVIEW_INDEPENDENCE_UNEVIDENCED`
- `LOCAL_SOURCE_PROVENANCE_ONLY`

## Verification performed

- Read every listed source, test, protocol, tracker, report, result JSON/JSONL/CSV, and both large design ledgers.
- Independently decoded `EOS_DataSet.mat` from the ZIP:
  - `aging_time`: `(11,1)`
  - `C`: `(11,6)`
  - `ESR`: `(11,6)`
- Recomputed:
  - ZIP SHA-256: `944cd228...6accacfb`
  - MAT SHA-256: `9db651a1...00cb4a3`
  - current Stress-2 package hash: `fae1423f...8981f8`
  - current frozen protocol hash: `3b1b4471...d873dc`
- Verified all four Stress-2 prediction seals, CSV row chains, JSONL chains, manifests, `COMPLETE` bindings, split hashes, prefix hashes, training-snapshot hashes, and prediction IDs.
- Recomputed every Stress-2 unit and aggregate MAE/RMSE/MASE; maximum floating serialization discrepancy was below `4.5e-15`.
- Recomputed every design cell count/rate/mean from all 3,000 repeat rows.
- Ran the present code independently:
  - Context-4 Stress-2 reproduced all 11 stable artifacts byte-for-byte.
  - Design quick reproduced all seven artifacts byte-for-byte.
- Tests:
  - All three listed test files: `24 passed`.
  - Full project `tests/` suite supporting the report’s test-count claim: `30 passed`.

## A. Ground Truth Provenance — WARN

### Stress-2 trajectory evaluation

The trajectory labels are real dataset observations, not model outputs.

Evidence:

- Fixed source hashes and required MAT variables: `experiments/audit_cap/stress2.py:21-24`.
- Raw `C` and `ESR` arrays are loaded directly: `stress2.py:84-97`.
- Evaluated values are deterministic transforms:
  - `capacity_ratio = 1 - C_loss/100`
  - `esr_ratio = 1 + ESR_increase/100`
  - `stress2.py:109-130`.
- Maturity scoring resolves the held-out target from the canonical dataset event: `experiments/audit_cap/replay.py:1090-1103`.
- The report explicitly limits the claim to observed degradation ratios: `refine-logs/EXPERIMENT_RESULTS_20260820_155512.md:19`.

Classification: `real_gt`.

Qualifications:

- The MAT contains no physical-unit identifiers, duplicate-group metadata, termination reason, or embedded voltage metadata.
- The parser explicitly records `physical_unit_id=None`, `unit_identity_status=column_surrogate`, and `possible_duplicate_group=unknown`: `stress2.py:114-124`.
- Stress voltage is labeled as external metadata, not MAT content: `stress2.py:134-135`.
- No two C or ESR columns are numerically identical, but that does not prove six independent devices.
- Endpoint crossings are deterministic threshold derivations from real observations, but `rul_score_eligible=False`: `stress2.py:143-190`.
- “NASA/public” acquisition provenance is not established by the listed artifacts alone; only the local byte identity is proven.

### Design simulation

Truth is explicitly synthetic:

- Synthetic effect enters the DGP at `design_simulation.py:141-164`.
- The repeat-seal lineage says `"labels": "synthetic_ground_truth"`: `DESIGN_REPEAT_SEAL.json:30-33`.
- Summary fixes mode to `quick_trajectory_only` and Design Gate to not evaluated: `DESIGN_SIM_SUMMARY.json:45-51`.

Classification: `simulation_only`.

There is no undisclosed model-generated ground truth.

## B. Score Normalization — WARN

### Stress-2 — PASS

No prediction metric is divided by a statistic of the evaluated model’s own predictions.

- MAE/RMSE use raw prediction-minus-observation errors: `replay.py:1153-1205`.
- MASE denominator is the mean first-difference scale of outer-training units only: `replay.py:1182-1206`.
- Relative skill uses the separately executed last-value baseline: `replay.py:1221-1242`.
- Raw predictions, actual labels, unit metrics, scale denominators, and aggregate metrics all exist and were independently recomputed.
- Primary unrounded values are present at `AGGREGATE_METRICS.csv:2-37`.

### Design simulation — WARN

There is no fraudulent self-max normalization:

- Effect estimate is the protocol-defined comparator ratio  
  `1 - mean(candidate loss)/mean(incumbent loss)`: `design_simulation.py:222-225`.
- Promotion/correctness/coverage rates use all 200 planned repeats as denominator: `design_simulation.py:285-318`.
- Failures therefore lower planned-denominator rates rather than disappearing.

However, the raw per-unit incumbent/candidate losses and even their per-repeat means are discarded after analysis:

- Loss arrays are produced at `design_simulation.py:118-173`.
- Only derived repeat summaries are retained at `design_simulation.py:274-284`.
- `DESIGN_REPEAT_SEAL.json:2-25` confirms the ledger has effect estimates, differences, p-values, and decisions, but not raw unit losses or numerator/denominator means.

Thus cell rates can be recomputed from artifacts, but per-repeat effect estimates and p-values cannot be independently recomputed without rerunning the current code.

## C. Result File Existence and Claim Matching — WARN

All six named result directories exist and contain the expected files.

### Verified Stress-2 counts

| Run | Predictions | Maturities | Checkpoints | Reveals | Prediction/scoring failures |
|---|---:|---:|---:|---:|---:|
| context 3 | 1,512 | 1,512 | 48 | 66 | 0 |
| context 4 | 1,296 | 1,296 | 42 | 66 | 0 |
| context 5 | 1,080 | 1,080 | 36 | 66 | 0 |
| context-4 repro | 1,296 | 1,296 | 42 | 66 | 0 |

Artifact examples:

- Primary counts and status: `stress2_context4_complete.../RUN_SUMMARY.json:3-48`.
- Context-3 counts: `stress2_context3_sensitivity.../RUN_SUMMARY.json:3-48`.
- Context-5 counts: `stress2_context5_sensitivity.../RUN_SUMMARY.json:3-48`.
- Primary seal: `stress2_context4_complete.../PREDICTION_LEDGER.seal.json:36-79`.
- Primary manifest hashes: `stress2_context4_complete.../RUN_MANIFEST.json:3-50`.
- Primary final marker binds both manifest and seal: `stress2_context4_complete.../COMPLETE:2-7`.

The reported primary metric table matches `AGGREGATE_METRICS.csv:2-37`, including all 36 model-target-horizon rows.

### Hidden tuning failures

They are not hidden:

- Context 3 contains exactly 144 rejected Ridge/window-4 tuning rows.
- First examples appear at `INNER_TUNING_LEDGER.csv:112-115`.
- Every failed candidate has `selected=False`.
- Tuning status totals: 900 `OK`, 144 `FAIL`.
- Predictions and maturities remain 1,512/1,512 `OK`.
- This matches the disclosure at `EXPERIMENT_RESULTS_20260820_155512.md:31`.

Context 4 and context 5 each contain 1,044 successful tuning rows and no tuning failures.

### Verified design counts

- 15 cells × 200 repeats = 3,000.
- 2,987 `OK`; 13 `FAIL_NO_MATURE_ORIGIN`.
- Failures occur only in QT2:
  - null: 7
  - 10% effect: 6
- Evidence: `DESIGN_CELL_SUMMARY.csv:13-14` and `DESIGN_SIM_SUMMARY.json:45-51`.
- QT1 10% is exactly 78.5%, CI `[0.721529, 0.839818]`: `DESIGN_CELL_SUMMARY.csv:12`.
- QT3 10% is exactly 52.0%, CI `[0.448412, 0.590986]`: `DESIGN_CELL_SUMMARY.csv:16`.

### Reproducibility claims

PASS for observed byte equality:

- Context-4 primary/repro differ only in `RUN_SUMMARY.json`, `RUN_MANIFEST.json`, and `COMPLETE`; the 11 claimed stable artifacts are byte-identical.
- The two design directories are byte-identical for all seven files.
- A new round-1 rerun using current code reproduced the same stable Stress-2 hashes and every design artifact.

### Provenance gaps

- Design `RUN_MANIFEST.json:2-23` lists five artifacts but has no:
  - code hash
  - design protocol hash
  - command
  - dependencies
  - seed/config lineage at manifest level
- Design `COMPLETE:1` is only `complete`; it does not bind the manifest or seals.
- Therefore the historical run-to-code/run-to-protocol relationship is not cryptographically established, even though current code reproduces it exactly.
- The report’s “independent pre-run reviewer” statement at `EXPERIMENT_RESULTS_20260820_155512.md:34` has no supplied reviewer trace or reviewer identity artifact. The attack test itself is real and passes (`tests/test_stress2_replay.py:315-389`), but reviewer independence is unverified.

Tracker states are otherwise consistent with artifacts:

- Stress sanity rows: `EXPERIMENT_TRACKER.md:13-24`.
- Design quick is `COMPLETE_NOT_EVALUATED`: `EXPERIMENT_TRACKER.md:17-18`.
- Benchmark L/formal design remain blocked: `EXPERIMENT_TRACKER.md:18,25-29`.

## D. Dead Code Detection — PASS

No claimed metric function was found to be dead.

- Inner validation MAE is executed through `_select_config`: `replay.py:170-258`.
- Unit/aggregate MAE, RMSE, MASE, and last-value comparisons are executed in `_score_predictions`: `replay.py:1153-1278`.
- `_score_predictions` is invoked during maturity: `replay.py:1379-1385`.
- All resulting tables are emitted by the CLI: `run_stress2_baselines.py:108-118`.
- Design paired t, Holm selection, Clopper-Pearson intervals, coverage, and rates are executed at `design_simulation.py:201-245,285-325`.
- The design ledgers and summary are emitted at `design_simulation.py:367-388`.

RUL, survival, and prediction-interval metrics are not implemented in this slice, but they are explicitly `NA`/blocked rather than claimed:

- `run_stress2_baselines.py:129-130`
- `DESIGN_SIM_SUMMARY.json:45-50,89`
- `EXPERIMENT_RESULTS_20260820_155512.md:138-143`

An unused `revealed_index` accessor exists at `replay.py:514-516`; it is not a claimed metric and has no result impact.

## E. Scope Assessment — WARN

### Actual Stress-2 scope

- One ZIP containing one 1,090-byte MAT data member.
- Six unidentified matrix columns, 11 time points each.
- Two evaluated targets.
- Three event-step horizons.
- Contexts 3, 4, and 5.
- Six deterministic model families.
- 29 configuration candidates per outer-unit/target/horizon combination, yielding 1,044 tuning rows per run.
- One nominal seed (`20260813`); models in this suite are deterministic.
- One same-code/same-environment context-4 rerun.
- No Benchmark L, RUL, uncertainty intervals, physical-time horizons, deployment test, or independent external dataset.

The result report is generally disciplined about these limits. However:

- The frozen protocol initially calls the six columns “6 capacitors” at `FROZEN_EVAL_PROTOCOL.md:29-35`, while the raw MAT does not establish that identity.
- The later parser/report/tracker correctly downgrade these to column surrogates:
  - `RUN_SUMMARY.json:28`
  - `EXPERIMENT_RESULTS_20260820_155512.md:19`
  - `EXPERIMENT_TRACKER.md:37`

Any use of `n=6` for confirmatory independent-unit inference would therefore exceed the evidence.

### Actual design scope

- Six synthetic scenario structures.
- Fifteen cells.
- 200 repeats per cell.
- 3,000 deterministic per-repeat seed streams.
- Synthetic `N=6` or `N=12`; `K=1` or `K=5`.
- Quick simulation only.
- No formal ≥2,000-repeat grid.
- No real-device Design Gate.

The report correctly labels this `NOT_EVALUATED_QUICK_SANITY`. Its rates support simulator diagnostics only.

## F. Evaluation Classification — PASS

| Evaluation | Classification | Qualification |
|---|---|---|
| Stress-2 context 3 | `real_gt` | Real observed MAT values; grouping only by unverified column surrogate |
| Stress-2 context 4 | `real_gt` | Same |
| Stress-2 context 5 | `real_gt` | Same |
| Stress-2 context-4 repro | `real_gt` | Deterministic duplicate of the same evaluation |
| Design quick | `simulation_only` | Explicit synthetic ground truth |
| Design quick repro | `simulation_only` | Deterministic duplicate |

No `self_supervised_proxy`, `human_eval`, or undisclosed `synthetic_proxy` evaluation was found.

## Additional integrity checks

### Append-only and seals — WARN

Stress-2 internal consistency passes:

- Writers refuse existing ledger targets: `ledger.py:92-105`, `replay.py:381-405`.
- Every prediction row is flushed/fsynced before its checkpoint: `replay.py:417-443`.
- Access authorization is fsynced before reading the next event: `replay.py:528-568`.
- Final seal binds prediction ledger, checkpoint log, and reveal log: `replay.py:455-484`.
- All four supplied chains and seals independently verify.

Evidentiary limitation:

- Files are opened in ordinary exclusive write mode, not OS-enforced append-only/WORM storage.
- Prediction, checkpoint, reveal, and final seal are produced by the same process.
- Checkpoint/access logs are bound only by the final seal after the complete replay.
- There is no external timestamp, signed checkpoint service, separate label-process trust boundary, or externally anchored seal.

Therefore the artifacts prove self-consistency under the recorded code, not non-repudiable historical chronology against a malicious executor.

### Design seal semantics — WARN

`write_sealed_ledger` hardcodes `"SEALED_BEFORE_LABEL_ACCESS"` at `ledger.py:115-123`.

But design execution:

1. Generates synthetic truth and losses.
2. Runs truth-aware coverage/correctness analysis.
3. Builds repeat and cell results.
4. Only then writes both seals.

Evidence: `design_simulation.py:258-341,367-381`.

Yet the artifact says `SEALED_BEFORE_LABEL_ACCESS`: `DESIGN_REPEAT_SEAL.json:27-36`.

That status is semantically false for this result ledger. It does not invalidate the hash chain or numerical results, but it must not be cited as pre-label causal evidence.

### Failure parity — PASS

- Stress models share exactly the same planned common keys; no duplicate model-key or prediction ID exists.
- Generation/config/state/predict failure parity is enforced at `replay.py:572-588,661-752`.
- Maturity failure propagation and strict aggregate `NA` behavior are at `replay.py:1153-1278`.
- Fault-injection tests cover config/state/predict/maturity failures: `tests/test_stress2_replay.py:392-540`.
- Design shares the same availability mask across candidates: `design_simulation.py:149-173`.
- Failed design repeats remain in the planned denominator.

### Nested splitting — WARN

Code-level nested splitting is correct:

- Outer held-out column is excluded before reading training target values: `replay.py:155-167`.
- Inner validation leaves one outer-training column out: `replay.py:178-195`.
- Hyperparameter selection is per outer fold/target/horizon: `replay.py:198-258`.
- Final state is fitted only on outer-training columns: `replay.py:934-960`.
- All split, train-set, and exact training-snapshot hashes independently match.

The remaining WARN is not a code leakage: column-level grouping cannot guarantee physical-device or duplicate-group disjointness because identity is absent.

### Future-label access — WARN

The predictor boundary only receives copied revealed prefixes:

- `replay.py:661-697`.
- Predictions are committed before `service.reveal_next`: `replay.py:961-987`.
- Prediction ledger contains no `actual` or `target_time_h`.
- All rows satisfy `prediction_commit_seq < expected_label_available_seq`.
- All prefix hashes match the exact raw prefix.

However, the event service and predictor execute in one Python process and the service owns the full `Stress2Data`; this is logical separation, not process/security isolation. The supplied logs are strong software-test evidence but not a hostile-executor guarantee.

### Code-hash match — mixed

- Stress-2: PASS. Recorded hash `fae1423f...8981f8` matches the present `experiments/audit_cap/*.py` package hash and appears in every row, summary, and seal.
- Frozen Stress protocol: PASS. Recorded `3b1b4471...d873dc` matches the present file.
- Design: WARN. No historical code or design-protocol hash exists in its artifacts. Current-code byte reproduction shows behavioral agreement but does not repair historical lineage.

## Claim-by-claim impact

| Claim | Impact | Finding |
|---|---|---|
| Run inventory/counts in report lines 12-17 | Supported | All counts and statuses match artifacts |
| Stress targets are dataset observations, not model GT | Supported with qualifier | Real MAT values; physical column identity remains unknown |
| RUL is disabled because termination is unknown | Supported | Code, summaries, tracker, and endpoint tables agree |
| Recorded ZIP/MAT hashes | Supported locally | Byte hashes match; original NASA/public acquisition chain not supplied |
| All manifests/hash chains verified | Supported | Internal consistency passes |
| Context-3 has 144 rejected tuning evaluations | Supported | Exactly 144, none selected |
| Context-4 deterministic rerun | Supported | Claimed 11 stable files are byte-identical; new rerun also matches |
| Design deterministic rerun | Supported | All seven files are byte-identical; new rerun also matches |
| “30 tests passed” | Supported for present tree | Independently rerun: 30 passed |
| “Independent pre-run reviewer” | Unsupported process claim | No trace/identity artifact supplied |
| Primary context-4 numerical table | Supported | Every number matches and was recomputed |
| Ridge lowest in all 18 context-target-horizon cells | Supported descriptively | True for this six-column harness only |
| Design rates/CIs/failures | Supported as simulation summaries | Rates recompute; raw per-unit losses are absent |
| Durable causal barrier operational | Supported as code-level invariant; needs qualifier | Not externally anchored or process-isolated |
| Nested LOCO | Supported as surrogate-column LOCO only | Does not establish device-independent LOCO |
| Ridge is a credible larger-benchmark candidate | Interpretive only | May motivate future testing; no superiority/generalization claim |
| Benchmark L/RUL/intervals/Design Gate remain blocked | Supported | Tracker and outputs consistently block them |
| CPU-only/no external model service | Supported by code path; historical process only partly evidenced | No external API path exists in the evaluated executables |

## Required actions

1. Add design lineage fields to every seal/summary/manifest:
   - design code hash
   - `DESIGN_SIM_PROTOCOL.md` hash
   - command, seed, dependencies, platform
   - schema/version hash
2. Replace the design seal status with an accurate semantic value such as `SEALED_AFTER_SYNTHETIC_ANALYSIS`; do not reuse `SEALED_BEFORE_LABEL_ACCESS`.
3. Make design `COMPLETE` a JSON marker binding the final manifest and both seals, like the Stress-2 marker.
4. Persist per-repeat unit losses, or at minimum incumbent/candidate means plus hashes of a sealed raw unit-loss ledger.
5. For stronger causal claims, separate predictor and label service and externally anchor every per-origin checkpoint before label release.
6. Resolve physical identity/duplicates before any independent-unit inference; otherwise retain “column-surrogate” everywhere.
7. Supply a reviewer trace before claiming independent review.
8. Before formal Design Gate execution, implement the protocol’s one-sided Clopper-Pearson bounds rather than treating the current quick two-sided intervals as formal-gate code.

## Compact JSON

```json
{
  "audit_skill": "experiment-audit",
  "round": 1,
  "review_independence": "same-family",
  "acceptance_status": "provisional",
  "overall_verdict": "WARN",
  "integrity_status": "warn",
  "reason_codes": [
    "UNVERIFIED_PHYSICAL_UNIT_IDENTITY",
    "CAUSAL_BARRIER_SELF_ATTESTED",
    "DESIGN_CODE_PROTOCOL_LINEAGE_MISSING",
    "DESIGN_RAW_UNIT_LOSSES_NOT_ARCHIVED",
    "MISLEADING_DESIGN_SEAL_STATUS",
    "REVIEW_INDEPENDENCE_UNEVIDENCED",
    "LOCAL_SOURCE_PROVENANCE_ONLY"
  ],
  "checks": {
    "A_ground_truth_provenance": {
      "status": "WARN",
      "details": "Stress-2 targets are direct deterministic transforms of real MAT observations, and design truth is explicitly synthetic. Physical-unit identity, duplicate relationships, and original public acquisition provenance are not proven by the supplied source."
    },
    "B_score_normalization": {
      "status": "WARN",
      "details": "No self-output normalization was found. Stress raw metrics and denominators are reproducible. Design uses a valid incumbent denominator but does not archive raw per-unit losses or numerator/denominator means."
    },
    "C_result_existence": {
      "status": "WARN",
      "details": "All numerical claims, counts, hashes, and tracker statuses match. Design lacks historical code/protocol lineage, and the independent-review process claim has no trace."
    },
    "D_dead_code": {
      "status": "PASS",
      "details": "All claimed metric functions are executed and emitted. Unimplemented RUL/interval metrics are explicitly NA or blocked."
    },
    "E_scope": {
      "status": "WARN",
      "details": "Stress evidence is one dataset with six column surrogates, two targets, three horizons, three contexts, and one deterministic rerun. Design is 15 simulation cells with 200 repeats each, not a formal Design Gate."
    },
    "F_evaluation_type": {
      "status": "PASS",
      "details": "Stress runs are real_gt with surrogate-grouping qualification; design runs are simulation_only."
    }
  },
  "evaluations": [
    {"id": "stress2_context3", "type": "real_gt", "status": "WARN", "scope": "6 column surrogates, 11 events, 2 targets, 3 horizons"},
    {"id": "stress2_context4", "type": "real_gt", "status": "WARN", "scope": "6 column surrogates, 11 events, 2 targets, 3 horizons"},
    {"id": "stress2_context5", "type": "real_gt", "status": "WARN", "scope": "6 column surrogates, 11 events, 2 targets, 3 horizons"},
    {"id": "stress2_context4_repro", "type": "real_gt", "status": "WARN", "scope": "deterministic duplicate"},
    {"id": "design_quick", "type": "simulation_only", "status": "WARN", "scope": "15 cells, 3000 planned repeats"},
    {"id": "design_quick_repro", "type": "simulation_only", "status": "WARN", "scope": "deterministic duplicate"}
  ],
  "independent_checks": {
    "stress_manifest_and_hash_chains": "PASS",
    "stress_causal_log_internal_consistency": "PASS",
    "causal_chronology_external_proof": "WARN",
    "design_hash_chains": "PASS",
    "design_seal_semantic_accuracy": "WARN",
    "failure_parity": "PASS",
    "nested_split_code": "PASS",
    "nested_split_physical_independence": "WARN",
    "future_suffix_boundary_code": "PASS",
    "future_label_process_isolation": "WARN",
    "hidden_tuning_failures": "PASS_DISCLOSED",
    "exact_numeric_recomputation": "PASS",
    "deterministic_reruns": "PASS",
    "stress_code_hash_match": "PASS",
    "design_code_hash_match": "UNVERIFIABLE_FROM_HISTORICAL_ARTIFACT"
  },
  "quantitative_verification": {
    "stress_prediction_rows": {
      "context3": 1512,
      "context4": 1296,
      "context5": 1080,
      "context4_repro": 1296
    },
    "stress_prediction_or_scoring_failures": 0,
    "context3_tuning_failures": 144,
    "design_cells": 15,
    "design_planned_repeats": 3000,
    "design_ok_repeats": 2987,
    "design_failed_repeats": 13,
    "tests_listed_files": "24 passed",
    "tests_full_project_tests_dir": "30 passed"
  },
  "claims": [
    {"id": "C1_run_inventory", "impact": "supported"},
    {"id": "C2_real_stress_gt", "impact": "supported_with_identity_qualifier"},
    {"id": "C3_hash_and_seal_consistency", "impact": "supported_internally"},
    {"id": "C4_context3_tuning_failures", "impact": "supported_and_disclosed"},
    {"id": "C5_deterministic_reruns", "impact": "supported"},
    {"id": "C6_independent_reviewer", "impact": "unsupported_process_claim"},
    {"id": "C7_primary_metrics", "impact": "supported"},
    {"id": "C8_ridge_ordering", "impact": "supported_descriptively_only"},
    {"id": "C9_design_operating_rates", "impact": "supported_as_simulation_only"},
    {"id": "C10_durable_causal_barrier", "impact": "needs_self_attested_software_evidence_qualifier"},
    {"id": "C11_nested_loco", "impact": "supported_for_column_surrogates_only"},
    {"id": "C12_blocked_claim_families", "impact": "supported"}
  ]
}
```