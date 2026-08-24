# CAP-ACT Experiment Code Review — M0/M1 Integration Round 1

**Time**: 2026-08-24 15:28:02 +08:00  
**Reviewer**: fresh same-family `gpt-5.6-sol` (`xhigh`), read-only  
**Verdict**: `BLOCKING_ACCURACY_RUNS`  
**Scope**: `experiments/vfps_agent` M0/M1 contracts, action registry, budget and ledgers. No network, provider, data, accuracy or RUL run was performed.

## Verified in isolation

- H1=6, RF1=5 and RC1=8 are disjoint and their union is exactly ACT1=19.
- `b_star` is structurally the literal common `FALLBACK=N0`.
- ACT1 cannot select ACT-COMP96-only transforms.
- Strict response shapes, complete-key checks, convex fusion, SHIFT, INFLATE, whole-bundle fallback and numeric-RUL rejection pass.
- ENUM deterministic tie/backoff behaviour passes on synthetic fixtures.
- The reviewed mock provider path has no network or environment access.

Selected regression command:

```text
.venv-audit-cap/bin/python -m pytest -q \
  tests/test_vfps_contracts.py tests/test_vfps_budget_ledger.py \
  tests/test_vfps_no_network.py tests/test_capact_actions_verifier.py \
  tests/test_capact_arms_search.py
```

Result: `40 passed`.

## Blocking findings

1. **M0/M1 are not integrated in the durable path.** The budget runner accepts generic decoded output and arbitrary fallback instead of binding the policy, packet, CAP registry, action space, `b_star` and budget hashes before invoking `execute_arm`.
2. **One-attempt state is process-local.** A fresh process can resend the same slot; append/resume locking and deterministic no-resend recovery for crash-left `STARTED` attempts are absent.
3. **Cross-ledger linkage is incomplete.** Prediction verification does not mechanically bind attempt STARTED/FINISHED, policy, origin, packet, prediction, commit, checkpoint and seal records; an orphan prediction can pass isolated chain verification.
4. **Per-key execution/maturity state is missing.** Every planned key must persist exactly one of `ACTIVE`, `DELIBERATE_FALLBACK`, `ERROR_FALLBACK`, then exactly one of `MATURED`, `NEVER_MATURED`.
5. **The packet boundary is not fully causal/identity-safe.** It must enforce `observed_at <= available_at <= cutoff`, typed allowlists, sealed split/provenance lineage, chronology and broader identity/future-proxy rejection.
6. **ENUM/IF1 are not outer-fold bound.** Loss tables, feature bins and context strata need outer-training/cross-fit/additive-loss provenance and packet-derived context hashes, with held-out-label invariance tests.
7. **Secret-safe logging is incomplete.** Public ledgers must store only a closed error enum and hashed provider response ID, never hashes of raw response/reasoning or provider-supplied free text; canary rejection must cover every provider/exception field.
8. **IF1 grammar cardinality is only asserted, not implemented.** The declared 76,969 syntax requires 19 unconditional artifacts plus 76,950 conditional artifacts, or a protocol revision to the actually accepted grammar.

## Endpoint and scope caveat

When an endpoint gate forces RUL to `NA`, the key must expose one explicit forced `RUL_NA` action and be excluded from active-action coverage. It must not appear as 19 syntactically different actions that collapse to the same `NA` output.

## Release decision

- M0/M1 primitives: `PASS_IN_ISOLATION`.
- M2 mock hardening: `REQUIRED`.
- Any claim-producing data/API run: `BLOCKED`.
- Benchmark-L model/RUL run: independently `BLOCKED` by its Data Gate.
- Authenticated Ark call: independently `BLOCKED` pending rotated credential and human Gate.

A second fresh review is required after M2 integration. Passing unit tests alone cannot lift the accuracy-run block.
