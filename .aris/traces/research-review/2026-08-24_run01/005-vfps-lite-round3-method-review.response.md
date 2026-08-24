# Research-Refine Round 3 Review — VFPS-Lite

**Review status:** `PROVISIONAL — same-family Codex review`  
**Evidence boundary:** local files named in the Round 3 request only; no web search, no external novelty verification, no downloaded Ren/Patrizi/Warwick payload, no authenticated AgentPlan call, and no scientific forecasting result.  
**CALIBRATION:** `none` — no human-curated known-good/known-bad proposal anchors were supplied.  
**Verdict:** `RETHINK` as a program-synthesis method; `REVISE` only after an explicit pivot to an empirical Agent-architecture study.  
**Weighted composite:** **6.325/10 = 6.33/10**.

## Immutable Problem Anchor

> Can a maturity-aware agent graph whose typed proposals are tested by executable counterfactual replay improve strictly causal, held-out capacitor forecasts over both direct LLM agents and strong specialized numerical models under matched call, token, and latency budgets?

The anchor is copied exactly. The proposal continues to ask the correct empirical forecasting question, but its advertised per-origin conditional-program mechanism does not currently supply a distinct predictive function class.

## Executive decision

The refinement is substantially more implementable than the previous round: the one-call boundary, arm-specific permissions, syntactic grammar, fallback semantics, three-way data split, durable attempts, and current Data/API stop conditions are unusually explicit. The exact grammar arithmetic is also correct as a **per-target×horizon syntactic count** under the stated distinct-branch convention.

The core method claim nevertheless fails a direct equivalence test. At an origin, the proposer already sees every value used by the predicate. It emits and immediately executes a fresh program for that same origin. Therefore every emitted

```text
IF(predicate, action_true, action_false)
```

is observationally equivalent, for the committed forecast, to emitting only whichever one of `action_true` or `action_false` is active. Branching adds syntax, inactive-branch failure modes, and perhaps a finite-model prompting bias; it does not add pointwise predictive expressivity. Stochastic decoding does not rescue the claim.

This is not a kill condition that needs held-out labels to resolve. It is already a property of the proposed interfaces. Accordingly, the paper should **pivot now** to the empirical architecture question—whether constrained one-call action selection is more accurate, reliable, and efficient than direct numeric LLM forecasting and ordinary numerical/hybrid controls. It should not retain “per-origin program synthesis” as a conditional dominant method contribution.

If a genuine conditional-program claim is indispensable, the method must change materially: synthesize and seal a program **before** its predicate values are known and reuse it over later origins, or withhold a causally available executor-side diagnostic from the proposer until local execution. Either choice requires a new information/budget design and is not a wording repair.

## Scores

| Dimension | Weight | Score | Weighted contribution |
|---|---:|---:|---:|
| Problem Fidelity | 15% | 7.5 | 1.125 |
| Method Specificity | 25% | 8.5 | 2.125 |
| Contribution Quality | 25% | 4.0 | 1.000 |
| Frontier Leverage | 15% | 6.5 | 0.975 |
| Feasibility | 10% | 5.0 | 0.500 |
| Validation Focus | 5% | 8.0 | 0.400 |
| Venue Readiness | 5% | 4.0 | 0.200 |
| **Total** | **100%** |  | **6.325/10** |

**GAP:** With no curated anchors, this score is rubric-calibrated rather than exemplar-calibrated. VFPS-Lite is closest to a strong preregistration and safety harness on Method Specificity and Validation Focus, but it falls far short of a top-venue method proposal on Contribution Quality: the 2,052,096-program syntax quotients to at most 96 active Actions at each realized origin. It also falls short on Feasibility and Venue Readiness because every real target/API route remains gated. The largest acceptance lift will not come from another node, role, predicate, or verifier; it will come from deleting the invalid expressivity claim, installing the exact action-only controls, and obtaining eligible whole-unit data.

## 1. Decisive per-origin `IF` equivalence

Let (x) be the frozen current `OriginPacket`, let (A) be the 96-Action set, and let (q(x)) be a deterministic predicate whose inputs are present in (x). Define the realized-action map

