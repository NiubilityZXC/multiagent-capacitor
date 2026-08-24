# Adversarial idea-jury report

`review_independence: same-family`  
`acceptance_status: provisional`

## Verdict

The central question is currently unanswered: there is no eligible large capacitor benchmark and no numerical result. Stress-2 is only a 6-column × 11-point surrogate sanity check with unproven physical independence. Benchmark-L capacitance, ESR, endpoint, and RUL modeling remain blocked.

Choose **B, narrowly**:

- Method kernel: **Minimum Verified Evidence Support graph** derived from candidate 12.
- One additional mechanism: a finite-library, typed, executable perturbation/counterfactual challenger.
- Do not include randomized edge probes, capsule replay, endpoint algebra, ledgers, or semantic stress suites as coequal method contributions. They are evaluation, credit, or audit machinery.
- Replace “causal cut” terminology. Current observational data cannot support causal-edge or intervention-effect claims, and the proposed optimization is not a graph-theoretic minimum cut.

“Strictly causal” should mean “using only causally available past information.” It must not imply causal identification.

## 1. Disposition of all 32 candidates

Indices are the novelty ledger’s zero-based indices.

| Index | Candidate | Disposition |
|---:|---|---|
| 0 | Bitemporal Maturity-Gated Evidence Graph | Infrastructure only. Bitemporality and mature-only weighting are crowded; retain provenance invariants, not a method claim. |
| 1 | Censoring-Aware Forecast-to-Evidence Credit Graph | Reframe as credit/audit machinery. Edge-level censoring correction needs a coherent estimand and identifiable censoring. |
| 2 | Transportable Mechanism–Context Graph | Defer. Current conditions and metadata cannot identify a transportable mechanism. |
| 3 | Versioned Contradiction-Fork Graph | Archive. Close to bitemporal memory, change-point mixtures, and multiple-model estimation. |
| 4 | Maturity-Calibrated VoI Scheduler | Later routing study only. Delayed cost-aware routing is crowded and mature rewards will be sparse. |
| 5 | Cross-Target First-Passage Consistency | Strong numerical structured baseline/add-on, not agent novelty. RUL remains blocked. |
| 6 | Provenance-Weighted Sensor Reliability | Defer to a sensor-fault paper after real acquisition faults and provenance are available. |
| 7 | Dual-Clock Quarantine | Absorb its provisional-versus-mature state invariant into safety infrastructure; do not lead with it. |
| 8 | Typed Causal Claim Compiler | Merge its typed DSL and executable compilation into the selected core; remove unsupported “causal” wording. |
| 9 | Orthogonal Residual Court | Keep as a strong bounded-residual control. Ordinary sparse residual selection may reproduce it. |
| 10 | Counterfactual Evidence Braid | Challenger only. Negative controls/interventions are presently unavailable or unjustified. |
| 11 | Delayed-Maturity Double-Entry Ledger | Infrastructure. The replayable claim–impact invariant is useful, but not the paper’s method. |
| 12 | Minimum Causal-Cut Agent Graph | **Select as method kernel**, renamed Minimum Verified Evidence Support graph and formulated correctly. Novelty is same-family provisional. |
| 13 | Role-Conditional Conformal Product | Numerical uncertainty baseline/control; low method novelty. |
| 14 | Verified Correction-Operator Tribunal | Keep as the most credible simpler hybrid pilot and mandatory bounded-correction arm. |
| 15 | Falsification-First Shadow Court | Use selected deterministic falsifiers as validators; anytime testing is not a second method contribution. |
| 16 | Randomized Edge-Probe Ledger | Evaluation-only causal-credit experiment, preferably semi-synthetic. Not core architecture. |
| 17 | Counterfactual Capsule Replay | Evaluation/credit diagnostic only. Valid only downstream of merge points with cached sufficient outputs. |
| 18 | Maturity-Factored Credit Tensor | Archive. Primarily multi-task missing-feedback bookkeeping. |
| 19 | Regret-Escrow Adapter | Possible theory sidecar; defer unless a genuinely new unresolved-liability guarantee is proved. |
| 20 | Anytime-Valid LOCO Edge Gate | Evaluation/promotion control. Likely underpowered with few independent capacitors. |
| 21 | Transport-Minimax Credit | Robust-router baseline or later study; too close to group-DRO and domain routing. |
| 22 | Orthogonal Delayed Marginal Credit | Semi-synthetic credit-estimator diagnostic only; ordinary AIPW/OPE is the main neighbor. |
| 23 | Mature-Credit Deadline Knapsack | Systems control, not scientific core. Agent/workflow knapsack routing is crowded. |
| 24 | Typed PHM Forecast Contract | Retain as schema infrastructure. Novel only with a formal temporal/unit soundness result. |
| 25 | Mechanism-Signature Tool Registry | Defer. Signatures may be unstable dataset identifiers and Benchmark-L mechanisms are unresolved. |
| 26 | Universal Damage Transition | Separate long-term cross-family paper; latent reparameterization makes the causal claim fragile. |
| 27 | Endpoint Algebra/RUL Compiler | Protocol infrastructure. Essential for safe `RUL=NA`, but not current method novelty. |
| 28 | Conformal Do-No-Harm Gate | Strong safety control; low novelty and susceptible to near-universal fallback. |
| 29 | Delayed-Outcome Causal Credit Ledger | Archive as duplicative delayed expert weighting plus provenance. |
| 30 | Cross-Family Transfer Boundary Atlas | Potential separate empirical paper; too broad for the capacitor method paper. |
| 31 | Causal Counterfactual Graph Grammar | Use its perturbation suite as evaluation/verification machinery. Do not claim a causal graph under current data. |

