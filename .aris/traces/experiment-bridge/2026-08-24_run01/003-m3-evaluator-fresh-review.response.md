# Fresh Post-Implementation Evaluator Review

**Review class**: fresh same-family reviewer, read-only, provisional
**Network / credential access**: none
**Product/test edits**: none
**Decision**: `RELEASE_MOCK_ONLY`
**Explicitly not supported**: production permission isolation, malicious-same-UID resistance, qualified-data accuracy, calibration, RUL, or paper performance claims.

## Audited snapshot

| Artifact | SHA-256 |
|---|---|
| `experiments/vfps_agent/evaluator_service.py` | `567bf0583c3185a80bfe66c4bcc2921465d43b27bdd8296c9284a359f76cad62` |
| `experiments/vfps_agent/replay.py` | `400c82b95fe141c360022c81e41579332bb3f672abc8bf50c1241469e4fa469a` |
| `experiments/vfps_agent/runner.py` | `3c7948bd2f01702d57b1312614b9bbe38bcddf650e012a82f05fd0c699daecf8` |
| `experiments/vfps_agent/__init__.py` | `aa41b9ef55e02fd231995781cf84f9d85db857c87f006b7e506c7b5f8575b96b` |
| `tests/test_vfps_evaluator_service.py` | `9ea50bf025746f501185cabd471f28af2c206bb5a48cf9ba438e476fcbe26da4` |
| `refine-logs/EXPERIMENT_PLAN.md` | `6527ecbba427e6e965296badcf165dfd6ef8c071d82cbdfa8d96f6cf6d6670df` |

Focused reproduction:

```text
PYTHONDONTWRITEBYTECODE=1 .venv-audit-cap/bin/python -m pytest -q \
  -p no:cacheprovider \
  tests/test_vfps_evaluator_service.py tests/test_capact_m2_runner.py

36 passed in 6.22s
```

The tests establish useful mock/local behavior, but two additional read-only diagnostics reproduced release-blocking states:

```text
EARLY FINALIZE:
FINALIZE_ERROR EvaluatorProtocolError
MATURITY_EXISTS True OBSERVED_VALUE_PRESENT True BYTES 1371

AUTHENTICATED COMPLETE-PREFIX JOURNAL ROLLBACK:
ROLLBACK_PREFIX_ACCEPTED True ORIGINAL_LINES 5 TRUNCATED_LINES 3
```

Both diagnostics used temporary directories outside the repository and made no source/test changes.

## What the implementation now proves

1. The normal client object contains the revealed prefix but no `_events` or `_state_key`, and the evaluator PID differs from the caller PID (`evaluator_service.py:947-1007`; test `test_vfps_evaluator_service.py:79-103`). This is a useful address-space separation under an honest trusted-launcher handoff.
2. IPC uses `send_bytes`/`recv_bytes`, canonical JSON, exact top-level key sets, bounded frames, request/response HMACs, monotone sequence numbers, nonces, and request/response chains (`evaluator_service.py:47-104, 518-636, 1019-1083`).
3. Authenticated reorder, request-ID reuse, nonce reuse, unauthenticated mutation, duplicate checkpoint, and exact last-response replay are exercised (`tests/test_vfps_evaluator_service.py:214-313`).
4. The REVEAL crash points intentionally covered by the implementation work locally: ACCESS has been fsync'd before the injected post-operation crash, and a COMPLETED record has been fsync'd before the injected pre-reply crash (`evaluator_service.py:843-894`; tests `:166-211`). Exact pending REVEAL recovery is deterministic and ACCESS is not appended twice.
5. `verify_durable_checkpoint` is materially stronger than the previous partial check. It verifies typed attempt/prediction/execution/checkpoint ledgers, exactly one STARTED/FINISHED/prediction, lineage, committed prediction semantics, exact execution key set, checkpoint references, evaluator-recomputed origin/packet hashes, and an allowed policy hash (`runner.py:831-969`; `replay.py:102-118, 242-303`).
6. The honest FINALIZE path seals prediction evidence, ACCESS, maturity, the access barrier, and the final run artifact (`replay.py:305-385, 394-537`). This remains mock/local evidence, not scientific accuracy evidence.

## Blocking findings

### B1 — Early FINALIZE writes hidden future labels before it fails

**Severity**: critical
**Status**: reproducible

An authenticated client may request FINALIZE after BOOTSTRAP whenever no previous FINALIZE exists; the session phase check does not require the hidden stream or frozen origin schedule to be complete (`evaluator_service.py:834-839`). FINALIZE immediately calls `seal_access_and_mature` (`evaluator_service.py:653-655`). That method:

1. seals ACCESS (`replay.py:310-313`);
2. derives labels from any `origin+horizon < len(self._events)` and writes `observed_value` into `MATURITY_LEDGER.jsonl` (`replay.py:315-367`);
3. only afterward calls `verify_complete_run`, which rejects a label whose event was never causally revealed (`replay.py:369`; verifier at `:475-502`).

