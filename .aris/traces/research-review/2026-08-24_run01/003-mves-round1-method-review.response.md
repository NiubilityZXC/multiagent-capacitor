# Research-Refine Round 1 Review

**Review independence:** same-family  
**Acceptance status:** provisional  
**CALIBRATION:** none

No curated known-good/known-bad proposal anchors were available, so scores use the weighted rubric without exemplar calibration.

## Frozen Problem Anchor

> Can a maturity-aware agent graph whose typed proposals are tested by executable counterfactual replay improve strictly causal, held-out capacitor forecasts over both direct LLM agents and strong specialized numerical models under matched call, token, and latency budgets?

The proposal preserves this text exactly. However, its implemented mechanism only partially realizes it: most “counterfactual” checks are software invariance tests, while MVES presently reduces to conservative finite-route selection.

## Scores

| Dimension | Weight | Score | Weighted |
|---|---:|---:|---:|
| Problem Fidelity | 15% | 8 | 1.20 |
| Method Specificity | 25% | 6 | 1.50 |
| Contribution Quality | 25% | 5 | 1.25 |
| Frontier Leverage | 15% | 4 | 0.60 |
| Feasibility | 10% | 4 | 0.40 |
| Validation Focus | 5% | 6 | 0.30 |
| Venue Readiness | 5% | 3 | 0.15 |
| **Weighted composite** | **100%** |  | **5.40/10** |

## GAP

The proposal is considerably stronger than a vague multi-agent diagram: it defines contracts, causal availability, fallback behavior, route costs, and a mathematically honest selector. The gap to the 9/10 READY bar is nevertheless structural. The finite grammar is small enough for deterministic enumeration, making four LLM roles unnecessary; making routes expressive enough for LLMs to matter destroys the mature support needed to certify their costs. The challenger selects extra tests from a cheap finite library that deterministic exhaustive execution can dominate. Thus the paper currently has excellent protocol discipline but no clearly irreducible LLM-era mechanism.

## Central assessment

### 1. Is MVES more than conservative route selection?

Not yet.

After correctly abandoning “minimum cut,” MVES becomes a multiple-choice selector over finite routes with:

- inner-replay excess loss;
- an uncertainty penalty;
- a complexity penalty;
- an instability penalty;
- fallback whenever the conservative score is nonnegative.

That is a careful conservative route/model-selection rule. The graph contributes little mathematically because route losses are evaluated at route level, not propagated compositionally through graph structure. Conflict constraints add feasibility engineering, but not yet a distinct learning principle.

The proposal needs to demonstrate something standard sparse stacking, constrained model selection, or a deterministic contextual router cannot express. At present, `SELECT_MODEL`, finite convex templates, quantile shifts, inflation, and abstention are all directly enumerable.

The key unresolved trilemma is:

1. **Coarse finite routes:** enough mature support and easy verification, but deterministic enumeration dominates LLM proposals.
2. **Expressive contextual programs:** LLM synthesis may matter, but signatures become sparse or unique and cannot receive credible mature-loss estimates.
3. **More roles/proposals:** increases diversity, but worsens support, multiplicity, API cost, and attribution without resolving either issue.

This is the main reason for `RETHINK`.

### 2. Are four LLM roles justified?

No.

The proposal specifies trajectory, context, sensor-integrity, and challenge roles, but does not show that four information views exist or that their proposals are complementary:

- Stress-2 lacks meaningful context and sensor-provenance richness.
- Benchmark-L targets remain blocked.
- The context and sensor roles may therefore abstain or restate deterministic diagnostics.
- The challenge role is dominated by exhaustive execution of the frozen tests.
- Using the same backbone controls model heterogeneity but does not prove that role decomposition is useful.

The default architecture should be one typed proposer plus a deterministic verifier. A four-role graph should be an ablation that earns inclusion only if it beats that single-proposer control under the same physical attempts and token ceiling.

### 3. Is mature support for route signatures defined?

No, and this blocks scientific implementation.

The proposal never fixes the equivalence class represented by \(p\). A signature could include:

- target and horizon;
- operator and numerical model;
- parameter bin;
- regime/disagreement/missingness bins;
- role;
- evidence-reference pattern.

If signatures include contextual evidence, most will have negligible independent-unit support. If contextual fields are removed, costs become global operator averages and cannot validate origin-specific LLM routing.

A valid construction needs:

