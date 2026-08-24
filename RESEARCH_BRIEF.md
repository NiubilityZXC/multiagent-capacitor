# Research Brief: Agentic Online Capacitor Prognostics

**Frozen direction date:** 2026-08-24  
**Workflow:** ARIS research pipeline  
**Decision policy:** `AUTO_PROCEED=false`, human checkpoints required

## Problem Statement

Design and numerically evaluate a multi-agent online forecasting system for capacitor degradation. At every rolling origin, using only causally available history, the system should predict future capacitance/capacity, ESR, SOH, RUL when the endpoint is identifiable, predictive intervals, and anomaly risk. Real held-out predictive accuracy is the primary objective; architecture novelty, cost, calibration, and auditability are secondary constraints.

The method comparison must include all of the following as distinct experimental arms:

1. specialized numerical/statistical forecasters without an LLM;
2. a single LLM that directly emits multi-horizon numeric forecasts;
3. homogeneous and heterogeneous multi-agent LLM systems that directly emit forecasts;
4. LLM agents that select, combine, diagnose, or boundedly correct specialized numerical models;
5. a dynamically routed, typed, counterfactual-verification architecture with a numerical fallback.

## Problem Anchor

The target contribution is not generic prompting or a renamed fixed multi-agent topology. The central research question is:

> Can a maturity-aware agent graph whose typed proposals are tested by executable counterfactual replay improve strictly causal, held-out capacitor forecasts over both direct LLM agents and strong specialized numerical models under matched call, token, and latency budgets?

## Public Data and Current Eligibility

- NASA Stress-2 is verified as a six-column surrogate dataset with 11 observations per column. It supports only a small trajectory/scorer sanity benchmark. Physical-unit independence is not proven. Capacity-threshold outcomes comprise five interval-censored events and one unknown-termination tail; ESR threshold crossings are absent.
- The 5.04 GB electrical-stress pack has passed partial integrity and schema audits, but capacitance/ESR target definitions, physical identity, termination semantics, and transient alignment are not fully established. Benchmark-L target and RUL modeling remain blocked until their estimand-specific Data Gates pass.
- No endpoint, target, or unit identity may be inferred from filenames, file lengths, final rows, or other future-only metadata.
- If an endpoint is not identifiable, RUL must be emitted and scored as `NA`, never replaced by a guessed exact label.

## Evaluation Constraints

- Outer leave-one-capacitor-out and leave-condition-out testing where the data support them.
- Inner-only model, feature, prompt, router, and calibration selection.
- Strict rolling-origin replay; predictions must be durably committed before target reveal.
- Common origin/target/horizon keys across methods; failures remain explicit.
- Immutable prediction, maturity, routing, API-attempt, and evaluation ledgers with code/data/protocol/config hashes.
- Numeric proper scores only. LLM self-scores, LLM judges, prose plausibility, or explanations cannot replace target error, calibration, survival likelihood, cost, or reliability measurements.
- Any feature, Skill, prompt, agent node, model, or routing policy is admitted only through the frozen Eval and shadow validation.
- All architecture comparisons must match physical API attempts, allowed input information, output-token ceilings, deadline policy, and retry policy; matched-token and matched-call controls are both required.

## Candidate Agent Backbones

The available Ark AgentPlan registry reported by the user includes the following model identifiers, to be verified online before use:

- `doubao-seed-2.0-mini`
- `glm-5.3`
- `deepseek-v4-flash`
- `kimi-k3`
- `glm-5.2` (reported as approaching retirement; not a preferred formal dependency)
- `kimi-k2.7-code`
- `minimax-m3`
- `deepseek-v4-pro`

The non-secret AgentPlan base URL is `https://ark.cn-beijing.volces.com/api/plan/v3`. API credentials must be supplied only through a locally exported environment variable after rotation. Credentials must never enter prompts, shell command text, repository files, manifests, logs, or papers.

## Scientific Hypotheses

- **H1 — direct-agent value:** A direct LLM or multi-agent forecaster can numerically outperform at least one simple trajectory baseline, but is not assumed to beat a tuned specialized ensemble.
- **H2 — hybrid value:** Typed LLM reasoning over diagnostics and specialized forecasts can improve held-out proper loss over the same numerical experts without LLM assistance.
- **H3 — architecture value:** Executable counterfactual verification plus maturity-only credit is necessary for any hybrid gain; matched-budget removal of verification or maturity gating should reduce performance or safety.
- **H4 — safe routing:** A value-of-information router can reduce API usage while remaining non-inferior to always-on agents and never materially underperforming the frozen numerical fallback in prespecified worst-fold tests.

All hypotheses are falsifiable. A null or negative result must be retained and may become the paper's empirical finding if it is robust.

## Compute and API Constraints

- Prefer CPU-compatible numerical baselines and cached deterministic preprocessing.
- Pilot at most three architecture candidates, each no more than two GPU hours and within a predeclared API-call budget.
- Run no paid or real API experiment before the Gate 1 human checkpoint, credential rotation, online model-registry verification, and a secret-leak/failure-injection review.
- A provider outage, malformed response, timeout, late response, or budget exhaustion must return the frozen numerical forecast and be counted in the attempt ledger.

## Workspace and GitHub Reproducibility

- All source code, protocols, compact result summaries, paper sources, and reproducibility manifests must be created and executed under `/home/user/multiagent-capacitor`.
- The configured GitHub remote is used for checkpoint synchronization after secret scanning, artifact-size checks, tests, and a clean diff review.
- Raw datasets, extracted 5 GB archives, API credentials, virtual environments, caches, and provider response material that could contain secrets are never committed.
- Large immutable numeric ledgers may be summarized by content hashes and compact tables when committing them directly would make the repository impractical; the manifest must state what is local-only and how it can be reproduced.
- Every push is a reproducible checkpoint, not evidence that a scientific gate passed.

## Publication Goal and Claim Ceiling

The goal is a reproducible high-quality paper, not a guaranteed venue outcome. A method paper requires a verified architectural contribution that survives matched-budget controls and node/edge ablations. If it does not, the maximum defensible contribution is an audited empirical study of when direct and hybrid LLM agents help or harm online capacitor prognostics. Stress-2 alone cannot support broad claims; final claims must match the number of independent devices, conditions, identifiable endpoints, and successfully completed external validations.

## Non-Goals

- Claiming novelty for generic fixed role prompts, majority vote, ordinary debate, or an LLM-weighted ensemble alone.
- Using LLM prose or self-confidence as ground truth, reward, calibration, or evaluation.
- Fine-tuning on held-out capacitor prefixes or using future suffixes, terminal metadata, or full-life normalization.
- Reporting unavailable RUL labels or converting unknown termination into administrative right censoring.
- Calling an architecture publishable before numerical pilots, independent review, and strict held-out testing.
