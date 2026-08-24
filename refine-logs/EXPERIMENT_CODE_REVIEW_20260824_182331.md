# CAP-ACT Experiment Code Review — M3 Offline Provider and Evaluator

**Time**: 2026-08-24 18:23:31 +08:00
**Review protocol**: ARIS `experiment-bridge`, pre-implementation threat review → two fresh read-only reviews → repair → two post-fix re-reviews
**Reviewer family / independence**: `openai` / `same-family`; all acceptance is `provisional`
**Network, credentials, data, accuracy runs**: none

## Layered release decision

| Layer | Verdict | Exact scope |
|---|---|---|
| Ark adapter | `RELEASE_MOCK_ONLY` | Offline construction, local response verification, typed persistence and failure injection only. No concrete authenticated HTTP transport was used. |
| Evaluator | `RELEASE_LOCAL_PROCESS_BOUNDARY` | Honest trusted-launcher, same-machine address-space separation with authenticated local audit and REVEAL recovery. Not a security or production permission boundary. |
| Integrated M3 harness | `RELEASE_MOCK_ONLY` | Synthetic protocol development only. P1/P2/P3/P4 scientific execution remains blocked. |
| Forecast accuracy / RUL | `BLOCKED` | No qualified capacitor rows, authenticated API calls, held-out losses, intervals or RUL labels were produced. |
| Paper | `NOT_READY` | No numerical result-to-claim evidence exists. |

## Reproduction evidence

Executor command:

~~~text
PYTHONDONTWRITEBYTECODE=1 .venv-audit-cap/bin/python -m pytest -q \
  -p no:cacheprovider tests
~~~

Result: `204 passed in 21.18s`.

Fresh post-fix reviewers independently reported:

- Ark focused: `101 passed`; canonical full: `204 passed`.
- Evaluator focused: `48 passed`; full: `204 passed`.
- `py_compile`, `git diff --check` and a path-only secret-pattern scan passed; no real key was found in the repository.

These results prove only the tested local contracts. They do not prove remote API behavior or prediction quality.

## Implemented architecture

### Direct LLM and LLM-plus-specialized-model path

`CAPAccuracyRun` is the single formal entrypoint for direct numeric LLM arms and typed hybrid arms. `ArkProviderAdapter` receives an injected, secret-owning transport and constructs one stateless `/responses` request. The persisted `ArkProviderEvidenceEnvelope` contains typed, canonical policy, budget, request contract, binding manifest and invocation audit. Runner close and ledger replay independently rebuild and cross-check:

- arm, policy, prompt, response schema, decode and provider rules;
- numerical registry, verifier, fallback and grammar hashes;
- capability snapshot, requested/returned model and one-call budget;
- STARTED attempt, deadline, usage, response content and ephemeral request/response hashes.

Raw request bytes, raw response bytes and the raw provider response ID are not persisted. Missing usage remains a valid `UNKNOWN`; partial, invalid, negative, boolean or over-ceiling usage consumes the slot and forces `INVALID_RESPONSE` fallback. The formal CAP verifier remains the final numerical authority, so a weak same-version adapter schema cannot commit an invalid direct or action forecast.

### Local process-separated evaluator path

Hidden events are held by a spawned evaluator process. The prediction-side client retains only the revealed prefix, public packet configuration and an opaque IPC capability. Canonical framed messages use exact schemas, HMAC, session/request identity, nonces, monotone sequences and request/response hash chains. Each REVEAL requires a complete verified `STARTED → FINISHED → prediction → execution → checkpoint` lineage and an allowed frozen policy hash.

The evaluator launch HMAC binds events plus context, causal schema, split, registry authority, packet kind, allowed policies and train-only configuration. A companion authenticated head detects journal-only complete-prefix rollback. FINALIZE now performs a side-effect-free complete-replay/access preflight before creating any ACCESS seal, maturity label or final seal.

## Adversarial findings and repair disposition

### Ark pre-fix findings

| Finding | Post-fix status |
|---|---|
| Durable provider evidence could be self-hashed but semantically wrong | **Fixed locally**: complete typed envelope, runtime reconstruction and STARTED/FINISHED post-hoc verification. |
| Formal runner accepted `97/96` output usage | **Fixed**: runner-owned validation forces `ERROR / INVALID_RESPONSE / FALLBACK`. |
| Capability was only an opaque arbitrary hash | **Partially fixed**: typed exact model-list × text-resource intersection and membership; authentic provenance still requires P3. |
| Ledger append ignored a short write | **Fixed**: write-all before state advance; injected short-write test proves provider is not sent. |
| One `transport.send()` could hide multiple HTTP sends | **Open blocker**: requires a concrete audited transport and P3 failure injection. |

Ark post-fix verdict remains `RELEASE_MOCK_ONLY` because a mock Protocol cannot prove that the eventual HTTP client disables internal retry, redirect or replay. A complete canonical per-arm response-schema registry is also not yet implemented; safety currently relies on the second formal verifier.

### Evaluator pre-fix findings

| Finding | Post-fix status |
|---|---|
| Early FINALIZE wrote hidden labels before rejecting | **Fixed**: rejection occurs before any ACCESS seal, maturity or final artifact; attack test observes zero future-label bytes. |
| Journal-only valid-prefix rollback was accepted | **Partially fixed**: authenticated companion head detects single-file rollback; synchronized rollback of journal and head remains possible. |
| Launch journal bound only hidden event bytes | **Fixed for local execution semantics**: complete launch configuration is HMAC-bound. |
| Error code came from exception class names | **Fixed**: frozen four-code allowlist, validated on both sides. |
| Malformed journal error path referenced an unbound exception | **Fixed** with a direct closed-error regression. |

Evaluator post-fix verdict is `RELEASE_LOCAL_PROCESS_BOUNDARY`, narrowly limited to an honest launcher and address-space separation.

## Remaining hard blockers

1. **Concrete Ark transport**: no authenticated transport implementation or receipt proves one physical HTTP send, zero internal retry/redirect and trusted local deadline measurement.
2. **Capability provenance**: the typed capability artifact has no real authenticated control-plane/resource snapshots or independent signature yet.
3. **Canonical arm schemas**: full direct/action/IF schema registry and permission-specific schema generation remain open; the formal verifier currently supplies the final fail-closed boundary.
4. **Evaluator authority**: predictor and evaluator share UID/filesystem. Coordinated journal+head rollback, same-UID ledger forgery, path TOCTOU and lack of WORM/evaluator signing remain unresolved.
5. **Recovery and global barrier**: whole-client loss, BOOTSTRAP/FINALIZE interruption and generation-global all-fold/all-arm scoring barrier are not implemented.
6. **Scientific data**: Ren/Patrizi payloads are not acquired or audited; Benchmark-L remains blocked; whole-capacitor splits, targets, endpoints and numerical floor are not frozen from eligible rows.
7. **Human/API gates**: every key exposed in chat is invalid until rotated. No authenticated discovery, synthetic probe or capacitor API call is authorized.

## Trace evidence

The exact prompts and reviewer responses are stored under:

`/.aris/traces/experiment-bridge/2026-08-24_run01/`

- `001`: pre-implementation threat review;
- `002` / `003`: initial Ark and evaluator reviews;
- `004` / `005`: post-fix Ark and evaluator re-reviews.

## Final handoff

The offline engineering step is complete enough to stop at the human checkpoint without losing causal protocol work. The next valid actions are either P1 data acquisition/audit or P3 authenticated synthetic capability probing after credential rotation. Neither approval authorizes P4 capacitor prediction; P4 needs a separate budget/release decision after P1/P2/P3 pass.
