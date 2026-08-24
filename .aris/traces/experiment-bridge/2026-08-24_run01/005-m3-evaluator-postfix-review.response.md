# M3 Evaluator Post-Fix Fresh Review

**Review mode:** ARIS `experiment-audit`, fresh post-fix, offline/read-only review of product code and tests. No network, credential, environment-variable, source, or test mutation was used. Temporary directories were used only for runtime adversarial reproduction.

**Decision:** `RELEASE_LOCAL_PROCESS_BOUNDARY`

This decision is deliberately narrow: the implementation now supports an honest trusted-launcher, same-machine, address-space causal boundary for the local evaluator harness. It is **not** a secure or production permission boundary, is not resistant to a malicious same-UID/shared-filesystem actor, is not a generation-global experiment controller, and supplies no qualified-data accuracy, calibration, RUL, or paper-result evidence.

## Audited snapshot

| Artifact | SHA-256 |
|---|---|
| `experiments/vfps_agent/evaluator_service.py` | `810ad82bf4ce764e673a5801bb47abae5c219b41335e42b5bfd6c42a6cecab2d` |
| `experiments/vfps_agent/replay.py` | `30aafb9172e561b9a4ed9b3130edaf5d5042ecbf58fd2f6513a6634bcf9ffe97` |
| `experiments/vfps_agent/runner.py` | `75661ea868099acdbdef75d7faa59ab3231a289bf5e6ad574628f4e685591ac4` |
| `experiments/vfps_agent/ledger.py` | `4eac2c4fe2e50ca56b727144ecdc72f8fcd0861a1c0bc98d7a345dcf02d2b068` |
| `experiments/vfps_agent/__init__.py` | `aa41b9ef55e02fd231995781cf84f9d85db857c87f006b7e506c7b5f8575b96b` |
| `tests/test_vfps_evaluator_service.py` | `ba64d47201824d29fddc7f10530e93c60f0937ec1d2a8f08f0ae031b9a272456` |
| `refine-logs/EXPERIMENT_PLAN.md` | `6527ecbba427e6e965296badcf165dfd6ef8c071d82cbdfa8d96f6cf6d6670df` |
| original fresh-review trace | `44f9bb598f458ddbd08dc6ace594891ee6661921769998d1f2bd22d0fda059e5` |

## Reproduction evidence

Final-snapshot focused and full runs:

```text
PYTHONDONTWRITEBYTECODE=1 .venv-audit-cap/bin/python -m pytest -q \
  -p no:cacheprovider tests/test_vfps_evaluator_service.py tests/test_capact_m2_runner.py
48 passed in 8.32s

PYTHONDONTWRITEBYTECODE=1 .venv-audit-cap/bin/python -m pytest -q \
  -p no:cacheprovider tests
204 passed in 24.12s
```

Independent reproductions of the original B1/B2 attacks produced:

```text
B1_ERROR isolated evaluator rejected the committed operation: FINALIZE_REJECTED
B1_ACCESS_UNCHANGED True
B1_POST_ARTIFACTS {'ACCESS_LEDGER.seal.json': False,
 'MATURITY_LEDGER.jsonl': False,
 'MATURITY_LEDGER.seal.json': False,
 'RUN_SEAL.json': False}
B1_CLIENT_PREFIX [1.0, 0.99, 0.98]

B2_SINGLE_PREFIX_REJECTED True ORIGINAL 5 TRUNCATED 3
B2_SYNCHRONIZED_PAIR_ROLLBACK_READY_ACCEPTED True

UNKNOWN_ERROR_CODE_REJECTED evaluator error code is outside the closed allowlist
```

The early-FINALIZE diagnostic used one committed origin followed by a prediction-phase seal, without revealing the suffix. Rejection left ACCESS byte-identical and created neither ACCESS seal nor maturity/final artifacts. Thus the previously reproduced future-label persistence is gone on this path.

## Original B1-B7 disposition

