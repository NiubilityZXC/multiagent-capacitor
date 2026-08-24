# Multi-Agent Capacitor Prognostics

An ARIS-managed research project for strictly causal, online prediction of capacitor degradation using both direct LLM agents and hybrid LLM-plus-specialized numerical models.

## Research question

Can a maturity-aware agent graph with typed, executable counterfactual verification improve held-out capacitor forecasts over strong numerical forecasters and direct LLM-agent baselines under matched call, token, latency, and information budgets?

The target outputs are multi-horizon capacitance/capacity, ESR, SOH, RUL when the endpoint is identifiable, predictive intervals, and anomaly risk. Numerical accuracy on unseen capacitors is the first priority. LLM explanations and self-scores are never substitutes for target error or calibration.

## Required experimental arms

- numerical/statistical models without LLMs;
- one LLM directly producing numerical forecasts;
- homogeneous and heterogeneous multi-agent LLM direct forecasting;
- LLM agents selecting or combining numerical experts;
- bounded LLM residual correction around a numerical anchor;
- typed counterfactual arbitration with a frozen numerical fallback.

All arms use strict rolling-origin replay, outer leave-one-capacitor-out and cross-condition tests where identifiable, common prediction keys, and immutable prediction/maturity ledgers.

## Current status

- ARIS Idea Discovery and method refinement are complete at a provisional empirical-study framing. CAP-ACT is an architecture comparison, not a pre-claimed method novelty.
- The typed M0–M3 harness now implements causal packets, direct and hybrid arm authority, durable one-attempt slots, typed Ark request/evidence binding, runner-owned token limits, blind rolling reveal, a same-UID process-separated evaluator, crash-safe REVEAL recovery, per-key maturity and endpoint-gated `RUL_NA`.
- Fresh post-fix review returned `RELEASE_MOCK_ONLY` for the Ark/integrated harness and narrowly scoped `RELEASE_LOCAL_PROCESS_BOUNDARY` for the honest-launcher evaluator. Neither label means production security, real API readiness or forecast accuracy.
- Stress-2 is available only as a small column-surrogate sanity benchmark. It cannot establish physical-unit generalization.
- The 5.04 GB electrical-stress pack has partial integrity/schema audits, but its target, physical-identity, alignment, and outcome gates still block Benchmark-L model and RUL claims.
- Ren and Patrizi acquisition/audit scopes are frozen in [the P1 decision packet](refine-logs/DATA_ACQUISITION_GATE.md), but neither new payload may be downloaded before its explicit human approval.
- No real Ark API request has been made in the current architecture run.
- Ark authenticated discovery and at most 15 tiny synthetic capability probes are separately specified in [Gate-2](refine-logs/ARK_AGENTPLAN_GATE2_PROTOCOL.md). Any key exposed in chat must first be rotated and injected outside the repository; capability approval does not authorize capacitor prediction.

See [RESEARCH_BRIEF.md](RESEARCH_BRIEF.md), [the latest idea report](idea-stage/IDEA_REPORT.md), and [the output manifest](MANIFEST.md).

## Local validation

Use the project environment:

```bash
.venv-audit-cap/bin/python -m pytest -q tests
```

Validated CAP project suite on 2026-08-24: `204 passed in 21.18s`; fresh reviewers independently obtained `204 passed`. `py_compile`, `git diff --check` and a non-echoing repository secret scan also passed. These are synthetic implementation checks, not target-accuracy evidence.

## Ark AgentPlan

The non-secret base URL is:

```text
https://ark.cn-beijing.volces.com/api/plan/v3
```

Never place a real API key in this repository or a command argument. Rotate any key exposed in chat, then inject it from a local shell or secret manager:

```bash
export ARK_BASE_URL='https://ark.cn-beijing.volces.com/api/plan/v3'
export ARK_API_KEY='ROTATED_VALUE_FROM_SECRET_MANAGER'
```

The provisional model registry is [configs/ark_agentplan_models.json](configs/ark_agentplan_models.json). Formal experiments require an authenticated account-level model snapshot and synthetic strict-schema smoke tests first.

The repository now contains an offline, transport-injected `/responses` adapter. It does not own credentials or networking. A future P3 concrete transport must prove that SDK/HTTP retry, redirect and replay are disabled; one adapter method invocation is not yet evidence of one physical HTTP request. Full direct/action/IF response-schema registry generation also remains a pre-P4 task.

## Evaluator boundary

The local evaluator holds the hidden suffix in a spawned process and releases each next point only after a durable checkpoint is verified. HMAC-framed IPC, launch-configuration binding, early-FINALIZE preflight and authenticated journal heads are covered by adversarial tests. Predictor and evaluator still share UID and filesystem, so coordinated rollback, TOCTOU, client-process loss and generation-global scoring require a stronger external authority before formal confirmatory runs.

## Data and result policy

Raw archives, extracted large MAT files, credentials, virtual environments, caches, and reproducible high-volume row ledgers remain local. Git tracks source code, frozen protocols, compact metrics, reports, hashes, seals, and reproduction metadata. A GitHub checkpoint means the repository is synchronized; it does not mean a scientific gate passed.

## Claim policy

No result is promoted by prose judgment. New features, prompts, agent nodes, tools, and model candidates must pass the frozen Eval, strict time splits, rolling replay, held-out-unit tests, and shadow validation. If the architecture does not beat strong controls, the defensible output becomes an audited negative empirical study rather than an invented method win.