## 2. Ranked top three pilot designs

1. **Narrow B: verified support graph plus executable challenger.**  
   Highest scientific upside and closest to the research anchor. The graph selects only prevalidated numerical routes; a fourth agent selects preregistered perturbation tests that deterministic code executes. Success requires beating both the strong numerical fallback and every matched-budget non-graph hybrid.

2. **Verified correction-operator tribunal.**  
   LLMs select only finite actions such as variance inflation, state reset, bounded residual correction, or fallback; numerical code determines magnitude. This is the cheapest test of whether LLM diagnosis has any predictive value. Execute this before building the full graph; failure kills the graph pilot.

3. **Randomized probes plus merge-local capsule replay.**  
   Run only as an evaluation pilot on synthetic or semi-synthetic hidden edge effects. Randomized substitution supplies ground truth; capsule replay is allowed only downstream of declared merge points. This can validate attribution but should not enter the forecasting method.

Recommended execution order is 2 → 1 → 3, despite the scientific ranking.

## 3. Exact proposed architecture

### Name and mathematical formulation

Use **MVES-CF: Minimum Verified Evidence Support with a Counterfactual Challenger**.

Do not call it a minimum cut. A conventional \(s\)-\(t\) cut removes paths, whereas this system selects predictive support routes. Predictive loss is also non-additive across edges, so a directed Steiner formulation with summed edge losses is unjustified.

For each target–horizon terminal \(\tau\), enumerate a finite set of executable routes \(\mathcal P_\tau\). Every route is a support subgraph assembled from a frozen operator library. On outer-training, inner-LOCO mature replays, freeze:

\[
C_{p,\tau}
=
\widehat L_{p,\tau}
+\kappa\,\widehat{\mathrm{SE}}_{\text{unit}}(L_{p,\tau})
+\lambda |E_p|
+\gamma\,\mathrm{Instability}_{p,\tau}.
\]

All coefficients and loss definitions are frozen before outer evaluation. Let \(V_{p,\tau}\in\{0,1\}\) be the deterministic validation result and \(x_{p,\tau}\) the route choice:

\[
\begin{aligned}
\min_x\quad &
\sum_{\tau}\sum_{p\in\mathcal P_\tau} C_{p,\tau}x_{p,\tau} \\
\text{s.t.}\quad &
\sum_{p\in\mathcal P_\tau}x_{p,\tau}=1,\quad \forall\tau,\\
&x_{p,\tau}\le V_{p,\tau},\\
&x_{p,\tau}+x_{q,\tau'}\le1
\quad\text{for declared conflicts},\\
&x_{p,\tau}\in\{0,1\}.
\end{aligned}
\]

The frozen fallback is a member of every \(\mathcal P_\tau\), ensuring feasibility.

This is a multiple-choice route-selection MILP. If joint routes cover several terminals, it becomes a set-partitioning MILP over enumerated support subgraphs. It is not set cover unless multiple overlapping routes may jointly satisfy a terminal, and it is not Steiner unless defensible additive edge costs are introduced.

### Numerical backbone

All hybrid arms share the same frozen library:

- last value;
- global drift;
- local linear;
- log-linear exponential;
- causal local-trend Kalman filter;
- ridge causal increment;
- a training-only nonnegative convex ensemble.

Additional models enter only after inner-LOCO qualification. The fallback is the inner-selected numerical champion, with a frozen tie rule.

### Four fixed graph roles

1. `trajectory_proposer`: causal capacitance/ESR prefix and numerical disagreement, but no identity or terminal metadata.
2. `context_proposer`: available operating exposure and training-side effect summaries; no future outcome.
3. `sensor_integrity_proposer`: missingness, timing, calibration, and acquisition diagnostics.
4. `challenge_selector`: sees typed proposals and a frozen test library, not current or future labels; selects tests rather than judging quality.

All use the same base model in the primary topology experiment. Cross-model heterogeneity is secondary.

### Typed records

- `OriginPacket.v1`: opaque origin key, event/ingestion cutoff, causal history, physical units, horizons, allowed context, numerical forecast bundle, maturity snapshot hash, and budget-contract hash. It excludes file paths, IDs, final lengths, termination, suffixes, RUL labels, and outer-result summaries.
- `Proposal.v1`: origin echo, role, target, horizon, evidence references, operator enum, parameter bin, signed-effect enum, requested test enums, and abstention flag. No free text or generated code; `additionalProperties=false`.
- `TestSpec.v1`: one of `drop_edge`, `replace_fallback`, `sensor_mask`, `temporal_placebo`, `unit_invariance`, `identity_permutation`, or an explicitly supported load intervention.
- `RouteCertificate.v1`: proposal hash, lineage result, unit/type result, training-replay result, per-unit stability result, perturbation results, eligibility, and rejection reason.
- `PredictionCommit.v1`: target, horizon, point/quantiles, route hash, fallback flag, attempt/token/latency data, request/response hashes, commit time, and seal.
- `MaturityEvent.v1`: forecast ID, target availability time, exact/interval/right-censored state, scorer, and score.
- `CreditUpdate.v1`: route/edge class, target, horizon, mature unit count, effective sample size, paired loss difference, and frozen update version.

### Deterministic validators

1. JSON schema, finite values, enum completeness, and origin echo.
2. Temporal lineage: every referenced datum was ingested by the origin.
3. Unit and target compatibility; capacitance cannot be silently treated as battery capacity.
4. Forbidden-field and proxy checks.
5. Operator trust region and predictive convex-hull checks where applicable.
6. Training-only mature replay and leave-one-training-unit-out stability.
7. Executable perturbations selected from the frozen library.
8. Solver feasibility and deadline checks.

Sensor masking, unit invariance, temporal placebos, and ID permutation are properly called perturbation or invariance tests. “Counterfactual” is reserved for a documented intervention or identified structural model. Capacity monotonicity cannot be a universal validator because recovery has been reported.

### Delayed maturity credit

- A \(h\)-step capacitance or ESR label matures only at the actual \(t+h\) event.
- Within a held-out unit, a frozen algorithm may update from previously matured short-horizon labels, but each outer unit starts from the same outer-training snapshot.
- RUL credit does not mature at \(t+h\). It remains training-only until a valid EOL/censoring outcome exists.
- Other outer-evaluation units and aggregate outer results are never used.
- If censoring assumptions are unjustified, IPCW credit is `NA`; it is not replaced by complete-case credit.

### Fallback

Timeout, malformed schema, semantic failure, OOD support failure, insufficient mature support, solver failure, deadline miss, or budget exhaustion returns the exact frozen numerical forecast. Late responses cannot overwrite the committed fallback. Intervals come only from training-side prequential residuals; insufficient calibration units produce `NA`.

Stress-2 RUL and Benchmark-L RUL remain `NA` under current evidence.

### Budget policy

- Raw causally available information is identical across arms. Numerical outputs are deterministic transformations of that history and are exposed only in arms defined as hybrid.
- The graph uses four logical calls. Formal call-matched comparisons use exactly four physical attempts and no retry; failures consume their slot.
- A separate resilience experiment permits one common transport-only retry for timeout/429/5xx. There is no schema-repair or semantic retry.
- Total input and output token ceilings, model version, decoding settings, deadline, and allowed tools are frozen in one `BudgetContract`.
- The one-call direct arm is the natural baseline. A total-token-matched direct call receives the combined output ceiling. Four-call homogeneous direct self-consistency is the physical-call-matched direct control.
- Architecture value is claimed only if it survives both matched-token and matched-call comparisons.
- Actual attempts, tokens, cost, and p50/p95/p99 latency remain outcomes; successful-call-only accuracy is forbidden.

## 4. Required controls and ablations

### Mandatory arm panel

| Arm | Definition |
|---|---|
| N0 | Strong numerical-only expert/ensemble; zero API calls |
| D1 | One direct LLM numeric forecast |
| HD | Homogeneous direct multi-agent: same model and role, four isolated direct forecasts, deterministic aggregation |
| XD | Heterogeneous direct multi-agent: disjoint roles with direct forecasts; cross-model heterogeneity is secondary |
| NT | LLM selects/invokes a numerical tool that supplies the forecast |
| RC | Bounded residual correction |
| RF | LLM routing or convex fusion over the shared numerical experts |
| VG | Typed, executable, counterfactual/perturbation-verified support graph |

Add a token-matched expanded D1 and a non-LLM numerical router. No LLM vote or judge selects a champion.

### Essential ablations

- A-only versus B-narrow: remove the executable challenger.
- Minimum support versus full verified graph and size-matched random support graphs.
- Deterministic exhaustive proposal enumerator versus LLM proposals.
- Untyped structured output versus typed DSL.
- Mature-only credit versus frozen weights and a clearly invalid premature/proxy-credit leakage control.
- Remove each role, edge class, conflict constraint, validator, and perturbation test.
- Replace route-level replay cost with generic sparse stacking.
- Shuffled role views and duplicated views.
- Current-device mature short-horizon updating on versus off.
- Fallback-only, fallback disabled, and equal fallback coverage controls.
- Identical numerical backbone and calibration across all hybrid arms.
- Five preregistered seeds for stochastic components.
- Failure injection for timeout, malformed output, late response, missing channel, timestamp swap, unit error, and budget exhaustion.

## 5. Falsifiable hypotheses and kill conditions

All thresholds are prospective; Freeze B must confirm them before outer results.

- **H1—primary value:** VG reduces unit-macro primary proper loss by at least 5% versus both the strong numerical champion and the best preregistered non-graph matched-budget control.
- **H2—verification necessity:** B-narrow improves over A-only by at least 2%, or improves a prespecified worst-condition metric without violating mean non-inferiority.
- **H3—typing/maturity necessity:** removing typing or mature-only credit causes at least a 2% loss or a prespecified safety failure.
- **H4—LLM necessity:** VG outperforms a deterministic enumerator using the same finite operator and route library.
- **H5—failure safety:** every injected API/schema/deadline failure returns the byte-identical frozen fallback and no late response overwrites it.
- **H6—budget robustness:** the architecture result holds in both matched-call and matched-token comparisons.
- **H7—verification validity:** null/placebo edges remain below the preregistered false-admission level; passing the perturbation suite predicts robustness on untouched shifts.

Preregistered kill conditions:

- Data or Design Gate fails: no superiority paper and no Benchmark-L RUL.
- Physical independence, target definition, or termination semantics remain unresolved.
- VG fails to beat the numerical champion or matched non-graph hybrid.
- B does not beat A: delete the counterfactual-verification contribution.
- The deterministic enumerator matches VG: delete the LLM-agent contribution.
- Gains arise only from extra information, calls, tokens, retries, latency, or more favorable fallback.
- Active non-fallback coverage is too low to satisfy a frozen minimum; safety by near-universal abstention is not success.
- Any numeric RUL is emitted when the endpoint is ineligible.
- Worst-group degradation, coverage, or deadline failures exceed Freeze B bounds.
- Edge attribution is unstable across equally optimal routes: retain prediction results but delete edge-necessity claims.
- No valid interventions or negative controls exist: delete all causal-effect and mechanism language.
- Stress-2-only improvement: engineering sanity, not scientific evidence.
- Any LLM self-score or judge replaces held-out numeric loss: automatic invalidation.

## 6. Minimum experiment and data package

### Engineering qualification

- Synthetic streams with known route effects, delays, censoring, faults, and hidden leakage.
- Stress-2 only for parser, commit/maturity ledger, LOCO scorer, timestamp invariants, and failure handling.
- Do not use its six columns as proven independent physical units.
- Do not treat its unknown-termination tail as an ordinary confirmed right-censoring event.

### Scientific eligibility

An accuracy paper requires:

1. Verified physical-unit identities and cross-resource duplicate resolution.
2. Formal capacitance target construction, ESR derivation, units, reference conditions, and causal timestamp alignment.
3. Resolved ES12 off-by-four timestamps and ES10C8 missing modality.
4. Explicit EOL and termination semantics supporting exact, interval-censored, right-censored, or unknown states.
5. A primary corpus with enough independent units and condition groups to pass a preregistered design simulation—e.g. at least 80% power for the chosen minimum relevant effect with unit-cluster inference.
6. Preferably an untouched external capacitor cohort or second independently collected/audited corpus. Without it, conclusions remain dataset-specific and are unlikely to support a general top-venue method claim.
7. Nested whole-unit LOCO and, where supported, leave-one-accelerated-stress-voltage-out evaluation.
8. Freeze B: one endpoint, horizon, estimand, primary comparison, non-inferiority bounds, no-event rule, tie rule, hidden split, and sealed analysis hash.
9. Immutable prediction, maturity, API-attempt, route, and evaluation ledgers.
10. Model capability/version snapshot, prompt/schema hashes, secret scan, environment lock, and full failure denominator.
11. CPU-first experiments, cached API outputs, at most three architecture candidates, and no more than two GPU hours per pilot as already constrained.

Benchmark-L currently satisfies none of the target/outcome eligibility needed for formal forecasting. Schema existence—24 EIS labels, 23 transient labels, and `Cs/Cp` tokens—is not target validity.

## 7. Results-to-claims matrix

| Outcome | Defensible claim |
|---|---|
| VG beats numerical and every matched direct/hybrid arm; B beats A; ablations survive | Typed verified support routing improved held-out trajectory forecasting on the audited accelerated-stress corpora. Causal/mechanism and broad PHM claims still require interventions and external data. |
| VG beats direct LLMs but not strong numerical models | Direct agents are inferior; agent participation provides no predictive advantage over specialized numerical forecasting. |
| A beats controls but B does not beat A | Minimal verified support selection may help; executable counterfactual verification is unnecessary. |
| B improves worst-shift performance but not mean loss | Prespecified robustness benefit only, provided fallback frequency and mean non-inferiority pass. |
| Deterministic enumeration matches VG | A numerical verified-route method may work; there is no evidence that LLM agents are necessary. |
| Gain occurs only at high fallback rate | No hybrid-improvement claim; report selective coverage/fallback behavior. |
| Null with narrow intervals | Evidence against a practically meaningful agent-graph advantage under the tested budgets. |
| Null with wide intervals | `NO_CHAMPION`; study is underpowered and supports no equivalence claim. |
| VG is worse or less reliable | Negative finding: added agent structure harms accuracy, latency, or reliability relative to the fallback. |
| Positive Stress-2 result only | Pipeline and scorer sanity only; no unseen-capacitor or architecture claim. |
| RUL positive without endpoint gate | Invalid result; no claim. |

## 8. Strongest rejection argument and minimum answer

### Strongest rejection

This is an elaborate agent wrapper around unresolved and extremely small capacitor data. The claimed “causal cut” is neither causally identified nor mathematically a minimum cut. Typed schemas, delayed maturity, ledgers, fallback, conformal calibration, and matched budgets are evaluation hygiene. Sparse numerical routing, bounded residual correction, delayed bandits, and workflow verification are crowded. Any apparent gain may come from the numerical backbone, fallback selection, hidden compute, or leakage. With no eligible Benchmark-L targets and no results, the paper cannot show either novelty or scientific utility.

### Minimum answer

- Pass the physical identity, target, alignment, and outcome gates.
- Supply an adequately powered independent-unit benchmark and preferably an untouched external cohort.
- Replace “minimum cut” with the exact route-selection formulation.
- Freeze one primary endpoint and comparison.
- Run all eight arms with matched-call and matched-token controls.
- Show A versus B, full versus minimal/random graphs, and deterministic enumeration versus LLM proposals.
- Use only committed held-out numerical losses and unit-cluster uncertainty.
- Either provide defensible interventions/negative controls or remove causal claims.
- Demonstrate that gains persist on the planned denominator and are not produced by fallback frequency.

Anything less supports, at most, a careful negative benchmark or engineering report.

## 9. Venue positioning

For NeurIPS/ICML, the work needs an eligible multi-dataset empirical result plus a formal contribution beyond PHM-specific schema engineering. The best path is a precisely defined verified-route method, executable test semantics, strong contemporary direct/hybrid baselines, and evidence that the LLM proposer is indispensable. Randomized edge identification could support a separate methodological contribution, but combining it now would overextend the paper.

For PHM/IJPHM, a rigorous capacitor-specific empirical study is plausible even with null results: audited physical identities, correct capacitance/ESR semantics, interval censoring, causal replay, strong numerical baselines, and honest RUL abstention are valuable. The agent graph should remain secondary unless it wins.

For ML systems, emphasize typed execution contracts, immutable commits, API failure containment, budget/deadline accounting, hidden fault tasks, and reproducible fallback behavior. Candidate 16/17/31 fit this positioning as evaluation infrastructure rather than forecasting innovations.

## 10. Mock review

**Current NeurIPS/ICML score: 2/10 — Strong Reject.**  
**Confidence: 5/5.**

Reason: no eligible large benchmark, no result, unsupported causal terminology, and an overbroad bundle of method and audit mechanisms. Candidate 12 provides a plausible same-family-provisional kernel, but only after mathematical correction and decisive matched-budget experiments.

A successful Data Gate, adequately powered frozen evaluation, narrow B architecture, and clear wins over both strong numerical and matched-budget direct/hybrid controls could move the work into borderline territory. It would not, by itself, establish broad causal or universal PHM claims.
