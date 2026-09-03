# M3.1 Offline Release Evidence

**Time**: 2026-08-31 17:58:50 +08:00  
**ARIS workflow**: `experiment-bridge`  
**Verdict**: `PASS_OFFLINE_HONEST_LAUNCHER_SCOPE / NO_API / NO_ACCURACY_CLAIM`

## Release boundary

The M3.1 implementation is released for offline protocol development and pre-seal review. It does not authorize authenticated discovery, Ark calls, development calls, capacitor prediction, P2 fitting/scoring, RUL construction/scoring, outer evaluation, unseal, or a paper performance claim.

The verified integrity claim is limited to the documented honest-launcher, same-machine boundary. It is not a hostile same-UID or remote-server attestation claim.

## Closed prior blocker

The former split-brain generation-unseal blocker is mechanically closed:

1. the only admitted artifact path is the normalized absolute `<frozen-plan-parent>/GENERATION_JOINT_UNSEAL.json`;
2. issuance requires the exact complete admitted supervisor/cell/session set;
3. the statistics executable SHA-256 is pinned by the generation plan and rechecked at issuance;
4. every supervisor receives and verifies the same generation-wide `joint_unseal_hash`;
5. alternate path, wrong statistics hash, partial set, duplicate issuance, tamper, bad HMAC, and cross-cell authorization fail before label-bearing writes.

## Executed checks

| Check | Result |
|---|---|
| Local authoritative suite | `275 passed in 30.11s` |
| Independent review focused suite | `124 passed in 13.35s` |
| Independent review full suite | `275 passed in 30.71s` |
| `compileall` for experiment/test modules | PASS |
| all tracked audit/refinement JSON parse | PASS |
| `git diff --check` | PASS |
| canonical plan pins | PASS |
| Patrizi P1 `ARTIFACT_HASHES.sha256` from its bundle directory | 14/14 PASS |
| Ren P1 `ARTIFACT_HASHES.sha256` from its bundle directory | 15/15 PASS |

The hash-list commands must run from their respective bundle directories because their entries are relative. A prior repository-root invocation produced path-resolution errors; rerunning from the correct directories verified every entry and did not change any evidence.

## Reviewed source hashes

| File | SHA-256 |
|---|---|
| `experiments/vfps_agent/ark_provider.py` | `8a219070027420767c3e92c894b781f5627fdb97c9c859d4ad260df98d6bacfe` |
| `experiments/vfps_agent/canonical.py` | `b3d00372b3bdecb39569d41c3dbd1b706b6f1f66f2dcacff3a48db029b2dacc5` |
| `experiments/vfps_agent/evaluator_service.py` | `45fc51138fc97bf0dafabc6c1e51c3e11e4b1d16861a97bceb4d3b80cc352392` |
| `experiments/vfps_agent/runner.py` | `187fd6f91df844e46ed4ce72aafea96f4221e519b8f0583aa193f2ba0292c307` |
| `experiments/vfps_agent/ark_https_transport.py` | `2bdfd7f10d359064f54a8181ce94e205616f77e222713ca73d4729abe4a38a98` |
| `experiments/vfps_agent/generation_barrier.py` | `3240967f9586f066aa535e0440b1e8c56ab8321cb84d4acf3d53f00a8d0b53c8` |
| `experiments/vfps_agent/response_schema.py` | `ea6411f0ae7c698c0ffafc662411fabcb1c9186e6b792ef8d87b8bd8c209147c` |
| `experiments/vfps_agent/architecture_registry.py` | `08e263690c59c83e54bdcc1b06e318e1acebe63d8b60109944ec8b6667f6a951` |

Canonical upstream remained byte-identical:

- `EXPERIMENT_PLAN.md`: `df968d2e7ba33748043e547165143d9247358afca573946f3dde573c8c04b6d2`
- `round-3-refinement.md`: `d4d40b0a7e3f5c9030bfe80e5ede3d059673c3b3c96122c9cf050097aa54f110`

## Secret scan

The path-only in-scope scan returned four matches, all classified without persisting or printing a real credential:

1. a PHMForge GitHub URL substring: regex false positive;
2. the intentional synthetic `Authorization: Bearer ...` canary in `tests/test_vfps_ark_provider.py`;
3. the `benchmark-l` schema-version substring: regex false positive;
4. the `frozen-risk` idea-ledger substring: regex false positive.

No user Ark credential is present in the reviewed repository artifacts.

## Independent review

Fresh secondary Codex review verdict: `PASS`. Exact trace:

`.aris/traces/experiment-bridge/2026-08-31_run01/003-m3.1-final-release-review-pass/`

Reviewer provenance is recorded as same-family/unattested; therefore the verdict is independent in context, not independently attested across model families.

## Residual non-blocking engineering risks

- A hostile process with access to supervisor private state, signing keys, or ancestor paths is outside the threat model.
- The future scoring entrypoint must verify its executable bytes against the sealed statistics hash immediately before execution.
- The one-shot transport receipt proves the local call path, not remote server receipt or execution.
- A crash after exclusive joint-unseal publication may require abandoning/resealing the generation; availability recovery is intentionally fail-closed.

## Current gate

`BLOCKED_P1_REN / PRESEAL_UNAPPROVED / NO_API / NO_MODEL_RESULTS`.

## 2026-09-03 Plan-A preseal closure addendum

The preseal architecture contract received a second independent offline review after three executable lineage findings were repaired. The current audited pins are schema resource `a18a53a3a635d5cbc8a01b7dc3e2fbfb8a888a69e8bf126f27e614d54e3273aa`, validator `36e9f718f6a84bc8316e128969ae683334d2db9c439fc29e1836b4e2d17a6dd7`, and contract tests `78e41ec3767d6126151421e4552d91829800d40cad9dd17e72ff4be22963568a`. The final review verified 19/19 preseal listed-file hashes, 29/29 P1 internal hashes, and 31 focused architecture tests; explicit-file full local collection passed 298 tests.

The finalizer now derives its sole parents from the same four durable closure records; A03 R00 binds the same cell's typed durable w1 failure; and valid forecast closures perform manifest/key/numeric semantic validation before acceptance. This is a `PASS_PRESEAL_CONSISTENCY_ONLY`, not scientific execution authority. The current gate is unchanged: `BLOCKED_P1_REN / PRESEAL_UNAPPROVED / NO_API / NO_MODEL_RESULTS`. Trace: `.aris/traces/experiment-bridge/2026-09-03_run01/002-plan-a-final-protocol-release-review-pass/`.