| ID | Post-fix status | Evidence and residual boundary |
|---|---|---|
| **B1 early FINALIZE label leak** | **FIXED** | `BlindReplayService.seal_access_and_mature` now rejects an incomplete reveal schedule before prediction verification, ACCESS sealing, maturity creation, or final sealing (`replay.py:305-331`). The direct reproduction above confirms zero post-barrier artifacts and no suffix added to the client. The protocol exposes only `FINALIZE_REJECTED`, not the internal cause (`evaluator_service.py:1031-1057`). |
| **B2 authenticated-prefix rollback** | **PARTIALLY FIXED** | The companion authenticated head binds journal byte length/SHA, record count, final state hash, launch binding, and capability (`evaluator_service.py:267-321`); it is rewritten after every fsynced append (`:511-560`). A journal-only valid-prefix truncation is now rejected. However, restoring both journal and head to the same older valid pair is accepted through READY, as independently reproduced. Both files share the same directory/rollback domain and there is no external monotonic anchor. A crash between journal fsync and head replacement is fail-closed but may be unrecoverable. |
| **B3 incomplete launch binding** | **FIXED for launch execution semantics** | The launch HMAC now covers events, context, causal schema, split provenance, registry authority hashes, packet kind, allowed policy hashes, normalization, conditions, train summaries, and diagnostics (`evaluator_service.py:129-162, 881-905`). Restart drift is tested (`tests/test_vfps_evaluator_service.py:180-232`). Session/capability are independently journal-bound. Test-only fault hooks, filesystem authority, and generation-global orchestration are not part of this scientific configuration binding. |
| **B4 shared SHA ledgers / TOCTOU / writer authority** | **UNRESOLVED** | `verify_durable_checkpoint` provides strong semantic lineage and policy/origin/packet binding (`runner.py:937-1075`) and all regression tests pass. It does not authenticate the scientific-ledger writer against a malicious same-UID actor. `read_verified_ledger_records` still verifies a pathname and then rereads it (`ledger.py:796-805`), leaving a rename/swap TOCTOU window, and an actor with shared write authority can construct a new self-consistent SHA chain. The final seal remains unkeyed and does not provide an independent monotonic/WORM authority. |
| **B5 client pending/state durability** | **UNRESOLVED** | Sequence/hash heads, seen nonces, exact pending bytes, capability, and revealed prefix remain memory-only (`evaluator_service.py:1084-1140, 1223-1242`). Evaluator crash recovery works only while the exact client object survives and the supervisor replaces its connection (`:1403-1431`). Loss of the client process/object has no label-blind reconstruction protocol. |
| **B6 generation-global barrier** | **UNRESOLVED** | Per-run FINALIZE now has the correct local pre-write barrier and complete seal order (`replay.py:305-401`), but it still writes raw maturity labels per run. Nothing here enforces the plan's requirement that every outer fold/arm be sealed before any outer label/score is opened (`EXPERIMENT_PLAN.md:77`). This remains blocking for formal confirmatory outer-CV use, though not for the narrow local process boundary. |
| **B7 open error schema** | **FIXED** | Error values are a frozen four-code enum (`evaluator_service.py:105-112`); response construction rejects unknown status/code combinations (`:670-704`), exception classes/messages are not serialized (`:1031-1057`), and the client independently enforces the allowlist and status/code relationship (`:1169-1220`). A direct unknown-code probe failed closed. |

The briefly observed malformed-journal regression is also fixed in this final snapshot: `_verify_records` now binds `exc` and raises the intended closed `EvaluatorProtocolError` (`evaluator_service.py:323-332`), with a direct regression at `tests/test_vfps_evaluator_service.py:400-407`.

## Protocol and recovery coverage

