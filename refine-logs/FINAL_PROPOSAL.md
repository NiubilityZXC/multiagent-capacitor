# Research Proposal: Do LLM Agents Improve Online Capacitor Prognostics?

**Subtitle:** A Strictly Causal, Matched-Budget Study of Direct and Tool-Grounded Forecasting  
**Frozen refinement:** 2026-08-24 15:04:45 CST  
**Positioning:** empirical architecture study; not a new routing, program-synthesis, or multi-agent learning method

## Problem Anchor

> Can a maturity-aware agent graph whose typed proposals are tested by executable counterfactual replay improve strictly causal, held-out capacitor forecasts over both direct LLM agents and strong specialized numerical models under matched call, token, and latency budgets?

The operational question is whether direct numeric LLM forecasting, a one-call LLM controller with bounded numerical authority, or a matched multi-call model roster improves past-only whole-capacitor rolling forecasts over a strong numerical-only champion. Outcomes are forecast error, interval quality, failure-retaining coverage, anomaly risk, latency, tokens, attempts, and cost.

`maturity-aware` means that a sealed policy is evaluated only when independently determined outcomes mature; it does not mean online adaptation on outer-test labels. The implementation uses deterministic metamorphic or perturbation testing rather than causal “counterfactual” language unless a genuine intervention and identification design is later introduced.

## Technical Gap and Study Thesis

Prior direct-LLM, tool-augmented, routing, ensemble, and multi-agent time-series work makes a generic Agent-method novelty claim untenable. The unresolved empirical question is narrower: after freezing future availability, whole-device splits, numerical experts, packet bytes, physical attempts, requested ceilings, fallback, and mature scoring, does changing the LLM's numerical authority change held-out capacitor risk, reliability, and cost?

The study thesis is:

> Byte-accounted information controls, one-attempt execution, typed authority, deterministic local execution, prediction-before-reveal, and sealed whole-unit outer cross-validation can distinguish value from raw LLM forecasting, numerical-expert information, authority restriction, finite-action control, repeated sampling, and heterogeneous model rosters without attributing gains to extra calls, retries, fallback, or leakage.

The dominant contribution is the controlled empirical factorization. The supporting artifact is a reproducible CAP-ACT harness with strict arm-specific schemas, exact common fallback, durable attempt/prediction ledgers, blind maturity, fault qualification, and claim-bounded analysis.

### Explicit non-claims

- Action routing, fusion, tool use, reflection, and multi-agent decomposition are not claimed as new.
- Per-origin `IF` syntax does not enlarge the realized action class.
- Hash ledgers, Graph Engineering, policy qualification, or fallback do not prove predictive accuracy.
- D4-X versus D4-H is a sealed heterogeneous-roster effect unless constituent-model ability is separately controlled.
- No LLM, hybrid, multi-agent, ESR, SOH, or RUL benefit is asserted before eligible numerical results exist.

## Architecture Factorization

### Primary one-call authority block

| Arm | Causal input | Agent output authority | Local numerical authority |
|---|---|---|---|
| `N0` | no API | none | outer-training numerical champion |
| `D1-RAW` | raw causal packet | complete numeric forecast bundle | strict parse or common fallback only |
| `D1-PACKET` | hybrid packet | complete numeric forecast bundle | strict parse or common fallback only |
| `H1` | hybrid packet | one frozen numerical-model ID | deterministic execution |
| `RF1` | hybrid packet | one frozen fusion-template ID | deterministic convex fusion |
| `RC1` | hybrid packet | identity/shift/inflate around frozen `b_star(target,h)` | deterministic correction/calibration |
| `ACT1` | hybrid packet | one ID from the unified 19-Action set | deterministic compile and execute |
| `ENUM-ACTION` | deterministic train-derived causal features | no API | sealed finite-action risk selector |
| `IF1` | hybrid packet | known-condition branch artifact | representation/metamorphic ablation only |

`D1-RAW` directly satisfies the pure-LLM forecast question. `D1-PACKET` sees the same numerical candidates and training-only summaries as the hybrid arms but remains free to emit numbers. This isolates the value of expert information from bounded tool authority as far as the observable architecture permits. `D1-PACKET` versus `ACT1` remains an architecture-package contrast because output serialization, parsing surface, and fallback probability also differ.

