Verdict: **BLOCKED_PROTOCOL_AMBIGUITY**

Canonical hashes are correct, and these controls are otherwise represented consistently: `11 ∪ {ARCH1}`, three fold-local candidates with `k=4∈{2,3,4}`, exact/no-match `C_k`, global `BLOCKED_ARCH_DEV`, fixed seven primary slots with `p=1` for NA, one seal/barrier/unseal, no result-driven P5/B5, no monetary analysis under the directive ledger, fixed Table 2–6 placement, and the L0–L5 claim ladder.

Remaining defects:

1. **Unpermitted MASE-definition supersession.**  
   `EXPERIMENT_PLAN.md:127-131` requires each eligible origin’s scale to use only that origin’s visible-prefix one-step naïve differences. `PLAN_A_P2_FREEZE_PROPOSAL.md:13,78-99` instead defines a fold-level, outer-training, horizon-step scale. Metric changes are not among the five allowed supersessions in `CANONICAL_SUPERSESSION_LEDGER.md:30-40`; its `:28,59` makes unlisted conflicts blocking.  
   Exact correction: retain the canonical visible-prefix one-step MASE denominator and add only a mechanical zero-scale/exclusion rule. If it is impossible, use the canonical pre-API metric-fallback/new-hash path. Do not approve the current h-step fold scale without a new explicit user authorization.

2. **ARCH1 candidates are not yet “fully concrete.”**  
   `PLAN_A_ARCHITECTURE_CANDIDATES.md:27` admits machine-executable schemas do not exist; `:112-135` never enumerates A03’s route registry, assignments, or tie-break fusion; `:153` leaves prompt bytes unhashed. Thus A03 is not the fully specified finite candidate required by the directive.  
   Exact correction: before any development result, add and hash-pin a machine-readable candidate registry, all JSON Schemas, exact prompt bytes, the complete A03 route/assignment registry, every final-decision enum/aggregator, failure transition table, and parent/data-hash visibility map.

3. **Plan B trigger timing conflicts with P6.**  
   `PLAN_A_PROBLEM_ANCHOR_ADDENDUM.md:66` makes P6 PASS part of Plan A base, but `:72` triggers Plan B immediately after statistics if base is not met. `PLAN_A_P2_FREEZE_PROPOSAL.md:156` similarly says only “complete joint run.” By contrast, `MASTER_JOINT_SEAL_PROTOCOL.md:123-125` and `DUAL_STORYLINE_PAPER_OUTLINE.md:132` correctly require P6 PASS and make P6 failure a STOP.  
   Exact correction: define states `PENDING_P6`, `PLAN_B_TRIGGERED_AFTER_P6_PASS`, and `STOP_P6_AUDIT`; add “frozen statistics **and P6 PASS**” to both earlier trigger clauses.

4. **Master admission rules exclude a valid preregistered block state.**  
   `MASTER_JOINT_SEAL_PROTOCOL.md:63` permits seal-time NA/BLOCKED only from capability, Data Gate, or canonical Stop/Go. But `PLAN_A_PROTOCOL_ADDENDUM.md:37` and `PLAN_A_ARCHITECTURE_CANDIDATES.md:163` require `ARCH1=BLOCKED_ARCH_DEV` when any required fold has no qualified candidate.  
   Exact correction: add the preregistered ARCH development qualification gate to the allowed seal-time reason list. Keep `C_k=NA_NO_MATCH` hypothesis-only; it must not block the ARCH1 arm.

5. **Ck freeze order is ambiguous.**  
   `MASTER_JOINT_SEAL_PROTOCOL.md:25` says P2 completes `C_k` matching before P3/development, while `:27` only later obtains the selected candidate/roster. Exact matching requires those realized policy identities, as shown by `PLAN_A_CK_MATCHING_PROTOCOL.md:21-39,56-86`; the master seal then expects the actual ledger at `MASTER...:42`.  
   Exact correction: P2 freezes only calipers, selection algorithm, tie order, and NA rules. After P3 and the fold-local tournament, build the exact eligibility ledger and select `C_{4,f}` before creating the master seal.

6. **Physical slot versus actual attempt semantics conflict.**  
   `PLAN_A_ARCHITECTURE_CANDIDATES.md:22` and `PLAN_A_EXECUTION_ENVELOPE.md:99-101` allow a reserved downstream slot to close as `NOT_STARTED_DEADLINE, physical_attempts=0`. Yet candidate-specific clauses at `PLAN_A_ARCHITECTURE_CANDIDATES.md:71,103,135` say downstream workers “must” be called, and `CANONICAL_SUPERSESSION_LEDGER.md:35` presents `4O_RR_API` as an unqualified execution count.  
   Exact correction: define `planned_physical_slots=4`, `provider_send_attempts∈[0,4]`, and an immutable closure for every slot. Replace “must be called” with “must be sent if its sub-deadline opens before workflow deadline; otherwise close NOT_STARTED_DEADLINE.” Label `4O_RR_API` as reserved-slot count / maximum provider attempts, never realized attempts.

