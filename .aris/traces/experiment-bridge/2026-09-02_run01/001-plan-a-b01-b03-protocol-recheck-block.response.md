# BLOCKED

## Independent B-01/B-03 adversarial recheck

**Scope.** Read-only review of the final current bytes requested by the prompt. I ran only offline Python/pytest checks. I did not use network/API access, extract data, score P2, run a model, or construct RUL.

**Reviewed final pins.** Validator `af1760908f15622537ffabef22fbc9e45b8ec3266aeec5a9a6368c9450a8b37f`; bound tests `052ec4e8aaea51fd1023fc7485c36b1d087dc682657d6bafddcc99e580990bb0`; artifact-schema resource `099fe2e58b5b6cd2624cc5704a027b9deeb3e2b35394ef98bd7438b1174aa30c`; registry file `3fbd48141583d9030db27d7d8735ab0f4ec7cef0af2becc53c08611226a46925`.

The former direct counterexamples for wrong route candidate/identity, unrelated hashes passed directly to `validate_final_decision`, malformed ACTIVE forecast bundles, A02 one-worker no-N0 median, insertion-order instability, impossible state/attempt/schema tuples, exact duplicate late events, orphan late events, and zero-send late events are now rejected. The A02 minima and source order are correctly enforced, invalid decisions and typed w4 failures share one local finalizer, and same-tree focused tests pass (`18 passed`). Those repairs are real.

Release remains blocked because the workflow-level durable-parent ledger is not closed. The current public validators allow a cell to validate and emit `ACTIVE` from artifacts that are not the artifacts named by that cell's four terminal closures. This defeats the exact ordered parent-lineage requirement and also leaves the A03 local-default transition without a mechanically required router-failure predecessor.

## Blocking executable counterexamples

### 1. `validate_workflow_closures` accepts shadow parents that differ from the durable closure outputs, and the same shadow parents produce `ACTIVE`

`validate_workflow_closures` checks that the four closure records have unique slot IDs, then validates each record against that record's caller-supplied `parent_artifacts` (`architecture_registry.py:881-898`). It never builds a canonical `{slot_id: output_artifact}` map from the four records and never requires each record's parent object/hash to equal the corresponding earlier record's durable `output_artifact_hash`.

I reproduced this with A01:

1. Durable w1/w2/w3 records used forecasts with offsets `-1` and `+1` and their matching critique.
2. The w4 record was given a second, non-durable w1/w2/w3 set with offsets `+20` and `+22`, plus a matching critique and decision.
3. `validate_workflow_closures(...)` accepted all four records.
4. The durable w1 closure hash was `a5738a862a986d9f96e8bf4751e94cab74952fcffe2f5cf13b62e862bf747a17`, while the accepted w4 first-parent hash was `bbdef8e9794e6a3a2c9a7a0e82644e8f3e63f7f036030db82a528ede53421e59`.
5. `execute_final_decision(...)` on those shadow parents returned `execution_status=ACTIVE` with point `30.0`.

Minimal reproducer shape:

```python
records = [
    (closure(aw1), aw1, {}),
    (closure(aw2), aw2, {}),
    (closure(aw3), aw3, {"w1": aw1, "w2": aw2}),
    (closure(shadow_decision), shadow_decision,
     {"w1": bw1, "w2": bw2, "w3": bw3}),
]
validate_workflow_closures(registry, context, records)  # accepted
execute_final_decision(
    registry, context,
    {"w1": bw1, "w2": bw2, "w3": bw3},
    n0=n0, decision=shadow_decision,
)  # ACTIVE
```

This is a direct B-01 bypass: the decision's three hashes are internally consistent with the objects handed to the finalizer, but they are not the ordered hashes of the cell's actual durable closure outputs. It is also a B-03 bypass because “one terminal closure per slot” does not constrain downstream consumption to those terminal artifacts.

**Required fix:** make one workflow-level ledger the sole parent authority. Derive parent objects/hashes from the four closure records inside the validator/finalizer; reject any supplied parent that is not byte/hash-equal to the corresponding durable record. Add a test that reproduces the two-parent-set example and requires rejection before `ACTIVE`.

### 2. A03 `R00_DEFAULT_N0_GLOBAL` can produce `ACTIVE` without any typed w1 failure or durable router-failure transition

