# Independent Protocol / Statistics / Architecture Adversarial Review

**VERDICT: BLOCKED**

**Review scope:** current worktree only; offline/read-only inspection of the requested protocol, registry, manifest, validator, executor, and tests. No network, API, model execution, data extraction, P2 scoring, or RUL work was performed.

## Executive conclusion

The seven previously reported specification blockers are substantially repaired at the document/schema level. In particular, the schema resource now has one valid `$id` scope with shared `$defs`; provider `FinalDecision.v1` is reference-only; A03 specialists close on one envelope; RoutePlan branches are finite and exact; roster selection evaluates full workflows; late responses are declaratively orthogonal to terminal closure; and the tier machine now requires both Holm rejections and the exact Bonferroni component-bound crossings.

Release cannot pass, however, because the hash-pinned “machine authority” validator/executor does not enforce several of those contracts. Concrete offline counterexamples are accepted today: a wrong-candidate route, a malformed identity, unrelated final-decision parent hashes, an A02 median with only one valid worker, a cross-candidate proposal, and an ACTIVE final output containing a malformed forecast. Invalid/absent w4 input raises instead of producing the frozen `ERROR_FALLBACK`. Slot/attempt/late-event closure invariants are also declarative only and the schemas admit impossible state combinations. These defects can change candidate qualification, failure/deadline rates, prediction hashes, and the confirmatory ITT output, so they are blocking rather than documentation polish.

## Status of the seven prior blockers

1. **Schema `$id` / `$defs` scope — CLOSED.** `artifact_schemas` is one Draft 2020-12 resource with `$id=urn:plan-a:ArtifactSchemas.v1`, shared `$defs`, no nested `$id`, and all local references resolve. The pinned canonical schema-resource hash matches.
2. **FinalDecision payload authority — STRUCTURALLY CLOSED, EXECUTABLY BLOCKED BY B-01/B-02.** The schema has 14 closed reference-only branches and no payload. The local executor nevertheless does not bind a decision to the actual parent artifacts/cell and does not validate all selected outputs.
3. **A03 single-envelope closure — CLOSED AT SCHEMA/GRAPH LEVEL.** w2/w3 each emit one `A03SpecialistOutput.v1`; the envelope binds both child hashes; w4 names the route plus two envelope hashes.
4. **RoutePlan R00/provider/assignments — CLOSED AT SCHEMA/STATIC-REGISTRY LEVEL, EXECUTABLY BLOCKED BY B-01.** Eight exact branches exist; provider R00 is rejected by the route helper. The helper still accepts the wrong candidate and malformed identity because it never applies the pinned instance schema/cell contract.
5. **Roster full-workflow / undefined role loss — CLOSED AT PROTOCOL LEVEL.** A01 enumerates homogeneous mappings; A02/A03 enumerate all ordered injective four-model mappings; every mapping runs the full four-slot workflow under inner whole-unit evaluation; qualification precedes MASE and the lexicographic roster tie is fixed. Exact integer manifests remain intentionally unresolved and API execution remains prohibited.
6. **Late response as immutable orthogonal event — DECLARATIVELY CLOSED, EXECUTABLY BLOCKED BY B-03.** `LATE_DISCARDED` is no longer a replacement terminal state, but there is no schema/transition validator for `LateResponseEvent.v1` or immutable closure update.
7. **Holm rejection versus exact Bonferroni bounds — CLOSED.** There are exactly seven fixed primary slots and 20 unique components. The 20 declared IDs equal the union of primary components. `tier_mapping` explicitly requires the relevant Bonferroni one-sided crossings in addition to the required Holm composite rejections and forbids calling the bounds Holm CIs.

## Blocking findings

### B-01 — The pinned validator/executor does not enforce the pinned artifact schemas, cell identity, parent lineage, or full-key output contract

Evidence:

- The registry declares itself machine authority and claims instance-sensitive validator scope at `PLAN_A_ARCHITECTURE_REGISTRY.json:7-40`.
- `validate_route_plan` (`architecture_registry.py:341-358`) checks only the top-level key set and route tuple. It does not validate the pinned JSON Schema, `candidate_id`, identity fields, schema hash, or expected parent set.
- `validate_final_decision` (`architecture_registry.py:409-429`) checks the decision discriminator and only that three parent strings are distinct. It never checks that those hashes equal the ordered w1/w2/w3 durable closure outputs supplied to the executor.
- `_proposal_bundle` and the selection paths (`architecture_registry.py:432-439, 588-595`) do not validate candidate, role, identity, parent hashes, exact entry structure, planned-key coverage, or even the selected direct bundle before returning an ACTIVE result.
- `execute_final_decision` accepts `parents` independently of `decision.parent_artifact_hashes`; the current unit-test fixture itself uses arbitrary `5*64`, `6*64`, `7*64` hashes (`test_vfps_architecture_registry.py:102-112`).

Reproduced counterexamples with the current public functions:

```text
ROUTE_WRONG_CANDIDATE_ACCEPTED
FINAL_MALFORMED_IDENTITY_ACCEPTED
UNRELATED_PARENT_HASHES_EXECUTED_ACTIVE
A02_ONE_WORKER_MEDIAN_AND_CROSS_CANDIDATE_ACCEPTED_10.0
MALFORMED_SELECTED_PROPOSAL_EMITTED_ACTIVE
```

This is not cured by the schemas merely existing: no code path in `architecture_registry.py` performs full instance validation before semantic validation/execution, and this module is the hash-pinned validator/local executor.

Required correction:

1. Add a single hash-pinned instance-validation entry point over the published schema resource (or an equivalently complete local implementation), and call it for every RoutePlan, proposal/failure, A03 envelope/children, FinalDecision, and FinalOutput.
2. Pass an expected sealed cell context and ordered expected parent records into validation. Require exact generation/fold/origin/request/data/schema identity equality, exact candidate/slot/role mapping, and `parent_artifact_hashes == [hash(w1 closure output), hash(w2 closure output), hash(w3 closure output)]` in the frozen order.
3. Before ACTIVE commit, validate the selected/aggregated direct bundle against the exact planned-key manifest, duplicate-key rule, finite/ordered quantiles, confidence enum, target/unit domain, and candidate identity. A hash alone is not a coverage check.
4. Add adversarial tests for wrong candidate/role/identity/schema hash, unrelated/reordered parent hashes, cross-cell/cross-candidate parents, missing/duplicate/extra planned keys, malformed quantiles, and non-finite/out-of-domain values.

### B-02 — Local aggregation/finalization contradicts the frozen registry and is not deterministic under equivalent inputs

Evidence:

- The registry freezes `A02 median_valid_workers_minimum = 2` and worker order `[w1,w2,w3]` (`PLAN_A_ARCHITECTURE_REGISTRY.json:1696-1702`). The implementation builds the set from caller insertion order and rejects only zero valid workers (`architecture_registry.py:603-613`). Thus `A02_MEDIAN_VALID_WORKERS` succeeds with one worker.
- Reversing the insertion order of the same two valid parent mappings produces an identical numerical payload but reversed `source_artifact_hashes` and therefore a different canonical `FinalOutput.v1` hash. This violates the frozen reproducibility order.
- The registry freezes invalid decision behavior as `COMMON_ERROR_FALLBACK` (`PLAN_A_ARCHITECTURE_REGISTRY.json:1685,1703,1729`), and `FinalOutput.v1` has an `ERROR_FALLBACK` branch (`1033-1100`). The executor implements only a valid `FinalDecision`; missing/invalid selected parents raise `ArchitectureRegistryError` and no public finalization path emits the required error fallback. Offline reproduction: `ABSENT_W1_RAISES_NO_ERROR_FALLBACK_ArchitectureRegistryError`.
- Every returned output is stamped `finalization_trigger_type=VALID_FINAL_DECISION` (`architecture_registry.py:645-656`); the two frozen error-trigger types are unreachable.

Required correction:

1. Enforce the exact A02 minima separately: at least two valid workers without N0, and at least one valid worker with N0.
2. Iterate only in the frozen `[w1,w2,w3]` order and produce deterministic source-hash order independent of mapping insertion.
3. Implement one deterministic finalizer that accepts either a schema-valid w4 decision or the typed w4 failure/invalid-decision artifact. Operational validation failures must commit the exact common `ERROR_FALLBACK` with the correct trigger type/hash; internal invariant/program failures must make the formal run invalid rather than silently fabricate success.
4. Validate the emitted `FinalOutput.v1` and test every decision code, all minimum-worker boundaries, both error triggers, deterministic parent-order permutations, and exact fallback bytes/hashes.

### B-03 — Slot closure, attempt accounting, and late-response immutability are not mechanically enforced

Evidence:

- `WorkerFailure.v1` and `SlotClosure.v1` are open across their cross-field semantics (`PLAN_A_ARCHITECTURE_REGISTRY.json:1102-1250`). They admit, for example, `NOT_STARTED_DEADLINE` with `provider_send_attempts=1`, `TIMEOUT_CONSUMED` with zero sends, `FINISHED_VALID` with `WorkerFailure.v1`, or a failure state with `ForecastProposal.v1`. Candidate/slot/role/output-schema combinations are likewise not discriminated.
- The static state-machine prose specifies the intended mappings (`1732-1810`), but `validate_registry` checks neither closure instances nor state/attempt/artifact consistency.
- `LateResponseEvent.v1` is only a descriptive object at `1812-1826`; it is absent from the artifact schema resource and has no append-only transition/reducer or test. The only code check is that a string is absent from terminal states and `closure_mutation_allowed` is false (`architecture_registry.py:322-326`). That does not prove the original closure hash/output cannot be replaced.

These fields directly define the candidate qualification gates and the primary/secondary error-free completion, fallback, and deadline endpoints. An impossible but schema-admitted closure can therefore alter model selection and confirmatory statistics.

Required correction:

1. Make closure/failure schemas discriminated by terminal state, with exact `provider_send_attempts`, failure code, output schema, and candidate-slot-role branch mappings.
2. Add `LateResponseEvent.v1` to the pinned schema resource, binding the exact pre-existing terminal closure hash and allowing no new send/prediction/closure authority.
3. Implement and test an immutable transition validator/reducer: one terminal closure per slot, no terminal-to-terminal rewrite, late events append only, and exact 0/1 attempt conservation.
4. Include impossible-combination, duplicate closure, late-overwrite, and orphan-event adversarial tests in the bound test file.

## Statistics and leakage review

No additional fatal multiplicity or outer-label leakage was found in the reviewed frozen specification:

- Candidate/roster selection is nested inside outer-training units; no global winner is selected from outer OOF results.
- Any required fold with no qualified ARCH1 candidate blocks ARCH1 generation-wide; Ck no-match is not repaired by subset-fold inference.
- Holm operates on seven fixed composite IUT p-values, including mechanical `p=1` slots; Bonferroni bounds operate on the fixed 20-component universe without alpha recycling.
- The tier mapping requires both rejection and simultaneous-bound evidence, so the former prose/machine disagreement is closed.
- The development count is finite and formula-complete but honestly unresolved; no API authority exists until a fully enumerated integer manifest and human approval.

Residual nonblocking risks to settle in later approved artifacts are the exact P2 margins/seeds/degenerate-bootstrap handling, exact inner split and roster manifests, integer `N_dev`, authenticated P3 roster, fault manifest, and final statistics executable. They remain visibly unresolved and do not currently masquerade as executable values.

## Offline verification performed

- `pytest -q tests/test_vfps_architecture_registry.py`: **8 passed**. These tests do not cover the blocking counterexamples above.
- Every file hash listed by `PLAN_A_PRESEAL_BUNDLE_MANIFEST.json`: **matched**.
- Canonical pins: `EXPERIMENT_PLAN.md=df968d...b6d2`, `round-3-refinement.md=d4d40b...f110`: **matched**.
- Patrizi and Ren existing `ARTIFACT_HASHES.sha256` graphs: **all entries passed** when checked within their bundle directories.
- Architecture schema resource, validator, and test hashes: **matched the pinned contract**.

The preseal state remains correctly marked `UNAPPROVED / NO_EXECUTION_AUTHORITY`; no result or execution claim is warranted.