1. A deterministic signature such as  
   \[
   \sigma=(\text{target},h,\text{operator},\text{model},\text{parameter-bin},
   \text{predeclared-context-bin}).
   \]
2. Context bins defined before LLM calls.
3. A minimum number of distinct physical training units, determined by the Design Gate—not window counts.
4. Candidate discovery and risk estimation on disjoint inner units, or fully cross-fitted predictions.
5. All frozen candidate programs evaluated on every eligible calibration origin, not only where the LLM happened to propose them.
6. Multiplicity control over searched signatures.
7. `+∞` cost whenever independent-unit support is insufficient.

Without this, the mature-cost table is either statistically unsupported or selection-biased.

### 4. Can the challenger beat exhaustive deterministic tests?

Not under the current design.

The mandatory library is finite and mostly cheap:

- future seal;
- identity permutation;
- unit equivalence;
- masks;
- bad-time ordering;
- boundary checks;
- endpoint removal;
- hash tampering;
- conflicts.

Running all applicable tests is safer and more reproducible than asking an LLM to choose extra tests. Test selection helps only if:

- tests have material compute or false-rejection costs;
- the selection budget is formalized;
- hidden faults require tests outside the mandatory set;
- the LLM can generate valid new typed transformations that deterministic enumeration cannot enumerate;
- those generated tests improve held-out fault detection at matched test-execution cost.

None is presently established. Remove the challenger from the core. The anchor requires proposals to be executable-replay tested; it does not require a separate LLM test selector.

### 5. Is the method implementable under current data/API constraints?

The mock system is implementable; the scientific method is not yet executable.

Data blockers:

- Stress-2 supports only contract and scorer sanity.
- Physical independence is unproven.
- Benchmark-L capacitance, ESR, chronology, physical identity, and outcomes remain blocked.
- No credible route-signature cost or outer-unit architecture comparison can currently be estimated.
- RUL must remain `NA`.

API blockers and inconsistencies:

- Authenticated model discovery and capability probes have not run.
- Gate-1 permits up to six physical requests and transport retries; the proposal separately states exactly four attempts and no retry for formal comparisons.
- Gate-1 uses three workers plus a fixed synthesizer for direct multi-agent arms, while MVES has three proposers plus a dependent challenger and local selection.
- Actual token matching is unavailable when provider usage is missing; the formal claim must distinguish matched requested ceilings from matched realized spend.
- Four logical roles may exceed `max_parallel_requests=3`, making their critical path systematically different.
- Model aliasing and seed behavior are unverified.

One canonical budget contract must replace these conflicting policies after capability probing.

## Dimension-specific weaknesses and fixes

### Method Specificity — 6/10

**Weakness:** Interfaces are detailed, but the statistical identity of a route, contextual generalization rule, discovery/evaluation separation, and support gate are unspecified. The system can be coded, but its cost estimates cannot yet be defended.

**Fix:** Define the route signature, context bins, candidate-discovery split, independent-unit support rule, cross-fitting procedure, multiplicity correction, and exact behavior for unseen signatures.

**Priority:** CRITICAL

### Contribution Quality — 5/10

**Weakness:** Correcting the graph optimization exposed MVES as conservative route selection. Typed contracts, maturity bookkeeping, fallback, and most validators are necessary protocol rather than a dominant method contribution.

**Fix:** Choose one of two honest framings:

- **Method fork:** one LLM synthesizes compositional, typed forecast programs whose executable behavioral contracts cannot be reproduced by the bounded deterministic search control.
- **Empirical fork:** retain the finite grammar and present a rigorous comparison showing whether agent proposals ever add value; do not claim a new graph-selection method.

Do not combine these forks.

**Priority:** CRITICAL

### Frontier Leverage — 4/10

**Weakness:** LLMs are used as four role-play selectors over a tiny enumerable action set. This does not exploit foundation-model program synthesis or broad reasoning and makes the frontier component ornamental.

**Fix:** If retaining a method claim, use one grammar-constrained LLM as an amortized synthesizer of contextual forecast programs. Generate a fixed number of candidate programs under a matched proposal budget, then execute and verify them deterministically. Compare directly against bounded symbolic search and random program generation.

**Priority:** CRITICAL

### Feasibility — 4/10

**Weakness:** Engineering fixtures are feasible, but no current dataset can estimate the proposed route costs or primary effect. API discovery, versions, retry semantics, and actual usage are unresolved.