All primary API arms make one physical attempt per logical slot under `accuracy_v1`, with no accuracy retry, a common workflow deadline, common requested ceiling, and intention-to-treat fallback. Requested resources and realized tokens/latency are reported separately.

### Minimum multi-call block

The eventual scientific package pre-seals two four-attempt direct controls:

- `D4-H`: four stochastic outputs from the same authenticated backbone;
- `D4-X`: one output from each member of a four-model authenticated roster.

Both use the same compact numeric schema and componentwise median aggregation, followed by deterministic interval/nesting validation and the common fallback on whole-bundle failure. The four outputs form one origin-level cluster, not four independent observations. The comparison identifies a roster package effect, not pure diversity. One-call performance is reported for every constituent model; stronger diversity language additionally requires matched homogeneous-repeat controls for each constituent.

`ACT4`, sequential reflection, hierarchy, debate, and dynamic routing are appendix add-ons only after the primary one-call block and D4 controls are pre-sealed and scientifically eligible. Parallel and sequential arms must share the same physical-attempt and total-token envelope but may not be described as latency-matched when their attainable wall times differ.

## Causal Packets and Information Accounting

### `OriginPacketRaw.v1`

- opaque origin, policy, and split hashes;
- availability cutoff, target, horizon, known schedule, and target availability mask;
- canonical past-only short window and long-history summaries;
- missingness and deployment-available context;
- outer-training-only normalization metadata.

### `OriginPacketHybrid.v1`

The Raw fields plus:

- all frozen numerical candidate point/quantile bundles;
- outer-training cross-fitted unit-macro error summaries;
- train-defined disagreement, OOD, slope, curvature, and gap bins;
- Action registry, fallback, numerical-model, and transformation hashes.

The hybrid data section is byte-identical for `D1-PACKET/H1/RF1/RC1/ACT1/IF1`; instructions and response schemas are separately hashed. Direct arms use one compact fixed-order numeric JSON representation. Reports include data bytes, total request bytes, provider input tokens, requested output ceilings, realized output/reasoning tokens when available, local CPU, and end-to-end latency.

Packets exclude future suffixes, EOL or termination information, final sequence length, held-out error/rank, raw path/header, private device identity, full-life normalization, and future realized timestamps. Suffix and identity perturbation tests require committed packets and predictions to remain unchanged.

## Exact Primary Action Authority

For each target–horizon key:

```text
BaseAction := EMIT(model_id)             # 6
            | FUSE(weight_template_id)  # 5
            | FALLBACK                  # 1

ActionPrimary := BaseAction
               | SHIFT(b_star(target,h), s), s in {-1.0,-0.5,+0.5,+1.0}
               | INFLATE(b_star(target,h), q), q in {1.25,1.5,2.0}
```

`b_star(target,h)` is exactly the common `FALLBACK`: the `N0` champion bundle selected within the outer-training units by a frozen nested whole-unit rule. No arm receives a private fallback. The primary union therefore contains `12 + 4 + 3 = 19` Actions and is the literal union of H1's six model actions, RF1's five fusion actions, and RC1's `b_star` identity plus seven transforms.

`SHIFT` adds `s * scale_train(target,h)` to the point and all quantiles. The residual-scale estimator, unit weighting, zero/nonfinite behavior, domain checks, and hash are frozen from allowed training units. `INFLATE` leaves the point unchanged and expands each predeclared central interval around it. It is uncertainty recalibration, not location correction. Missing, nonfinite, nonnested, unit-inconsistent, or domain-invalid bundles fail as a whole to the common fallback. Transforms cannot nest.

An Agent-selected `FALLBACK` is `DELIBERATE_FALLBACK`; timeout, transport, schema, verifier, deadline, or crash fallback is `ERROR_FALLBACK`. They commit the same numbers but remain different reliability states.

The appendix-only `ACT-COMP96` applies the seven transforms to any of 12 BaseActions. It is paired with `ENUM-COMP96` and cannot support the primary authority-isolation claim.

## IF and Deterministic Selector Controls

`IF1` uses 225 predeclared known predicates and unequal branches from the 19 Actions. Its canonical syntax count is

\[
19 + 225\times19\times18 = 76{,}969,
\]

but its realized per-origin quotient is 19. It tests schema/elicitation, invalidity, and fixed-artifact metamorphic behavior only; it is not a new expressive policy class.