The registry says R00 is local-only and is generated after w1 failure. The slot-closure schema simultaneously requires an A03 w1 `FINISHED_VALID` closure to contain a provider `RoutePlan.v1`, while a failed w1 closure contains `WorkerFailure.v1`. Thus R00 is a derived local transition artifact, not the durable w1 slot output.

The finalizer does not require that transition evidence. `_validate_parent_artifacts` accepts an R00 object in `parents["w1"]` merely because its `route_origin` makes `provider_output=False` (`architecture_registry.py:785-791`). With R00-compatible specialist envelopes and a valid w4 decision, I called the public finalizer with no w1 failure artifact or closure and obtained:

```text
UNTRIGGERED_R00_STATUS ACTIVE
UNTRIGGERED_R00_POINT 10.0
```

This permits the local fallback route independently of every `router_failure_transition.trigger_states` value and gives w4 a parent hash that cannot equal the w1 failed closure's output hash. It is both a B-01 lineage violation and a B-03 state-transition violation.

**Required fix:** represent the local-route derivation explicitly and hash-bind it to the exact durable w1 `WorkerFailure.v1` closure/output (or define another single unambiguous ledger representation). The finalizer must reject R00 unless that bound failed closure exists in the same workflow ledger. Add tests for untriggered R00, valid R00-after-each-frozen-failure-state, and R00 whose failure/closure hash belongs to another cell.

### 3. `FINISHED_VALID` ForecastProposal closures admit semantic-invalid planned-key output

For generic valid artifacts, `validate_slot_closure` performs JSON-schema and context/role validation only (`architecture_registry.py:862-868`). It does not call `_proposal_bundle`, so it does not enforce the sealed manifest hash, full planned-key equality, quantile nesting, or target/unit domain before accepting terminal state `FINISHED_VALID`.

I reproduced two accepted closures:

```text
nesting ACCEPTED   # q10=20, point=10
manifest ACCEPTED  # planned_key_manifest_hash changed to 9*64
```

The finalizer later rejects such a parent before `ACTIVE`, so the narrow ACTIVE-output guard is repaired. But the durable state machine still records an invalid direct numeric output as `FINISHED_VALID`, which can corrupt completion/failure/deadline qualification endpoints and contradicts the declared direct-output and terminal-artifact contract.

**Required fix:** in the `FINISHED_VALID` ForecastProposal closure branch, apply the same `_proposal_bundle`/sealed-manifest semantic validation used by the finalizer, including exact ordered full-key coverage, finite/nested quantiles, and target/unit domain. Add closure-level tests for missing/duplicate/extra keys, wrong manifest hash, non-finite/nonnested values, and out-of-domain values.

## B-02 status

B-02 is closed for the reviewed paths. The executor freezes A02 worker order as w1/w2/w3, requires two valid workers without N0 and one with N0, produces insertion-order-independent source hashes, and maps invalid decisions plus typed w4 failures to the exact common `ERROR_FALLBACK`. A missing raw w4 object is appropriately a formal invariant error unless represented by the required typed w4 failure; I did not treat that as a new bypass.

## Late-event residual risk

The tightened late-event reducer correctly requires a sent `TIMEOUT_CONSUMED` closure, validates existing events, enforces strict monotonic append order, preserves the closure, and rejects exact duplicate event objects. A residual ambiguity remains: the same `late_response_sha256` with a later timestamp is accepted as a second event. I reproduced `SAME_LATE_RESPONSE_HASH_ACCEPTED 2`. This is non-blocking if the contract intentionally records repeated observations of the same response; otherwise uniqueness should be defined over `(original_terminal_closure_hash, late_response_sha256)` and tested. It does not change this verdict because the durable-parent and R00 bypasses above are independently blocking.

## Offline verification

- `PYTHONDONTWRITEBYTECODE=1 .venv-audit-cap/bin/python -m pytest -q -p no:cacheprovider tests/test_vfps_architecture_registry.py` -> **18 passed**.
- Every file hash in `PLAN_A_PRESEAL_BUNDLE_MANIFEST.json` matched at the time of review.
- The executable shadow-parent, untriggered-R00, semantic-invalid-closure, and repeated-late-response probes above were run in-memory only.

No release PASS is warranted until findings 1 and 2 are mechanically closed and adversarially retested. Finding 3 must also be closed if `FINISHED_VALID` feeds any qualification or operational endpoint, as the current protocol indicates.