# Research-Refine Round 2 Review — VFPS

**Review independence:** same-family  
**Acceptance status:** PROVISIONAL  
**CALIBRATION:** none

No curated known-good/known-bad proposal anchors were available. This review uses only the local files named in the request. I did not browse or independently update the literature search. The exact VFPS fork has not received a fresh external novelty search; novelty judgments are bounded by the same-family provisional local ledger.

## Frozen Problem Anchor

> Can a maturity-aware agent graph whose typed proposals are tested by executable counterfactual replay improve strictly causal, held-out capacitor forecasts over both direct LLM agents and strong specialized numerical models under matched call, token, and latency budgets?

The anchor remains textually intact. VFPS now preserves a substantive online Agent role: a frozen LLM policy is called at every origin and emits a context-specific executable AST. Two qualifications remain. First, maturity is presently used for offline policy qualification, not online test-time credit adaptation. Second, the available verifier implements perturbation and metamorphic invariants, not identified causal counterfactuals.

## Scores

| Dimension | Weight | Score | Weighted contribution |
|---|---:|---:|---:|
| Problem Fidelity | 15% | 8.0 | 1.20 |
| Method Specificity | 25% | 7.5 | 1.875 |
| Contribution Quality | 25% | 6.0 | 1.50 |
| Frontier Leverage | 15% | 7.0 | 1.05 |
| Feasibility | 10% | 4.0 | 0.40 |
| Validation Focus | 5% | 7.0 | 0.35 |
| Venue Readiness | 5% | 4.0 | 0.20 |
| **Weighted composite** | **100%** |  | **6.58/10** |

## GAP

VFPS makes a real conceptual advance over Round 1: it removes per-AST performance claims and treats the complete stochastic Agent policy as the statistical object. This resolves the unique-program support problem in principle and gives the LLM a natural program-synthesis role. The remaining gap to READY is no longer primarily architectural bloat; it is identification and fairness. A frozen policy can be evaluated whole-unit OOF, but adaptive prompt/grammar search can still leak through reused policy-validation units. ENUM-BFS is not yet a fully specified policy because it lacks a causal, current-label-free online scoring rule. Direct and hybrid arms do not yet have explicit information-parity packets, and there is no eligible capacitor corpus on which any scientific claim can be tested. Finally, policy-level OOF validation is established model-selection logic, so the exact method novelty must come from the two-level typed-program contract and online synthesis behavior, not from relabeling ordinary validation.

## 1. Does policy-level whole-unit OOF solve the unique-program trilemma?

**Conditionally, yes.**

Changing the estimand from a unique AST to the complete policy

\[
\pi=(\text{model/version rule, prompt, grammar, decoding, verifier, fallback, budget})
\]

is statistically coherent. A stochastic policy may emit a different AST at every origin; its unit-level risk can still be estimated from all planned origins, including invalid outputs, timeouts, and fallback. No repeated AST is required. The proposal correctly limits its claim to aggregate policy risk and declines per-program or per-edge credit.

That solution is valid only under five conditions:

1. The entire policy registry is frozen before policy-validation outcomes are examined.
2. Prompt, grammar, decoder, bin definitions, manual programs, ENUM heuristic, and fallback are all treated as policy hyperparameters.
3. Any policy change after seeing validation loss receives genuinely untouched units, or the complete development process is nested inside each whole-unit outer fold.
4. API randomness is averaged within unit and never treated as additional independent units.
5. The outer claim remains aggregate policy risk; rare or unique branch safety is not inferred from the policy mean.

The current text permits repeated policy/config development followed by OOF generation, but does not close adaptive post-selection. Holm/Bonferroni corrects selection over a fixed registry; it does not repair a registry repeatedly redesigned after inspecting the same validation units. A sealed-registry, one-shot policy-validation rule is required.

Policy-level validation also does not prove that an unseen rare AST is predictively safe. Static verification can prove contract compliance, not loss. This is acceptable only if the paper states that the guarantee is policy-level average/worst-unit performance plus deterministic contract safety—not per-AST predictive validity.

## 2. ForecastProgram grammar and execution semantics

The DSL is small, typed, and substantially more defensible than free code, but several execution semantics remain ambiguous:

- `SHIFT(target, signed_scale_bin)` and `INFLATE(target, scale_bin)` do not identify the base forecast they transform. They should be unary transforms over an explicit `EMIT` or `FUSE` child, or name a frozen base model.
- It is unclear whether one AST emits one target–horizon or a multi-target bundle. The first implementation should use one target–horizon per program.
- “Logical equivalence” canonicalization is not generally cheap. Limit canonicalization to syntactic normalization: sorted commutative children, constant folding, duplicate-child removal, and canonical enum ordering.
- Exact grammar cardinality after fixing predicates, bins, actions, and depth is not reported. Without this count, the claim that the space is combinatorial but not exhaustively searchable is untested.
- `NO-BRANCH` must share the same transform/action semantics, or its ablation confounds branching with operator availability.

These are implementable fixes, but they are prerequisites for a fair program-search claim.

## 3. Is VFPS necessary versus ENUM-BFS, RAND, MANUAL, and NO-BRANCH?

The proposed controls are the right families, but `ENUM-BFS` is not yet an executable matched policy.

At an online origin, deterministic search cannot use the current forecast loss. It therefore needs a frozen causal scoring function

\[
S_{\mathrm{enum}}(\mathrm{AST},\mathrm{OriginPacket})
\]

trained or specified using policy-development information only. If BFS chooses an AST using policy-validation or outer loss, it leaks. If it merely enumerates syntax without a current-origin score, it is not a router. If it searches offline for one global conditional AST, it belongs to a different policy class than VFPS, which synthesizes a fresh AST at each origin.

A fair baseline must freeze all of the following:

- the causal AST scoring heuristic;
- BFS expansion and tie order;
- maximum expanded ASTs;
- online CPU and wall-time ceiling;
- offline development-unit access and tuning budget;
- the number of candidate deterministic policies admitted to policy validation.

The search budgets currently mix incomparable quantities. VFPS uses one remote foundation-model inference whose internal search is hidden; ENUM may execute many local ASTs; MANUAL embeds uncounted human search; prompt/DSL iteration embeds uncounted developer search. Report three budgets separately:

1. **Development budget:** human iterations, API calls, CPU search, and units used before registry freeze.
2. **Policy-selection budget:** number of frozen candidate policies tested on policy-validation units.
3. **Online budget:** physical calls, requested/realized tokens, CPU expansions/program executions, and end-to-end deadline.

`RAND-GRAMMAR` must be a frozen stochastic policy producing the same number of AST outputs per origin as VFPS. `MANUAL` must be frozen before policy validation. `NO-BRANCH` must retain the same numerical registry and action transforms. Only then does VFPS > all four support LLM synthesis necessity.

## 4. Direct-LLM and hybrid budget/information matching

The one-call block is much cleaner than Round 1, but it still needs an explicit information contract.

VFPS receives numerical candidates and training-only error summaries. A truly direct raw-history LLM should not receive those derived forecasts; otherwise it is already hybrid. Conversely, withholding them means the arms are not input-representation matched. Use two direct controls:

- `D1-RAW`: causal raw prefix/context only; fulfills the pure direct-LLM requirement.
- `D1-PACKET`: the exact VFPS OriginPacket, including numerical candidates, but required to emit final numbers directly; isolates typed program synthesis from information access.

All hybrid arms—H1, RF1, RC1, VFPS1, and D1-PACKET—must receive the byte-identical causal packet except for the output schema/instruction treatment.

Additional required clarifications:

- H1 must select a local numerical executor in its single response. A second tool-continuation LLM call would violate the one-call block.
- Requested-token-ceiling matching and realized-token matching must remain separate claims, as the proposal states.
- Compilation, tests, and numerical execution count inside the common end-to-end deadline.
- Failed requests with unknown usage remain in the denominator and cannot support matched-spend claims.
- Direct numeric outputs and program outputs need comparable target/horizon obligations and the same frozen fallback.

The secondary four-call block is still asymmetric. Some direct arms use workers plus an LLM synthesizer, while VFPS arms appear to use four proposals plus local deterministic selection. Defer this block. If later run, use the same number of workers and the same local or LLM aggregation mechanism across direct and program arms.

