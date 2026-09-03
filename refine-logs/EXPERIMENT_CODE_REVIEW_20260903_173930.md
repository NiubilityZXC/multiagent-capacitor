# CAP-ACT Experiment Code Review — Plan-A Preseal Closure Repair

**Time**: 2026-09-03 17:39:30 +08:00
**Workflow**: ARIS `experiment-bridge`
**Reviewer provenance**: `openai` same-family, independently prompted; acceptance is provisional
**Scope**: offline code and static-contract review only; no network/API/download/extraction/model/RUL/scoring.

## Verdict

`PASS_PRESEAL_PROTOCOL_ONLY / UNAPPROVED_HUMAN_GATE_REQUIRED / NO_API / NO_MODEL_RESULTS`.

This PASS closes the three preseal implementation defects found in the preceding adversarial review. It does not authorize a master seal, P2/P3/P4/P5 work, authenticated discovery, model invocation, capacitor prediction, SOH/RUL construction, or an accuracy claim.

## Reviewed repairs

1. The public workflow validator and finalizer accept only four `(SlotClosure, durable output)` records and derive all downstream parents from that durable ledger. A caller cannot pass shadow parent objects to obtain `ACTIVE`.
2. A03 `R00_DEFAULT_N0_GLOBAL` is a local derived route only. It has exactly one parent hash: the same cell's durable typed w1 `WorkerFailure.v1`; all five frozen trigger states are covered, while absent/cross-cell/wrong-hash triggers fail.
3. A `FINISHED_VALID` `ForecastProposal.v1` now performs full planned-manifest/key/order/finite/nested-quantile/domain validation before its closure is accepted. Non-finite artifacts cannot receive canonical hashes.
4. The enclosing human spec and preseal bundle manifest were refreshed to the reviewed schema, validator, test, registry, and specification bytes.

## Evidence

| Check | Result |
|---|---|
| Architecture contract tests | `31 passed in 0.72s` |
| Whole local suite, explicit file collection | `298 passed in 30.43s` |
| Preseal listed-file hash graph | `19/19 PASS` |
| Patrizi + Ren P1 internal hash lists | `29/29 PASS` |
| `validate_registry(..., verify_bound_files=True)` | PASS |
| Fresh release review | PASS, trace `002-plan-a-final-protocol-release-review-pass` |

The direct bare `pytest` command is not a valid project invocation here: it resolves the environment without pytest. The project audit virtual environment and explicit test-file collection above are the recorded reproducible commands.

## Current gate

`BLOCKED_P1_REN / PRESEAL_UNAPPROVED / NO_API / NO_MODEL_RESULTS`.

The next action still requires an explicit human decision: retain the canonical N0 claim ceiling or approve a separately specified Ren parser/extraction plan. This review supplies neither decision.