`ENUM-ACTION` mechanically evaluates all 19 Actions on development-unit cross-fitted records, computes unit-macro losses, and seals a deterministic global/stratum backoff score, minimum-unit rule, cluster standard error, complexity penalty, feature bins, and lexicographic tie break. It receives no online label. It is called a pessimistic selector unless an actual confidence construction and multiplicity rule are frozen. Development label use and local compute are reported; no claim of pretraining-compute parity is made.

## Sealed Whole-Unit Evaluation

The confirmatory design is sealed outer whole-unit cross-validation, not a globally untouched shadow cohort.

1. Protocol development uses synthetic, mock, fault, Stress-2 sanity, and schema-only metadata to freeze prompts, packets, actions, budgets, metrics, failure semantics, and confirmatory contrasts.
2. For each outer held-out capacitor, every numerical fit, normalization, calibration, `b_star`, risk table, bin, feature, and fallback artifact uses only the remaining outer-training capacitors. Any selection uses whole-unit inner CV.
3. All outer-fold split manifests, registries, and commands are sealed and released as one batch before any outer score is opened. No prompt, arm, threshold, or hypothesis changes during the batch.
4. Origins are aggregated within physical capacitor before paired unit-level inference. Rolling origins, API calls, and model replicates never inflate the independent sample count.
5. Any post-release change creates a new exploratory generation. Multiplicity procedures do not repair adaptive reuse.

A wholly separate corpus that never influences the primary policy or claim freeze may be reported as a truly untouched external-domain stress test, but it is not pooled with the primary outer-CV estimate.

### Common planned-key state machine

Before any arm call, all arms receive the same ordered key manifest: origin, target, horizon, interval levels, availability mask, and maturity rule. Every key begins `PLANNED`, has exactly one execution state in `{ACTIVE, DELIBERATE_FALLBACK, ERROR_FALLBACK}`, and later exactly one maturity state in `{MATURED, NEVER_MATURED}`. A globally ineligible endpoint is protocol-level `NA`, not an arm failure or Action.

Primary loss uses every common `MATURED` planned key, including fallbacks. Active-only error is secondary and selection-biased. `NEVER_MATURED` counts remain visible and receive no fabricated label.

## Prediction-Before-Reveal and Fault Contracts

```text
reveal causal prefix
-> generate frozen numerical candidates and canonical packet
-> durably commit STARTED attempt
-> make at most one provider attempt
-> record FINISHED or consumed-ambiguous failure
-> strict parse and deterministic execute, or common fallback
-> durably commit prediction and marker
-> reveal next event only after marker verification
-> independent maturity service opens eligible labels and scores
```

An unmatched `STARTED` consumes the attempt and falls back; it is never resent in `accuracy_v1`. Late responses cannot overwrite fallback. Fault qualification covers suffix/identity/time leakage, missing modalities, endpoint removal, hash tamper, timeout, late response, crash recovery, ledger reorder/truncation, and secret canaries. Safety evidence and forecasting evidence are reported in separate tables.

## Data and Target Eligibility

- **Ren SCs (113 EDLC devices):** acquisition-only PASS. After raw audit, it may support derived capacitance, capacitance-SOH, and multi-step trajectories. ESR is `NA`; EOL/RUL require a separately frozen threshold and censoring gate.
- **Patrizi HSC (8 devices):** acquisition-only PASS as a separate external domain. Ah capacity, IR, and EIS require exact target conventions. One strategy per device creates perfect strategy–identity confounding.
- **Warwick:** AMBER auxiliary energy-domain stress only.
- **NASA Benchmark-L:** structural parser verification passed, but the scientific Data Gate failed; no modeling or RUL is eligible.
- **NASA Stress-2:** mock/replay/scorer sanity only.

EDLC, hybrid, electrolytic, and film-capacitor records are never pooled as exchangeable devices. Capacity, electrostatic capacitance, ESR/IR, energy, SOH, EOL, and RUL retain explicit units and endpoint definitions. Unknown or censored EOL is not scored as exact RUL.

## Claim-Driven Evaluation

### Block 1: one-call anchor

Compare `N0,D1-RAW,D1-PACKET,H1,RF1,RC1,ACT1,ENUM-ACTION` on common matured planned keys. Metrics include unit-macro MASE/MAE/RMSE, 50/80/90 interval score and coverage, failure/fallback and active coverage, physical attempts, requested/realized tokens, latency, and cost-quality Pareto results.