7. **Recovery-rate estimand mixes incompatible lanes.**  
   `PLAN_A_P2_FREEZE_PROPOSAL.md:126` pools preregistered fault injections “or” natural failures, while `:135` uses this as a base-tier gate. The controlling directive (`pasted-text.txt:115`) and canonical protocol require `resilience_v1` and `accuracy_v1` to remain separate; `PLAN_A_EXECUTION_ENVELOPE.md:17-23` also separates the fault lane.  
   Exact correction: select one frozen source for `r_rec` before P2 seal—preferably a separately preregistered `resilience_v1` fault manifest—and report natural confirmatory failures separately. Bind the fault manifest/statistic in the master seal; never pool the two denominators.

8. **Baseline decision artifact is missing, while “strong N0” is asserted prematurely.**  
   `BASELINE_ADEQUACY_AND_LITERATURE_REVIEW.md:78-96,149-151` says the six-expert pool is inadequate for a broad “strong/modern” claim and requires a decision. `MASTER_JOINT_SEAL_PROTOCOL.md:24` requires review but does not require an explicit approve/reject artifact. Meanwhile `PLAN_A_PROBLEM_ANCHOR_ADDENDUM.md:15` and `DUAL_STORYLINE_PAPER_OUTLINE.md:23` call N0 strong.  
   Exact correction: require a signed/hash-bound `BASELINE_ADEQUACY_DECISION` before seal, choosing either approved `N0+` contents or canonical N0 with narrowed wording. Until then use “preregistered fold-local numerical champion candidate; adequacy pending.” Replace `DUAL...:140` “strongest internally tested map” with “complete preregistered positive/mixed/null/negative map.”

9. **Current P1 authority is not precisely represented in the controlling ledger.**  
   `P1_REN_PATRIZI_DECISION_INDEX.md:18-25` says acquisition evidence exists but both datasets are scientifically blocked and Ren extraction was not attempted. Yet `PLAN_A_PROBLEM_ANCHOR_ADDENDUM.md:96`, `PLAN_A_PROTOCOL_ADDENDUM.md:124`, and `MASTER_JOINT_SEAL_PROTOCOL.md:135` still say “acquisition” is currently allowed, and `CANONICAL_SUPERSESSION_LEDGER.md:18-28` has no row reconciling the canonical old human-gate state with the completed P1 decisions.  
   Exact correction: bind the Markdown/JSON P1 decision-index hashes and bundle-root hashes in the ledger/master. State current authority as read/reverification of existing P1 artifacts, static/row-level audit, documents/code/offline release review only; no new download, Ren extraction, decoder/parser, author script, repair, P2/P3/API/model/SOH/RUL/P4/P5 without new approval.

10. **No hash-pinned Plan A approval bundle exists.**  
    `PLAN_A_PROBLEM_ANCHOR_ADDENDUM.md:11`, `MASTER_JOINT_SEAL_PROTOCOL.md:16`, and `CANONICAL_SUPERSESSION_LEDGER.md:61-63` require addendum hashes, ledger hash, approval, and generation ID, but only the two canonical hashes are recorded.  
    Exact correction: create a preseal bundle manifest containing every Plan A/protocol/baseline/outline/P1-index hash, generation ID, approval state, and later the exact human-approval artifact hash. Do not treat filenames or “latest version” as identity.

11. **The seven-slot family is conceptually fixed but not statistically executable.**  
    `PLAN_A_P2_FREEZE_PROPOSAL.md:142-158` defines max-component composite p-values and Holm, but `:154` does not specify a valid reproducible inversion for component adjusted CIs, and `:160-167` does not define inference for fault-derived absolute-rate components. `MASTER_JOINT_SEAL_PROTOCOL.md:46` merely promises a future executable hash.  
    Exact correction: add a machine-readable seven-row hypothesis registry listing every component, estimand, direction, margin, resampling unit, component p-value, `max()` construction, Holm adjusted-p algorithm, simultaneous-CI inversion, and fixed NA=`p=1`; separately freeze secondary families.

12. **Fresh M3 release evidence remains absent.**  
    `MASTER_JOINT_SEAL_PROTOCOL.md:22` requires fresh full tests, secret scan, diff review, and independent release review. The latest snapshot, `M3_WORKTREE_SNAPSHOT.md:7,41-43`, records `103 passed, 1 failed` and explicitly says prior 204/245 results do not cover the tree.  
    Exact correction: after stabilizing the current tree, produce a new per-file hash/status snapshot, full-test record, secret-scan scope/result, diff review, and independent release verdict. This is permitted offline review work, but cannot authorize any downstream stage.