\[
r_x(\mathrm{IF}(q,a,b))=
\begin{cases}
a,&q(x)=1,\\
b,&q(x)=0.
\end{cases}
\]

For any deterministic or stochastic proposer \(\pi_P(x,u)\), where \(u\) includes decode randomness, define an action-only policy

\[
\pi_A(x,u)=r_x(\pi_P(x,u)).
\]

Then \(\pi_A\) and \(\pi_P\) have the same conditional distribution over committed Actions and hence the same committed forecast distribution, assuming the same deterministic numerical executor. This transformation applies independently to every target×horizon AST in the full bundle.

Consequences:

1. **Extensional action class:** the conditional grammar yields at most the same 96 Actions at a fixed origin, often fewer because two registry entries can coincide numerically on that packet.
2. **Online policy class:** because a fresh LLM invocation already conditions on the entire current packet, it can implement the same choice internally and emit only the active Action.
3. **Stochasticity:** sampling produces a distribution over active Actions; an action-only stochastic selector can represent the same push-forward distribution.
4. **Inactive branch:** after observing predicate truth, the proposer has 95 arbitrary choices for the inactive branch. This is dead syntax for the committed forecast and an extra source of rejection/fallback.
5. **Possible finite-model effect:** explicit branch syntax may alter tokenization, elicitation, regularization, or parse failure. A measured benefit would be an empirical representation/inductive-bias result, not proof of a larger program or policy class.

At a fixed origin, each Action has

\[
1+225\times95=21{,}376
\]

syntactic representations under the proposed grammar: one direct Action and 21,375 conditional programs that execute that Action. Thus

\[
96\times21{,}376=2{,}052{,}096.
\]

The reported “program space” is therefore exactly partitioned into 96 origin-specific active-action fibers before additional semantic duplicates are considered.

### Counterfactual replay does not undo the collapse

