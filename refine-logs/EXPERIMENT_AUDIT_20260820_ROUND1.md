# Experiment Audit Report — Round 1

**Date**: 2026-08-20  
**Auditor**: GPT-5.6-Sol ultra, fresh same-family agent  
**Review independence**: same-family  
**Acceptance status**: provisional  
**Overall verdict**: WARN  
**Integrity status**: warn

The full unabridged reviewer response and request are preserved under `.aris/traces/experiment-audit/2026-08-20_run01/`. No fabricated Stress-2 ground truth, self-output normalization, phantom numerical result, omitted prediction/scoring failure, or dead claimed metric was found. All reported trajectory metrics were independently recomputed, and the supplied deterministic reruns matched.

## Checks

### A. Ground Truth Provenance — WARN

Stress-2 targets are direct deterministic transforms of MAT observations (`real_gt`), and the design study is explicitly `simulation_only`. The six MAT columns do not establish six independent physical capacitors or duplicate relationships, so all inference remains column-surrogate only.

### B. Score Normalization — WARN

Stress MAE/RMSE are raw; MASE uses outer-training first differences; relative skill uses the separately run last-value baseline. No self-normalization was found. Round 1 warned that design per-repeat raw unit losses were not archived, preventing artifact-only recomputation of effect estimates and p-values.

### C. Result Existence — WARN

Every named result file, count, hash, metric, and tracker status existed and matched. Context=3's 144 rejected Ridge/window=4 tuning evaluations were present, never selected, and disclosed. Round 1 warned that design artifacts lacked code/protocol/environment lineage, had an unbound text `COMPLETE`, and used an inaccurate generic seal status.

### D. Dead Code — PASS

Every claimed metric path was executed and emitted. RUL and interval metrics were explicitly NA/blocked rather than claimed.

### E. Scope — WARN

Actual trajectory scope is one 11×6-column dataset, two targets, three horizons, three contexts, six deterministic model families, and one same-code rerun. Design scope is 15 quick simulation cells × 200 repeats. Neither supports a general accuracy, RUL, uncertainty, Design Gate, or deployment claim.

### F. Evaluation Type — PASS

Stress runs: `real_gt` with surrogate-grouping qualification. Design runs: `simulation_only`.

## Round-1 reason codes

- `UNVERIFIED_PHYSICAL_UNIT_IDENTITY`
- `CAUSAL_BARRIER_SELF_ATTESTED`
- `DESIGN_CODE_PROTOCOL_LINEAGE_MISSING`
- `DESIGN_RAW_UNIT_LOSSES_NOT_ARCHIVED`
- `MISLEADING_DESIGN_SEAL_STATUS`
- `REVIEW_INDEPENDENCE_UNEVIDENCED`
- `LOCAL_SOURCE_PROVENANCE_ONLY`

## Claim impact

- Supported: counts, raw Stress metrics, internal hashes/chains, disclosed tuning failures, deterministic reruns, tests, and blocked claim families.
- Supported only descriptively: Ridge's observed ordering on the six-column harness.
- Supported only as simulation: quick design operating rates.
- Needs permanent qualifier: causal sequencing is same-process software evidence, not externally time-anchored proof; LOCO is surrogate-column LOCO, not proven device-independent LOCO.
- Unsupported in round-1 inputs: the process claim of an independent pre-run review because no reviewer trace was supplied. This audit's own full trace is now preserved.

## Required remediation

Round 1 requested design code/protocol/environment lineage, accurate seal semantics, a bound `COMPLETE`, raw unit losses, permanent causal/identity qualifiers, and reviewer tracing. The design-specific mechanical items were implemented after this snapshot and are subject to round-2 review; identity and external anchoring remain unresolved by design.