**Fix:** Stop at mock/fault tests until the target Data Gate and AgentPlan Gate-1 pass. Before any scientific pilot, produce a route-support feasibility table from audited independent units and one canonical API budget contract.

**Priority:** CRITICAL

### Validation Focus — 6/10

**Weakness:** The proposal contains ten comparator arms plus full/random graphs, sparse stacking, role deletions, every test deletion, every validator deletion, failure injection, and multiple budget analyses. Much is necessary eventually, but the current refinement no longer looks like minimal claim-driven validation.

**Fix:** Retain three decisive blocks:

1. all required direct/numerical/hybrid arms in one common benchmark table;
2. core mechanism test: proposed method versus no verification and deterministic enumeration;
3. safety/failure qualification, explicitly outside the method claim.

Role-by-role and test-by-test deletions occur only if the simplified architecture retains those components.

**Priority:** IMPORTANT

### Venue Readiness — 3/10

**Weakness:** There is no eligible scientific dataset, no result, no established LLM necessity, and no contribution distinct from conservative routing. The same-family novelty ledger is provisional.

**Fix:** Resolve the method fork, pass the data/API gates, and demonstrate one decisive result: a verified LLM-synthesized program must beat the strong numerical champion, ordinary hybrid routing, and equal-budget deterministic program search.

**Priority:** CRITICAL

## Simplification Opportunities

1. **Delete the challenge-selector agent.** Execute all applicable deterministic tests. Counterfactual or perturbation replay remains in the architecture without an LLM challenger.
2. **Collapse trajectory, context, and sensor roles into one typed proposer.** Reintroduce role partitioning only if a one-versus-many ablation proves complementary value.
3. **Delete the MILP from the first pilot.** With one route per target–horizon and no cross-target interaction, enumerate valid routes and take a deterministic argmin. Add joint set-partitioning only if a real multi-target conflict appears.

## Modernization Opportunities

1. Replace fixed role prompting with **grammar-constrained forecast-program synthesis**: one LLM proposes a small contextual program composed from typed predicates and numerical actions; deterministic execution and replay retain control.
2. Use multiple constrained samples from that single proposer only as an inference-time search budget. Do not add RL, fine-tuning, distillation, learned judges, or dynamic agent counts before program synthesis itself proves useful.
3. If the route space remains fully enumerable, use no modernization: drop the LLM method claim and treat direct/hybrid LLMs purely as empirical comparators.

## Drift Warning

The textual Problem Anchor is preserved, but there is **methodological drift**. The proposed system has moved from a maturity-aware agent graph with executable counterfactual replay toward static conservative route selection plus software metamorphic tests. Those tests establish leakage safety and interface correctness, not necessarily counterfactual forecast validity. Either restore a genuinely expressive verified proposal mechanism or explicitly reframe the work as an empirical study.

## Priority action items

1. **CRITICAL — Resolve the expressivity–support trilemma.** State exactly what LLMs can propose that bounded deterministic search cannot, and how that proposal class obtains independent mature support.
2. **CRITICAL — Choose the method or empirical fork.** Do not preserve method-paper language while keeping a trivially enumerable route grammar.
3. **CRITICAL — Remove the challenger and default four-role topology.** Start with one proposer plus exhaustive deterministic verification.
4. **CRITICAL — Define route signatures and estimation.** Freeze context bins, discovery/evaluation separation, cross-fitting, minimum independent-unit support, multiplicity handling, and unseen-signature fallback.
5. **CRITICAL — Reconcile the API contract.** Align physical attempts, retry policy, token ceilings, parallelism, synthesizer calls, and deadline accounting with the Gate-1 protocol.
6. **IMPORTANT — Separate correctness tests from predictive verification.** Future seals, unit equivalence, timestamps, and hashes are audit gates; only mature held-out loss can validate predictive utility.
7. **IMPORTANT — Reduce the validation sketch to three decisive blocks.**
8. **IMPORTANT — Keep the claim ceiling explicit.** Until Benchmark-L target and identity gates pass, only mock and Stress-2 engineering sanity are allowed.

## Verdict

**RETHINK**

The Problem Anchor is worth pursuing, and the proposal demonstrates unusually strong protocol discipline. But the present method cannot simultaneously make LLM proposals necessary, keep routes exhaustively verifiable, and estimate mature route costs from the available independent units. That is a blocker at the core-mechanism level, not a polish issue.

A READY verdict requires a weighted score of at least 9 with no blocker. This same-family provisional review is far below that threshold.