The error is therefore fail-closed too late. The reproduced run finalized after one context-origin prediction without revealing the suffix; FINALIZE returned `EvaluatorProtocolError`, but a persistent maturity ledger containing `observed_value` already existed. Because evaluator and prediction client currently share UID and run-directory authority, the prediction plane can read that hidden label after the rejected operation.

This directly violates the M2 kill rule that prediction must not gain future evidence (`EXPERIMENT_PLAN.md:278`) and prevents `RELEASE_LOCAL_PROCESS_BOUNDARY`.

**Required fix**:

- perform a side-effect-free preflight proving the complete frozen origin/reveal schedule and access barrier before opening any label;
- never write maturity labels into a prediction-readable directory;
- make evaluator-private maturity construction atomic, and release only approved post-generation artifacts after the global seal;
- add an early-FINALIZE adversarial test that asserts no maturity file, label bytes, access seal, or hidden-derived count is created on rejection.

### B2 — A valid authenticated journal prefix can roll state backward

**Severity**: critical
**Status**: reproducible

Journal verification rejects empty/torn files and verifies every remaining record's hash/HMAC chain (`evaluator_service.py:219-293`). It has no external monotone head, final state seal, or evaluator-owned expected sequence outside the journal. Consequently, truncating the five-line journal after one completed REVEAL to the earlier three-line, newline-complete BOOTSTRAP prefix was accepted at restart. Each retained record remained a valid HMAC-authenticated prefix.

This is a rollback attack, not byte tampering. The existing tamper test mutates a byte (`tests/test_vfps_evaluator_service.py:316-328`) and does not cover removal of complete authenticated transitions.

**Required fix**:

- anchor the latest journal head/sequence in a separate evaluator-owned monotonic store, WORM/sealed artifact, or equivalent rollback-resistant authority;
- cross-bind that head to ACCESS and checkpoint heads;
- reject any restart whose journal is a valid but stale prefix;
- test complete-record truncation at every COMPLETED boundary, not only partial-line corruption.

### B3 — Session state binds only the event bytes, not the frozen launch manifest

**Severity**: high

`hidden_binding_tag` is HMAC over `event_payloads` only (`evaluator_service.py:760-770`). It does not bind:

- context length;
- causal schema;
- split/provenance seal;
- registry and planned-key manifest;
- packet kind;
- allowed policy set or policy generation;
- normalization, conditions, train-only summaries, or diagnostics;
- protocol/run identity.

`EvaluatorSupervisor.restart` normally reuses its Python attributes (`:1265-1331`), but the durable journal cannot independently detect mutated/reconstructed restart configuration. The test covers a different hidden stream (`tests/:156-164`) only.

**Required fix**: HMAC one canonical immutable launch manifest containing all items above; persist its tag in every journal record and final run seal. Allowed policy authority should be a typed manifest with one explicitly frozen generation, not merely an arbitrary non-empty tuple of opaque hashes (`evaluator_service.py:1395-1402`).

### B4 — SHA-only shared ledgers do not authorize the supervisor and remain TOCTOU-sensitive

**Severity**: high

The checkpoint verifier is semantically stronger, but it reads predictor-writable, SHA-only ledgers (`runner.py:861-969`). `read_verified_ledger_records` verifies a path and then reopens/rereads it (`ledger.py:760-768`), while `_secure_read` itself performs `lstat` followed by a path open (`ledger.py:169-192`). A same-UID client can replace a regular file between checks or rebuild a fully self-consistent hash chain. SHA detects accidental mutation but does not authenticate the writer.

The evaluator journal records the request/checkpoint hash and response hash, but the final run seal does not bind the evaluator journal head, full request history, hidden binding tag, or supervisor authority (`replay.py:370-385`). Thus the journal cannot currently disprove post-reveal replacement of scientific ledgers/ACCESS with a different self-consistent history.

**Required fix**:

- evaluator/supervisor-owned checkpoint ingest or an unforgeable supervisor capability over the complete checkpoint lineage;
- same-fd/inode verify-and-read, fixed directory descriptor, ownership/mode/link-count checks, and immutable snapshots;
- final seal must bind evaluator journal head, launch-manifest tag, ordered request/checkpoint history, and ACCESS/science ledger heads;
- adversarial tests for regular-file rename swap and an entirely self-consistent forged ledger.

Until then this is not malicious same-UID or filesystem isolation.

### B5 — Client protocol state and unresolved request are memory-only

**Severity**: high

Sequence, request/response heads, seen response nonces, pending request bytes, prefix, capability, and session ID live only in `EvaluatorClient` memory (`evaluator_service.py:950-1006`). Recovery works only when the exact same client object survives and `EvaluatorSupervisor.restart` replaces its connection (`:1183-1192, 1265-1294`). If the prediction/client process itself crashes or the client object is lost, there is no supported reconstruction path for the pending request, causal prefix, or protocol chain.