Holding one emitted AST fixed and perturbing (x) can flip a predicate and exercise its inactive branch. That can support a narrow **fixed-artifact metamorphic contract**. It does not verify the behavior of the actual online LLM policy on the perturbed packet, because under the stated deployment that policy would call the proposer again and may emit a different AST. Testing (p_x(x')) is not the same as testing (p_{x'}(x')).

Therefore:

- the verifier may certify syntax, lineage, authority, deterministic execution, fallback, and explicitly specified metamorphic behavior;
- it cannot establish that the stochastic proposer itself is counterfactually stable unless the proposer is rerun on the perturbed packet under a separately budgeted test, or the emitted program is reused rather than resynthesized;
- it cannot establish predictive correctness or a causal effect;
- rejecting an invalid inactive branch is a stricter safety filter, not increased forecast expressivity.

The proposal is correct to avoid causal-effect language, but “executable counterfactual verification” still overstates what the current per-origin artifact test establishes. “Deterministic metamorphic contract testing of a typed action artifact” is the defensible description.

## 2. Grammar arithmetic and semantic audit

The arithmetic passes under the explicit mock manifest:

\[
A_0=M+W+1=6+5+1=12,
\]

\[
|A|=12(1+4+3)=96,
\]

\[
|Predicate|=15+2\binom{15}{2}=15+210=225,
\]

\[
|Program|=96+225(96)(95)=2{,}052{,}096.
\]

This count needs four qualifications in every method description:

1. It is the count for **one target×horizon**, not for the complete bundle. If (K) keys are chosen independently, the raw bundle space is (2{,}052{,}096^K), subject to coverage constraints. ENUM must state whether it searches keys independently and why the loss is separable.
2. It is syntactic, not functional cardinality. Same-feature mutually exclusive-bin conjunctions, redundant disjunctions, constant predicates on the admissible domain, and numerically coincident Actions create semantic duplicates.
3. The contract says equal branches are forbidden but the canonicalizer also says equal branches are folded. Choose one raw-input rule. Rejecting equal branches gives the displayed valid-serialization count. Accepting then folding them yields the same canonical set but a larger raw accepted serialization set, (96+225(96)^2=2{,}073{,}696).
4. `SHIFT` and `INFLATE` must still freeze exact point/quantile transformations, physical clipping behavior, and failure semantics; “trust region” alone is not an executable definition.

The arithmetic is not the problem. Treating syntactic scale as method expressivity is.

## 3. `ENUM-UCB`: label blindness and fairness

### Label-blindness verdict

`ENUM-UCB` can be strictly label-blind **at the online origin** if and only if all of the following are true:

- numerical predictions and loss tables are produced solely from development units with whole-unit cross-fitting;
- the current unit, policy-validation units, and shadow units never enter those tables;
- context stratum (z(x)) uses only past-available packet fields;
- candidate prefix, feature bins, score constants, score tables, action/program hashes, and tie rules are sealed before policy validation;
- online selection uses no newly revealed loss, suffix, endpoint, or unit identity.

The proposal largely states these conditions. It does not yet define the policy completely. It should state, for example,

\[
\pi_{ENUM}(x)=\arg\min_{p\in C_B}S_{enum}(p,x),
\]

where (C_B) is the exact sealed candidate prefix admitted by the offline budget. The loss aggregation, cluster-level standard error, confidence multiplier, missing-stratum backoff, and final tie order must be executable rather than prose.

The current `+inf` rule for an under-supported stratum is defective: support is generally a property of the stratum, so every candidate may become infinite and selection collapses to an arbitrary hash tie. Back off mechanically to the global term, record `stratum_unqualified=true`, and do not call the score a stratum estimate.

“UCB” is justified only if the standard-error construction, confidence level, dependence unit, and fixed-registry multiplicity treatment make it an actual prespecified upper confidence bound. Otherwise call it a frozen pessimistic risk score.

### Fairness verdict

`ENUM-UCB` is not an exactly compute-matched comparator, and the proposal appropriately admits that hidden pretraining compute cannot be equated to CPU expansions. It can still be a valid lower-cost algorithmic control if development search and online cost are reported separately. Required repairs are:

1. Add **`ENUM-ACTION`**, an exhaustive score-based selector over the 96 Actions. This is the direct deterministic test of whether any conditional syntax is needed.
2. Add **`VFPS-NB`**, using the same LLM model, packet, instructions except grammar restriction, decode settings, physical attempt, requested output ceiling, deadline, verifier scope, and fallback as `VFPS1`. The current `NO-BRANCH` description—“no API or pre-frozen policy”—is not a matched mechanism control.
3. State whether ENUM sees only (z(x)) or the full packet-derived feature vector. If it sees less information than the LLM, call that limitation out; if it sees the same frozen predicates, define the mapping.
4. Report coverage/performance as a function of the sealed candidate-evaluation budget. A hash-ordered truncated BFS is deterministic but can omit nearly all conditional syntax.
5. Prevent syntactic multiplicity from silently weighting equivalent behaviors. At minimum report unique development action/truth signatures and choose a fixed smallest representative for diagnostics.
6. Record human design time, prompt/policy trials, admitted candidate count, LLM calls, CPU evaluations, and online resource use in separate ledgers. Do not claim exact development-compute parity.

## 4. Information, call, token, retry, and latency matching

### What is already sound

- `D1-RAW` directly tests a pure numeric LLM forecaster on causal raw history.
- `D1-PACKET` receives the same hybrid packet data bytes as `H1/RF1/RC1/VFPS1` and directly emits numbers, which is the right control for numerical-candidate information access.
- Arm-specific schemas prevent a direct arm from silently invoking local numerical authority.
- `H1/RF1/RC1/VFPS1` perform one provider response followed by deterministic local execution; there is no provider tool continuation or accuracy reprompt.
- Invalid, late, timed-out, or incomplete outputs return the same complete fallback and remain in the planned denominator.

### Remaining asymmetries

1. Equal packet **data bytes** do not imply equal total input tokens because instructions and schemas differ. Hash and report data bytes separately from total serialized request bytes and provider-reported input tokens.
2. Direct arms must serialize every forecast number, while selection arms return short IDs. This is an intentional architecture efficiency, but it prevents a clean claim of equal realized token spend. Use a compact fixed-order numeric vector for direct arms, give all arms the same requested ceiling, forbid action arms from spending their spare budget on prose, and report both requested-budget and actual-spend/Pareto analyses.
3. `H1`, `RF1`, and `RC1` individually do not control for VFPS's union of model, fusion, shift, and inflate permissions. `VFPS-NB` must select from the same 96-Action union.
4. Local compiler, verifier, model execution, and queue time count toward end-to-end latency and must be reported even though they do not count as API calls.
5. `accuracy_v1` says one physical request and no retry, whereas the generic Gate-1 harness permits up to three physical attempts for selected transport failures. Freeze an experiment-specific override in the protocol hash. A second transport attempt is a second physical attempt even if the first body was not fully sent.
6. Homogeneous and heterogeneous direct multi-agent arms may be staged after the one-call pilot, but they remain required by the frozen Research Brief for the eventual full comparison. They cannot disappear from the final empirical claim because the pilot is negative.

Matched-call, matched-requested-token, matched-actual-spend, and matched-information are distinct analyses. The paper must not collapse them into one phrase.

## 5. Policy registry, qualification, and durable attempts

The development/policy-validation/shadow split is the right statistical object. Qualification attaches to the complete sealed stochastic `AgentPolicy`, not to unique ASTs. The following must be mechanical:

- seal the **entire** candidate policy registry before inspecting policy-validation outcomes;
- treat model, prompt, schema, grammar, decode, compiler, verifier, numerical registry, fallback, retry, capability snapshot, and version-acceptance rule as policy identity;
- use a frozen simultaneous procedure across all confirmatory policies/contrasts, select at most as preregistered, and touch shadow units once;
- never count API replicates as independent physical units;
- if a policy is edited after validation, use new untouched validation units rather than “correcting” adaptivity with Holm after the fact.

The durable attempt design is strong but needs a recovery rule. Any `STARTED` record without a sealed `FINISHED` record after a crash must count as an ambiguous consumed attempt and produce fallback; `accuracy_v1` must never resend it. Fsync the file and, when creating/renaming artifacts, the parent directory. Prediction commitment needs an atomic durable marker that the independent reveal service verifies before releasing the next event. Late provider writes must be unable to replace the committed fallback.

These are systems-validity requirements, not evidence of forecast improvement.

## 6. Maturity, Graph Engineering, and claim ownership

The proposal's “maturity” is currently an offline whole-policy qualification state. There is no online route-signature maturity update, delayed edge credit, or maturity-dependent routing. That is acceptable for a minimal empirical architecture, but the paper must not imply a richer maturity-aware online graph mechanism than it implements.

Likewise, the eight-node Graph Engineering development DAG is audit and workflow machinery. The proposal already calls it a non-contribution; follow through by moving it to a short reproducibility appendix or artifact document. It should not appear in the method figure, method novelty paragraph, or architecture ablation unless the paper is explicitly a research-workflow systems paper.

Deterministic validators, ledgers, Data Gates, shadow services, and release arbitration establish eligibility and provenance. Numeric held-out proper loss remains the only evidence for forecasting value.

## 7. Data and API eligibility

The newly source-qualified Ren corpus improves **feasibility planning only**:

- the landing page, download route, licence, reported 113-device fleet, expected bytes, and published MD5 are locally documented;
- the 2.1 GB archive has not been downloaded, extracted, parsed, deduplicated, or target-audited;
- capacitance in farads is not listed as a native field and requires a frozen waveform derivation;
- ESR is unavailable and must remain `NA`;
- protocol EOL/RUL needs a separately audited threshold and censoring rule;
- subset publications cannot be counted as independent fleets.

Patrizi remains an eight-unit, one-device-per-strategy external domain with condition/device confounding. Warwick remains an energy auxiliary. Benchmark-L remains `FAIL/BLOCKED` for every requested target and RUL despite a passing bundle verifier. Stress-2 remains a 6-column×11-point sanity fixture with unproven physical independence. AgentPlan remains blocked pending authenticated discovery, capability probes, secret/fault checks, and human approval.

Therefore VFPS-Lite is eligible only for mock compiler, no-network, synthetic search, blind-ledger, and fault-injection implementation. There is still no eligible basis for an accuracy, novelty-through-performance, or multi-agent superiority claim.

## 8. Required claim pivot

### Recommended primary framing: empirical architecture paper

The dominant question should be:

> Under strictly causal whole-unit replay and matched observable API budgets, when does a one-call LLM that emits a bounded action over frozen numerical experts improve or harm forecast risk, reliability, and cost relative to direct numeric LLMs and strong numerical models?

The typed compiler/verifier, exact fallback, durable attempt ledger, policy-level qualification, and information-parity controls make this study credible. They are architecture/protocol contributions supporting the empirical result, not evidence that program synthesis is a new predictive mechanism.

Use the 96-Action `VFPS-NB` controller as the minimal hybrid architecture. Keep `IF` only as a preregistered representation ablation. Even if `IF` beats `VFPS-NB`, the immediate claim ceiling is “explicit branch scaffolding helped this finite proposer under these schemas and budgets,” not “conditional program synthesis expanded the online policy class.”

### Only route back to a method claim

A method claim becomes logically available if the program is frozen before predicate realization and reused across multiple unseen origins or units. Then a fixed conditional program can express behavior that a fixed single Action cannot. The comparison must include:

- the same synthesis-time information;
- a persistent no-branch Action control;
- an ordinary per-origin action router under a fairly amortized call budget;
- branch-flipping causal-packet fixtures and exact contract invariants;
- untouched whole-unit evaluation.

This redesign is optional and should not be bolted onto the empirical pilot merely to preserve the word “program.”

### Claims that must be removed now

- Per-origin `IF` enlarges predictive expressivity.
- The 2,052,096 syntactic count represents 2,052,096 distinct realized forecast choices.
- A VFPS1 win over individually narrower `H1/RF1/RC1` proves program-synthesis necessity.
- Replaying a fixed emitted AST on perturbed packets verifies the complete resynthesizing LLM policy.
- Policy qualification or deterministic verification proves predictive correctness.
- Ren source acquisition qualification makes any current scientific experiment eligible.

## 9. Dimension-specific findings and fixes

### Problem Fidelity — 7.5/10

The exact anchor and causal-evaluation constraints remain visible. Fidelity is reduced because online “maturity” is actually offline policy qualification, the proposed counterfactual test does not cover the resynthesizing proposer, and the required direct multi-agent arms are deferred. These are scope labels to correct, not reasons to add more nodes.

### Method Specificity — 8.5/10

The packet schemas, arm permissions, one-call execution, grammar, fallback, attempt lifecycle, and split discipline are implementation-grade. Remaining executable gaps are ENUM's selection/backoff, raw equal-branch handling, full-bundle search factorization, exact transform semantics, and crash recovery.

### Contribution Quality — 4.0/10

- **Weakness:** the dominant conditional-program contribution is pointwise equivalent to action-only selection; two-level qualification is excellent evaluation hygiene but not yet a mechanism-level forecasting contribution.
- **Concrete fix:** make action-only typed selection the primary empirical architecture and `IF` a representation ablation. If a method paper is mandatory, redesign the program to persist across origins before predicate realization.
- **Priority:** `CRITICAL`.

### Frontier Leverage — 6.5/10

- **Weakness:** the LLM is currently a bounded router over frozen numerical experts, which is appropriate but not substantively elevated by the word “program.”
- **Concrete fix:** describe the LLM exactly as a one-call constrained action controller in the empirical fork. Do not add debate, memory, RL, or more roles. For a true synthesis fork, use a persistent typed policy with executor-time predicates; that is a mechanism change, not a branding change.
- **Priority:** `IMPORTANT`.

### Feasibility — 5.0/10

- **Weakness:** mock implementation is feasible, but all real scientific execution remains blocked by raw-data target/identity gates, human acquisition approval, and authenticated API capability gates.
- **Concrete fix:** complete the bounded Ren acquisition/parser/target audit and the AgentPlan capability/failure gate before freezing an accuracy protocol. Preserve ESR/RUL `NA` where unsupported.
- **Priority:** `CRITICAL`.

### Validation Focus — 8.0/10

The three blocks are focused and numeric. Replace the ambiguous `NO-BRANCH` with exact `VFPS-NB` and add `ENUM-ACTION`; otherwise the central necessity test is not identified. The safety block must remain separate from forecast-accuracy evidence.

### Venue Readiness — 4.0/10

- **Weakness:** no eligible real dataset or API result exists, local source qualification is not a Data Gate, and the proposed method novelty collapses under interface equivalence.
- **Concrete fix:** first produce a sealed multi-unit empirical result with strong numerical champions and all required direct/hybrid arms. Position it as a rigorous PHM/Agent-systems empirical study unless the persistent-program redesign demonstrates a general mechanism across more than one eligible corpus.
- **Priority:** `CRITICAL`.

## Drift Warning

**PARTIAL DRIFT.** The forecasting question is preserved, but the mechanism has drifted from a maturity-aware counterfactual agent graph toward an evaluation/audit stack around a one-call constrained router. The smallest honest repair is not to re-add graph modules; it is to relabel the work as an empirical Agent-architecture study and state that maturity means sealed whole-policy qualification. If the original method-level graph claim is non-negotiable, the per-origin interface must be redesigned so branch conditions are unresolved at synthesis and the program persists.

## Simplification Opportunities

1. Delete `IF` from the primary method and delete the two-million-program search from the primary pilot. Use the 96-Action union plus exact `VFPS-NB`/`ENUM-ACTION` controls.
2. Move the eight-node Graph Engineering DAG, release arbiter, and research workflow out of the method narrative into the reproducibility/audit appendix.
3. Keep one proposer, one provider attempt, no accuracy retry, one deterministic executor, and one fallback. Do not restore the four-role design unless the later required multi-agent empirical arm is being run as a control.

## Modernization Opportunities

**NONE required for the empirical fork.** The problem is identification and eligible evidence, not insufficient model fashion. Provider-native strict structured output may replace hand parsing only if the authenticated capability gate verifies it, but this is an engineering improvement and does not repair the contribution. Do not add debate, memory, RL, self-critique, or learned judges.

## Priority action items

1. **CRITICAL — Pivot the claim now:** make action-only one-call constrained control the primary architecture; demote `IF` to a representation ablation.
2. **CRITICAL — Install the exact equivalence control:** define `VFPS-NB` with identical proposer, packet, union Action set, decoding, call/token/deadline, verifier, and fallback.
3. **CRITICAL — Install the deterministic action control:** exhaustively evaluate `ENUM-ACTION` over 96 Actions with frozen global/stratum backoff.
4. **CRITICAL — Finish ENUM's contract:** exact `argmin`, candidate prefix, unit-level loss/SE, under-supported-stratum fallback, confidence terminology, full-bundle factorization, and offline/online budgets.
5. **IMPORTANT — Separate parity claims:** distinguish data-byte parity, total prompt tokens, requested ceilings, actual spend, physical attempts, local compute, and end-to-end latency.
6. **IMPORTANT — Resolve attempt-policy conflict:** bind `accuracy_v1` to exactly one physical attempt and no retry; leave the three-attempt transport policy in a separate resilience protocol.
7. **IMPORTANT — Complete seal/recovery details:** whole registry before validation, simultaneous selection rule, shadow once, unmatched `STARTED` recovery, and atomic prediction-before-reveal commit.
8. **CRITICAL — Respect eligibility:** no accuracy run until Ren or another corpus passes row-level target/identity/split gates and AgentPlan passes authenticated capability/fault gates.
9. **IMPORTANT — Preserve the full empirical comparison:** homogeneous and heterogeneous direct multi-agent arms may follow the one-call pilot, but must appear in the final frozen comparison required by the Research Brief.
10. **OPTIONAL — Method fork only if explicitly chosen:** synthesize a persistent program before predicate realization and preregister its matched persistent-action and per-origin-router controls.

## Final verdict

**RETHINK — 6.33/10 (same-family PROVISIONAL).**

VFPS-Lite is ready for mock-only implementation as a careful one-call constrained-action architecture. It is not ready as a program-synthesis method, because the per-origin `IF` is known-condition equivalent to `NO-BRANCH` and its fixed-AST perturbation tests do not verify the resynthesizing LLM policy. The recommended path is an explicit empirical architecture pivot. A top-venue method claim requires a genuinely persistent or synthesis-time-unresolved conditional policy, eligible whole-unit data, authenticated API execution, and decisive matched controls; none currently exists.