## 5. Does VFPS retain a substantive online Agent anchor?

**Yes, with a claim correction.**

The LLM is called once per rolling origin and maps the newly revealed causal prefix to a contextual executable program. This is not an offline prompt-discovery wrapper. The graph is minimal but real:

```text
online proposer -> compiler/verifier -> numerical executor -> commit
```

However, the current policy is **mature-qualified**, not adaptively maturity-updated during outer replay. The paper should say this explicitly. Adding within-test online policy updates would introduce a new estimand and is not needed for this version.

Likewise, future-seal, identity, unit, mask, and time-order tests are executable perturbation/metamorphic verification. They are not causal counterfactual identification. The exact Problem Anchor remains a research question, but under current data the tested method can support only “executable perturbation-verified online forecasting.”

## 6. Current data qualification and implementability

The software path is implementable, but there is no eligible scientific experiment today.

Local evidence establishes:

- Stress-2 is only a 6-column × 11-point parser/replay/scorer/API-shadow sanity resource, with unproven physical independence.
- Benchmark-L P1 has a valid sealed audit bundle but an overall Data Gate result of `FAIL`.
- EIS causal availability is blocked.
- ES10 transient chronology fails and ES12 alignment is blocked.
- physical identity and ES12/ES14 duplicate meaning are unresolved.
- capacitance, ESR/SOH, outcome, and RUL targets are blocked.
- RUL must remain `NA`.
- authenticated AgentPlan discovery and capability probes are still pending.

Consequently, VFPS may currently be implemented only as a mock/fault harness and synthetic policy-search test. No capacitor accuracy, superiority, novelty-through-performance, or multi-agent conclusion is presently executable. This is the dominant feasibility and venue blocker.

## 7. Novelty assessment within the local evidence boundary

The VFPS fork is cleaner, but its stated novelty is still too broad.

Policy-level whole-unit OOF validation is the ordinary correct way to evaluate a stochastic algorithm or policy. It solves the sparse-program support problem, but should be presented as the validity mechanism, not automatically as the novel contribution. The local novelty ledger already treats typed workflows, program/graph grammars, LLM routing, delayed validation, and semantic stress tests as crowded ingredients. It did not independently search the exact VFPS formulation.

The narrowest defensible provisional delta is:

> a two-level validity separation for online scientific forecast programs: every origin-specific AST receives deterministic temporal/unit/authority verification, while the frozen stochastic synthesis policy—not the AST—receives mature whole-unit predictive qualification.

That is coherent and falsifiable, but local evidence is insufficient to call it top-venue novel. If ENUM, MANUAL, or no-branch policies match VFPS, the LLM synthesis claim disappears. If verification changes only malformed-output rate and never predictive or shift robustness, the result is primarily a systems contract contribution.

## Dimension-specific blockers

### Contribution Quality — 6.0/10

**Weakness:** Policy-level validation is methodologically correct but not itself a new learning principle. The novelty currently rests on a combination of known program synthesis, typed workflows, and whole-unit validation.

**Minimum fix:** Make the two-level validity separation the single contribution, define precisely what deterministic verification guarantees and what policy-level OOF guarantees, and stop claiming that policy-level validation alone is the novelty. Add no second method module.

**Priority:** CRITICAL

### Feasibility — 4.0/10

**Weakness:** No eligible independent capacitor corpus or authenticated API configuration exists for the scientific experiment.

**Minimum fix:** Complete only VFPS-Lite mock/compiler/search tests now. Require a passing target/identity/chronology Design Gate and a frozen AgentPlan capability/budget snapshot before any accuracy run.

**Priority:** BLOCKER

### Venue Readiness — 4.0/10

**Weakness:** There is no result, no executable main dataset, unresolved search fairness, and only same-family provisional novelty evidence.

**Minimum fix:** Resolve ENUM policy definition and post-selection control, obtain an eligible corpus, and show VFPS1 beats N0, the strongest ordinary hybrid, D1-PACKET, and the matched deterministic search policy on untouched whole units.

**Priority:** BLOCKER

## Post-selection leakage audit

The following procedure is required:

1. Use development units for all prompt, grammar, bin, manual-program, ENUM-heuristic, and comparator design.
2. Seal a finite registry of complete policies and hashes.
3. Run each sealed policy once on untouched policy-validation units with all planned failures retained.
4. Apply the prespecified simultaneous bound to that fixed registry.
5. Freeze the selected policy before outer evaluation.
6. Any revision after policy-validation reveal is a new exploratory generation and cannot reuse those units for confirmatory qualification.

If units are too few for these layers inside outer LOCO, the Design Gate must return `NO_CHAMPION`; window-level OOF cannot substitute.

## Simplification Opportunities

1. Keep only `VFPS1`; defer the entire four-call topology block until the one-call method passes.
2. Compile one AST per target–horizon. Remove multi-target programs and cross-target conflicts from the first implementation.
3. Replace general semantic canonicalization with a small syntactic normalizer. Avoid theorem-sized machinery for logical equivalence.

## Modernization Opportunities

1. Use provider-native strict structured/grammar-constrained generation only if authenticated capability probes verify identical support across compared models. Otherwise retain strict parsing and fallback.
2. Do not add RL, fine-tuning, distillation, learned judges, or dynamic agent counts. Grammar-constrained online synthesis is already the appropriate frontier primitive.

## Minimum implementable repair

Because the composite is below 9, the smallest viable next revision is:

1. **Freeze VFPS-Lite:** one proposer, one call, no retry, one target–horizon AST, depth at most two, exhaustive deterministic tests, local numerical execution.
2. **Repair AST semantics:** define transforms as `SHIFT(base_action, bin)` and `INFLATE(base_action, bin)`; publish the exact grammar cardinality and syntactic normalization rules.
3. **Define ENUM as a policy:** specify a causal `S_enum(AST, packet)`, BFS order, expansion cap, offline tuning inputs, and online CPU/deadline budget. It must never use current or validation labels at inference.
4. **Seal search accounting:** log development API calls, human/manual revisions, deterministic expansions, frozen registry size, and online execution budgets separately.
5. **Close information parity:** add D1-RAW and D1-PACKET; make H1/RF1/RC1/VFPS1/D1-PACKET consume the same packet and use local one-response execution.
6. **Close policy selection:** use a sealed fixed registry and untouched whole-unit policy-validation; no prompt/grammar iteration after reveal.
7. **Limit the claim:** deterministic verification certifies contract behavior; whole-unit OOF certifies only frozen-policy risk; neither certifies individual AST accuracy or causal effects.
8. **Respect the data stop:** run only mock, fault, and synthetic search tests until an eligible capacitor corpus and AgentPlan Gate pass.

## Drift Warning

**PARTIAL, but improved.** The online Agent anchor is now substantive and the proposal no longer drifts into a static route table. The remaining drift is semantic: “counterfactual replay” is implemented as perturbation/invariance testing, and “maturity-aware” currently means mature offline policy qualification rather than online credit adaptation. State those boundaries rather than adding modules to force the original wording.

## Prioritized actions

1. **BLOCKER:** obtain an eligible independent-unit capacitor corpus or stop at a systems/mock paper.
2. **CRITICAL:** seal policy development and validation to eliminate adaptive post-selection leakage.
3. **CRITICAL:** turn ENUM-BFS into a fully specified causal online policy with explicit offline and online budgets.
4. **CRITICAL:** add D1-PACKET and clarify hybrid one-response execution for information/call parity.
5. **IMPORTANT:** repair AST transform semantics and report exact grammar size.
6. **IMPORTANT:** narrow novelty to two-level program-contract versus policy-risk validation; do not claim policy OOF itself as new.
7. **IMPORTANT:** defer all four-call and heterogeneous topology claims.

## Verdict

**REVISE**

VFPS is a coherent method fork and materially better than MVES. Policy-level whole-unit OOF resolves the unique-program support trilemma at the correct estimand level, provided the complete policy registry is sealed before validation. The remaining issues—especially ENUM policy definition, development-budget accounting, information parity, and post-selection control—are fixable without adding modules. The project is not READY because no eligible dataset or authenticated API configuration permits the scientific claim, and the exact novelty remains locally provisional.
