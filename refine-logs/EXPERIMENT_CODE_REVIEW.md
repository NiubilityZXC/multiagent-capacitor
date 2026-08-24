# CAP-ACT Experiment Code Review — M2 Release Round 2

**Time**: 2026-08-24 16:54:32 +08:00  
**Reviewer**: fresh same-family `gpt-5.6-sol` (`xhigh`), read-only  
**Independence**: `same-family`；`provisional`  
**Verdict**: `RELEASE_MOCK_ONLY`  
**Scope**: M2 synthetic protocol, typed actions, causal replay and durable ledgers. No network, provider API, data download, accuracy or RUL experiment was performed.

## Reproduction evidence

Reviewer command:

~~~text
PYTHONDONTWRITEBYTECODE=1 .venv-audit-cap/bin/python -m pytest -q \
  -p no:cacheprovider tests
~~~

Reviewer result: `130 passed in 15.31s`.

Executor independently obtained `130 passed in 15.38s`, then passed:

~~~text
python -m py_compile experiments/vfps_agent/*.py
git diff --check
~~~

These are mock/simulation correctness checks only. They are not forecast-quality, calibration, generalization or RUL evidence.

## Round-1 blocking findings adjudication

### 1. M0/M1 integration into the durable path — PASS (mock)

`runner.py` validates protocol/arm/packet kind, budget, policy, verifier, registry, action manifest, fallback, causal schema and sealed M2 lineage before any provider invocation. Every frozen arm uses the same `CAPAccuracyRun.run_origin` path and terminates in `execute_arm`.

Real provider request construction is not implemented and remains blocked below.

### 2. One-attempt state and crash no-resend — PASS

The attempt ID deterministically binds protocol, policy, origin and physical slot. `STARTED` is fsync'd before invocation; resume uses append-only locked ledgers. Existing `STARTED`, `FINISHED`, prediction, execution or checkpoint states recover without invoking the provider again. Crash points before return and after each durable stage are covered.

### 3. Cross-ledger semantic linkage — PASS

STARTED, FINISHED, prediction commit, per-key execution rows, checkpoint references and phase seals are cross-verified. The verifier recomputes committed prediction schema, bundle forecasts, forecast hashes, certificate authority/action map, outcome flags, commit disposition and record references. A recomputed isolated ledger chain with inconsistent cross-ledger lineage is rejected.

### 4. Per-key execution and maturity — PASS

Every planned key has one closed execution state: `ACTIVE`, `DELIBERATE_FALLBACK` or `ERROR_FALLBACK`; after the prediction phase seal it receives exactly one `MATURED` or `NEVER_MATURED` state. Complete-run verification requires execution and maturity key sets to match and binds matured labels to causally revealed events.

### 5. Causal and identity-safe packet/replay boundary — PASS (mock)

Contracts enforce `observed_at <= available_at <= cutoff`, chronological event indices and both time axes, typed field allowlists, forbidden future/identity proxies and full M2 split/provenance hashes. A checkpoint reveals only `origin+1`, cannot be reused, and suffix mutation leaves current packet bytes invariant. The latest patch additionally requires a proper bootstrap prefix and freezes caller-owned hidden-event mappings at construction.

A same-process private attribute is not a sufficient security boundary for real experiments; process/permission isolation remains required.

### 6. ENUM and IF1 outer binding — PASS (mock declaration)

Formal ENUM loss tables bind outer fold, outer-train set, held-out member, cross-fit manifest, additive loss definition and `OUTER_TRAIN_CROSSFIT` label scope. The formal selector derives its context stratum from the causal packet and rejects inconsistent bindings.

The current hashes are synthetic opaque declarations. Real experiment release requires recomputing them from row-level whole-capacitor manifests and mechanically verifying membership.

### 7. Secret-safe persistence — PASS (mock)

Provider free text and raw response/reasoning are unrepresentable in public attempt records. Only a closed error enum and a scanned hash of the provider response ID can persist. Canonical ledger payloads are scanned again without echoing offending values. Canary tests cover response, error, provider ID and returned-model fields.

The production adapter must pass the same tests.

### 8. IF1 grammar and endpoint-gated RUL — PASS

The implementation materializes 19 unconditional programs plus `225 × 19 × 18 = 76,950` conditional programs, total `76,969`, for a numerical key. IF1 changes representation only; its committed numerical action quotient equals ACT1's 19.

An endpoint-gated RUL key is an explicit exception: it exposes exactly one forced `FALLBACK -> RUL_NA` action, rejects every numeric/transform authority, and is excluded from active-action coverage. Documents must never describe that key as having 19 meaningful actions.

## Remaining blocking issues for real accuracy/RUL

1. **Production Ark adapter**: the formal runner still accepts `MockProvider`. A production adapter must mechanically bind prompt, decode, response schema, requested model, model rule, request bytes and returned-model equality to the frozen policy before HTTP transmission.
2. **Real split/provenance recomputation**: outer split, cross-fit and provenance hashes must be derived from Data-Gate-qualified whole-capacitor manifests, with membership disjointness, LOCO and cross-condition checks; opaque hash equality is insufficient.
3. **Evaluator isolation**: the mock `BlindReplayService` owns `_events` in the same process. Real held-out prediction code must not share process/filesystem authority with the event/label service.
4. **Human/data/API Gates**: Benchmark-L remains blocked; Ren/Patrizi acquisition/audit is unapproved; every chat-exposed Ark key must be rotated; authenticated capability and formal spend require separate approvals.
5. **No real numerical evidence**: there are no qualified held-out target errors, rolling metrics, intervals, seeds, shadow results or RUL labels for this architecture.

## Non-blocking cleanup

- Keep legacy `budget.py` out of the formal accuracy entrypoint; future experiment commands should expose `CAPAccuracyRun` only.
- State explicitly that IF1 `76,969` applies to a numerical key while endpoint-gated RUL has one forced action.
- Preserve `review_independence=same-family` and `acceptance_status=provisional`.

## Release decision

- M0/M1/M2 mock protocol: `RELEASE_MOCK_ONLY`.
- Claim-producing data/API accuracy run: `BLOCKED`.
- RUL run: `BLOCKED` until an endpoint/event/censor Gate establishes numeric RUL eligibility.
- Paper readiness: `NOT_READY`.