- **Hidden suffix/client boundary:** the client retains only its revealed prefix and execution configuration; it has no event store or state key. Normal handoff is therefore useful address-space separation. The launcher still receives hidden events and both handles, so handoff is procedural, not OS-enforced.
- **Framed IPC:** exact schemas, canonical JSON, bounded `send_bytes`/`recv_bytes`, HMAC, session/request identity, nonce uniqueness, monotone sequence, request chain, response chain, and deterministic exact-response replay are enforced (`evaluator_service.py:628-704, 725-757, 934-1029, 1153-1221`). Reorder, ID/nonce reuse, unauthenticated tamper, duplicate checkpoint, and exact transport replay tests pass (`tests/test_vfps_evaluator_service.py:283-382`).
- **REVEAL durability:** ACCESS-fsync-before-COMPLETED and COMPLETED-fsync-before-reply crash paths replay the exact pending request idempotently without a second ACCESS append (`tests/test_vfps_evaluator_service.py:235-280`). This did not regress.
- **Checkpoint/policy authority:** the evaluator recomputes the causal packet, checks the entire STARTED→FINISHED→prediction→execution→checkpoint lineage, exact execution-key set, origin and packet hashes, and membership in the frozen allowed policy-hash set (`runner.py:937-1075`). The unfrozen-generation test still rejects (`tests/test_vfps_evaluator_service.py:118-137`).
- **FINALIZE ordering:** complete replay and side-effect-free access preflight precede ACCESS seal; sealed prediction/access evidence precedes maturity construction; complete verification precedes the final run seal (`replay.py:305-401`).

## Remaining blockers for stronger claims

1. **Coordinated journal/head rollback:** a valid historical two-file snapshot passes authenticated-head verification. Resistance requires an independently administered monotonic/WORM/remote anchor, or an equivalent rollback domain not writable/restorable with the journal. The current head proves consistency, not freshness.
2. **Same-UID/shared-filesystem adversary:** process separation does not provide UID, namespace, mount, ptrace, `/proc`, ownership, or writer isolation. SHA seals and advisory locks do not establish supervisor authorship. A same-fd/inode snapshot verification design and evaluator-owned ingest would reduce TOCTOU but still would not substitute for a permission boundary.
3. **Client-loss recovery:** only evaluator-process crashes with a surviving client are covered. Whole-client loss, supervisor loss, and restart after BOOTSTRAP/FINALIZE interruption lack a supported recovery handshake.
4. **Generation-global scientific barrier:** per-run raw labels may become readable before all folds/arms are frozen. A private scorer plus a generation manifest/barrier is required before formal outer-test use.

These four items prohibit any description as secure isolation, production-ready permission isolation, malicious-local resistance, fully crash-complete evaluation, or completed M2 scientific release.

## Nonblocking limitations within the narrow decision

- Partial/torn journal writes and journal/head disagreement fail closed, but recovery/repair is manual. Malformed canonical journal input now fails through the intended protocol exception.
- Supervisor shutdown uses bounded join/terminate, but there is no adversarial stuck-filesystem, repeated-restart leak, orphan-process, descriptor-exhaustion, or deadlock campaign. Passing tests establish ordinary cleanup only.
- READY authenticates session/PID/nonce but not the journal sequence/head. Consequently a synchronized rollback can be accepted at READY and only conflict with a surviving client's next sequence later.
- The named cross-session behavior is cryptographically session-bound, but there is no separate-connection malicious same-UID security claim.

## Acceptance decision

| Candidate | Verdict |
|---|---|
| `RELEASE_LOCAL_PROCESS_BOUNDARY` | **ACCEPT, narrowly scoped** — B1/B3/B7 are fixed; journal-only rollback is rejected; IPC, exact REVEAL recovery, checkpoint/policy verification, and honest FINALIZE ordering pass focused and full tests. |
| `RELEASE_MOCK_ONLY` | Not selected — the prior critical causal-label leak and single-file authenticated-prefix rollback have been materially repaired enough to support the explicitly honest local address-space boundary. |
| `BLOCKED` | Not selected for this local harness — meaningful causal protocol behavior is demonstrated. Formal experiment execution and every stronger security/production claim remain blocked by the limits above. |

**Final decision: `RELEASE_LOCAL_PROCESS_BOUNDARY`.** No numerical prediction-quality conclusion follows from this review.