### Block 2: authority and representation

- `D1-RAW` vs `D1-PACKET`: expert-packet package effect;
- `D1-PACKET` vs `ACT1`: free numeric vs typed-authority architecture package;
- `H1/RF1/RC1` vs `ACT1`: restricted permission subsets vs their 19-Action union;
- `ACT1` vs `ENUM-ACTION`: LLM controller vs a deterministic selector on the same Actions;
- `ACT1` vs `IF1`: action-only vs explicit branch representation.

### Block 3: minimum multi-call controls

Report `D4-H` and `D4-X` under the same four-attempt envelope and fixed median aggregator. Compare each with its one-call constituent controls. Treat the output as repeat-ensemble and roster evidence unless stronger controls justify a topology or diversity claim.

### Block 4: safety and leakage qualification

Run deterministic invariance, crash, timeout, ledger-integrity, fallback, and secret-canary tests independently of accuracy results.

## Falsifiable Hypotheses and Claim Ceiling

- If no API arm beats `N0` under unit-level paired analysis and credible power, conclude that the tested LLM architectures add no forecast value under the frozen conditions—not that LLMs never help prognostics.
- If `D1-RAW` beats `N0`, support only direct-LLM value for the named target, horizons, corpora, backbones, and budget.
- If `D1-PACKET` beats `D1-RAW`, support a numerical-candidate packet package effect, not tool necessity.
- If `ACT1` beats `D1-PACKET`, `ENUM-ACTION`, and all literal subset arms with comparable coverage, support the tested typed-authority package, not a universal controller principle.
- If `ACT1` fails against `H1/RF1/RC1`, unified authority is unnecessary under the tested conditions.
- If `IF1` beats `ACT1`, support a representation effect only.
- If `D4-H` beats its one-call arm, support repeated sampling plus aggregation at four-call cost.
- If `D4-X` beats `D4-H`, support the sealed roster unless constituent ability is controlled.
- If only fallback/failure improves, claim operational reliability only.
- If a Data or API Gate remains blocked, claim only mock/fault harness implementation.

Any selected-arm positive claim uses a predeclared familywise or simultaneous rule. A well-powered multi-backbone null result with credible external scope is publishable evidence; a one-model or one-confounded-fleet null is local engineering evidence.

## Graph Engineering and Reproducibility

Graph Engineering governs data audit, Eval freeze, leakage checks, feature and model development, error diagnosis, fault recovery, zero-context review, sealed release, and claim arbitration. Nodes exchange typed, hash-addressed artifacts. Any new feature, Skill, prompt, model, arm, or target creates a new policy generation. The graph is an artifact-governance mechanism, not a source of forecast evidence or a main-method claim.

Reproduction requires immutable source URLs/digests, raw-to-canonical parsers, environment lock, split and key manifests, model/prompt/schema hashes, exact commands and seeds, attempt/prediction ledgers, provider capability snapshot, requested and realized resource accounting, compact predictions, unit-level sufficient statistics, and a claim-to-result matrix. Credentials and raw provider reasoning are never committed.

## Current Readiness and Gates

| Axis | Decision |
|---|---|
| Mock-only planning | **GO** |
| Primary one-call mock/no-network implementation | **GO** |
| Scientific accuracy execution | **BLOCKED** pending raw Data Gate and authenticated AgentPlan capability Gate |
| Scientific/paper readiness | **NOT READY** pending eligible real results, independent full-text novelty audit, and external validation |

The immediate route is mock implementation and fixed experiment planning, followed by a human checkpoint for the Ren/Patrizi downloads and authenticated API probes using a rotated credential supplied outside tracked files. No accuracy or RUL run is eligible before those gates pass.

## Publication Positioning

The safe framing is a PHM/reliability/industrial-AI empirical study:

> We present a controlled empirical study of direct and tool-grounded LLM Agent architectures for online capacitor degradation forecasting, with whole-device rolling replay, information- and attempt-aware controls, deterministic numerical authority, and failure-retaining evaluation.

Top-ML method claims are out of scope without a materially different mechanism. A strong PHM/TII/TIM/MSSP-level paper requires an audited substantial primary fleet, an independently audited external stress with honest target semantics, strong numerical controls, multiple authenticated backbones, unit-level uncertainty, complete direct/hybrid/multi-call comparisons, and a result—positive, mixed, or null—that changes practice.