This falls short of the plan's crash-recovery intent and is not covered by tests, which kill only the evaluator while retaining the client object.

**Required fix**: a supervisor-mediated, label-blind client recovery handshake that reconstructs prefix and chain from authenticated durable state without exposing suffix; test client loss before send, after send, after ACCESS fsync, after COMPLETED fsync, and after response receipt.

### B6 — Per-run FINALIZE is not the required global generation barrier

**Severity**: high for formal outer-CV use

The experiment plan requires every outer fold to be sealed before any outer score is opened and declares post-score changes a new generation (`EXPERIMENT_PLAN.md:76-78, 322`). Current FINALIZE is per run and writes raw label values into the shared run directory. Even the honest path can expose one fold's labels before later folds/policies finish, enabling adaptive reuse outside the IPC state machine.

**Required fix**: a generation-level manifest/barrier covering every fold/arm/origin before any maturity label or score becomes prediction-plane readable. Prefer scorer-owned private labels and release aggregates only after this barrier.

### B7 — Error schema is not closed

**Severity**: medium, blocking the claimed exact closed protocol

Evaluator errors serialize `type(exc).__name__` (`evaluator_service.py:897-923`), and the client checks only the OK/error-code-null relationship; it does not require a string from a frozen allowlist (`:1053-1072`). This is bounded compared with persisting exception messages, but it is not a closed schema.

**Required fix**: frozen error enum, exact type/allowlist validation, no exception-class-derived protocol values, plus one test per mapped failure.

## Non-blocking findings and claim limits

1. **Supervisor handoff is procedural**: documentation correctly says only the client may enter the prediction plane (`evaluator_service.py:10-13, 1200-1202, 1381-1386`), and the supervisor does not retain the stream. However the trusted caller supplies `events` and receives both handles. No OS/API mechanism prevents it from retaining events or handing over the supervisor. This is acceptable only as an explicitly documented honest-launcher assumption after the blockers above are fixed.
2. **Same UID and filesystem**: `spawn` provides address-space separation, not UID, mount, `/proc`, ptrace, or filesystem permission isolation. Do not call this production permission isolation. Separate UID/container/namespace tests are absent.
3. **BOOTSTRAP/FINALIZE crash availability**: constructor recovery accepts an interrupted REVEAL only and refuses a finalized session (`evaluator_service.py:201-217`). This is fail-closed, but BOOTSTRAP/FINALIZE crash recovery and result retrieval are not provided. It blocks a broad crash-resilient claim, though not causal integrity if no label has escaped.
4. **Journal partial write**: a non-newline torn append is rejected (`:219-221`), which is safe but unrecoverable. No fault test covers short/torn journal writes.
5. **Process cleanup**: supervisor uses bounded join/terminate (`:1260-1263, 1333-1337`) but does not assert the process is dead after the final timeout, and tests do not check orphan children or leaked descriptors. `_replace_connection` does not deterministically close an old connection when `_closed` is already true (`:1183-1192`).
6. **Deadlock/resource tests absent**: message polling is bounded client-side, but there is no adversarial oversized-frame, stuck filesystem, repeated restart, process-leak, or deadlock suite.
7. **Cross-session test scope**: the named cross-session test mutates an existing frame without recomputing HMAC (`tests/:263-279`). Code binds session ID inside HMAC, but a genuine separately created session-frame test is still desirable.
8. **No accuracy evidence**: all exercised events, provider outputs, policies and labels are fixtures. `36 passed` proves protocol behavior only. P1/P2/P3/P4/P5/P6 remain outside this review and no numeric scientific claim follows.

## Acceptance disposition

| Candidate decision | Verdict | Reason |
|---|---|---|
| `RELEASE_LOCAL_PROCESS_BOUNDARY` | **REJECT** | Early FINALIZE leaks hidden labels; authenticated-prefix rollback and shared-ledger authority remain unresolved. |
| `RELEASE_MOCK_ONLY` | **ACCEPT (provisional)** | Honest-path process separation, framed authenticated IPC, exact REVEAL replay, and complete checkpoint verification are useful mock/local harness evidence. |
| `BLOCKED` | **Not selected for the mock artifact** | Meaningful mock progress exists, but all formal data/API/scientific execution remains blocked by the experiment gates and the evaluator blockers above. |

## Final decision

`RELEASE_MOCK_ONLY`

The implementation must not be described as production permission isolation, adversarial same-UID security, completed M2 scientific release, or prediction-accuracy/RUL evidence. The first repair priority is B1 (label-before-barrier leak), followed by B2/B3/B4 (rollback and durable authority), then B5/B6 (client/global-generation recovery and sealing).