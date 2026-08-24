# Round 1 Refinement: VFPS——成熟策略级验证的电容 Forecast Program Synthesis

**日期**：2026-08-24  
**前轮评分**：5.40/10，`RETHINK`  
**当前路线**：method fork；若本轮仍无法证明 LLM synthesis 不可被确定性搜索替代，则切换为 empirical architecture study。

## Problem Anchor

> Can a maturity-aware agent graph whose typed proposals are tested by executable counterfactual replay improve strictly causal, held-out capacitor forecasts over both direct LLM agents and strong specialized numerical models under matched call, token, and latency budgets?

## Anchor Check

- **Original bottleneck**：判断大模型 Agent 在严格 past-only、held-out、matched-budget 电容在线预测中是否真的带来数值增益，并使 proposal 可执行、可证伪、失败可回退。
- **Why this still addresses it**：VFPS 仍在每个 rolling origin 调用 Agent，但 Agent 输出的是 typed forecast program 而不是自由预测；程序经本地执行与扰动测试；完整 Agent policy 只用 mature inner-LOCO loss 获得资格；outer replay 仍与 direct LLM 和专用模型比较。
- **Reviewer suggestions rejected as drift**：不把工作改成纯离线程序合成，因为那会丢失在线 Agent anchor；不把数据审计本身冒充方法创新。

## Simplicity Check

- **Dominant contribution**：把在线 LLM 的自由数值预测改写为 grammar-constrained executable forecast-program synthesis，并在 **policy level** 而不是 unique-program level 用成熟 whole-unit replay 验证。
- **Removed**：四个默认角色、LLM challenge selector、route-by-route mature cost、minimum-support graph、MILP、edge credit、动态 Agent 数量、randomized probes/capsule replay 作为方法组件。
- **Why smaller**：核心只有一个 online proposer、一个 deterministic compiler/verifier、一个 numerical tool registry 和一个 policy-level maturity gate。
- **Reintroduction rule**：homogeneous/heterogeneous multi-agent 只作实验 arms；只有 one-vs-many 在相同 calls/tokens 下通过后，才可能进入后续版本。

## Changes Made

### 1. 解决 expressivity–support trilemma

- **Reviewer said**：coarse finite routes 可枚举；expressive contextual routes 每条都缺 mature support；更多 Agent 只加剧稀疏。
- **Action**：取消每条 route 的风险估计。统计对象改为完整 `AgentPolicy`（model、prompt、DSL、decoder、fallback、budget 的固定配置）。Policy 在每个 origin 可生成不同 canonical AST；其所有成功、失败和 fallback 共同进入 inner validation loss。
- **Impact**：不再声称一个临时 AST 自身“经统计验证”。可验证的主张是：冻结 policy 在独立 units 上的整体数值风险通过资格门。

### 2. 删除 challenger 和四角色

- **Reviewer said**：有限 tests 应全部执行，四个 views 在当前数据上无证据且浪费预算。
- **Action**：单 proposer 为 core；所有 applicable mandatory tests 由本地代码穷举。多 Agent 只作为 required comparator。
- **Impact**：减少 API 和叙事复杂度，直接检验 LLM synthesis 是否必要。

### 3. 用程序合成而非 enumerable selector 提供 frontier leverage

- **Reviewer said**：小离散动作空间使 LLM 只是 ornament。
- **Action**：允许 bounded-depth contextual AST，组合 predeclared predicates、numerical tools 和 bounded actions；搜索空间组合增长，但每个程序仍可静态检查和确定执行。
- **Impact**：LLM 的可检验角色变为 amortized program synthesizer；matched-budget best-first symbolic search、random grammar search 和 manual library 是直接 kill controls。

### 4. 统一 API budget contract

- **Reviewer said**：四 calls、六 attempts、retry、parallelism 与 direct synth 拓扑冲突。
- **Action**：主一调用比较禁 retry；transport resilience 另行实验。预算按 policy class 分层冻结，不把 requested ceiling 写成 realized-token equality。
- **Impact**：primary VFPS 与 D1/H1/RF 为 one-call matched control；multi-agent topologies在 four-call block 内另行比较。

## Revised Proposal

# Research Proposal: VFPS—Verified Forecast Program Synthesis for Online Capacitor Prognostics

## Problem Anchor

> Can a maturity-aware agent graph whose typed proposals are tested by executable counterfactual replay improve strictly causal, held-out capacitor forecasts over both direct LLM agents and strong specialized numerical models under matched call, token, and latency budgets?

本提案把“strictly causal”限定为 origin 时刻因果可获得的信息；没有 identification assumptions 时只称 perturbation/invariance，不称因果效应。

## Technical Gap

Direct LLM 能表达复杂诊断，却可以自由修改数值；finite hybrid router 可验证，却通常被确定性枚举替代。现有设计的核心矛盾是：如果对每个生成 route 单独估计风险，contextual program 几乎必然缺少独立 unit support；如果缩小成少量 route，LLM 又无必要。

VFPS 的关键改变是把统计资格赋给 **生成 policy**，而不是它在某个 origin 生成的唯一程序：

- 一个冻结 Agent policy 在每个 origin 生成 typed AST；
- 每个 AST 都做 deterministic static/runtime verification；
- policy 在所有 inner validation units/origins 的 planned denominator 上计分，包括 invalid、timeout 和 fallback；
- only policy-level mature risk 决定是否可进入 outer test；
- unique AST 没有单独性能保证，也不获得 edge credit。

## Method Thesis

一个 grammar-constrained online LLM policy 是否能通过合成 context-specific executable forecast programs，在 matched one-call budget 下优于直接 LLM、普通数值工具调用、强数值 champion 和同预算 deterministic program search。

## Contribution Focus

- **Dominant contribution**：policy-level mature validation for online typed forecast-program synthesis；它允许 origin-specific expressive programs，同时避免为每个稀疏 program 伪造统计支持。
- **Supporting contribution**：一个针对电容目标、时间、单位、endpoint 和 numerical tools 的小型 executable DSL/contract。
- **Non-contributions**：ledger、fallback、Data Gate、RUL=NA、API attempt accounting 和 fault tests 是资格基础设施；multi-agent 数量不是默认创新。

## Proposed Method

### 1. Frozen numerical registry

所有 hybrid arms 共用同一 inner-qualified library：

- last value；held-prefix drift；local linear；log-linear exponential；causal local-trend KF；ridge causal increment；
- inner-frozen nonnegative convex ensemble；
- GPR/TSFM/survival model 只在 sample/target/outcome Gate 通过后 add-one；
- 每 target×horizon 固定 fallback 和训练侧 calibration；
- RUL endpoint 不可识别时 registry 只提供 `NA`。

### 2. ForecastProgram DSL

程序是 canonical JSON AST，不是代码。最大 depth、node 数、predicate 数和输出 target 数预注册。

```text
Program := Action
         | IF Predicate THEN Program ELSE Program

Predicate := BIN(feature_id) IN allowed_bins
           | MISSING(modality)
           | AVAILABLE(modality)
           | AND(Predicate, Predicate)
           | OR(Predicate, Predicate)

Action := EMIT(model_id)
        | FUSE(weight_template_id)
        | SHIFT(target, signed_scale_bin)
        | INFLATE(target, scale_bin)
        | ABSTAIN_FALLBACK
        | EMIT_RUL_NA
```

限制：

- `feature_id` 仅来自 past-only deterministic registry，例如 recent slope/curvature、candidate disagreement、sampling-gap bin、missingness、train-defined OOD bin、available stress level；
- 所有 bin edges 在 outer-training 内冻结；AST 不得发明阈值；
- action 参数来自 finite manifest；不得输出 free continuous value、任意 Python、网络/tool name 或 self-score；
- `SHIFT/INFLATE` 受训练尺度 trust region；interval 只可扩大，不可伪造 calibration；
- program 的 target、unit、physical dimension 和 horizon 都由 compiler 检查；
- AST canonicalization 去除逻辑等价重复并产生 hash。

深度 2 的 conjunction/branching 与多 numerical actions 形成组合搜索空间；它不是通过增加自由数值来换表达力。

### 3. AgentPolicy.v1

一个 policy 由以下内容唯一确定：

```text
provider/model/version rule
system prompt + role instruction
OriginPacket schema
ForecastProgram grammar/hash
decoding/max-output parameters
one-call budget/deadline/no-retry rule
parser/compiler/verifier versions
numerical registry/fallback hashes
```

Policy 每个 origin 恰好一次 physical request；response invalid、timeout 或 late 均消耗该 slot并 fallback。Provider 不保证 seed 时，policy 风险包括预注册 API replicate 的随机性；不能把 lucky response 缓存成 determinism claim。

### 4. OriginPacket.v2

包含：opaque origin hash、availability cutoff、canonical past target prefix、units、missingness、known schedule、allowed context、numerical candidates、train-only error summaries、frozen bin definitions、target/horizon list、protocol hashes。

禁止：unit/file/Test identity、actual/future/suffix/EOL/termination/final length、outer-test rank/error、full-life normalization、未来实际 timestamp。修改 held-out suffix 后 packet hash 与 prediction 必须不变。

### 5. Deterministic compiler and verifier

对每个 AST 必须执行所有 applicable tests：

1. strict schema、finite、size/depth、enum；
2. temporal lineage 与 `available_at <= origin`；
3. physical unit/target/horizon type checking；
4. forbidden-field/proxy scan；
5. operator trust region、quantile monotonicity、survival/NA contract；
6. future-seal invariance、ID permutation、unit equivalence；
7. referenced/unreferenced modality masks；
8. time-order rejection、parameter boundary、model-hash tamper；
9. endpoint removal → RUL NA；
10. deterministic execution and fallback hash。

这些 tests 证明程序遵守合同，不证明其预测正确。预测效用只由成熟 held-out numerical loss 决定。

### 6. Policy-level maturity validation

Outer training 内再 whole-unit split/cross-fit：

- `policy-development units` 只用于 prompt/DSL/config design；
- `policy-validation units` 对每个冻结 policy 做完整 rolling replay；
- 更高效版本用 nested unit-level cross-fitting，但每次 policy/config 变更必须在未参与该变更的 units 上产生 OOF prediction；
- 一个 policy 的所有 origins、所有 unique AST、invalid responses、timeouts 和 fallback 都进入同一 planned denominator；
- 多个 origins 先在 unit 内按冻结权重聚合，再按 unit 宏平均；
- label 到达前只提交 prediction，成熟后才 score；
- policy selection 对预注册 registry 做 Holm/Bonferroni 或 simultaneous upper bound；
- minimum distinct validation units 和功效由 Design Gate 冻结；不足则 `NO_CHAMPION`。

对 policy `π` 相对 numerical fallback `0` 定义每 unit 配对损失差：

\[
d_i(\pi)=\bar L_i(\pi)-\bar L_i(0).
\]

保守资格分数：

\[
R^+(\pi)=\bar d(\pi)+\kappa\,SE_{unit}(d(\pi))+gamma I_{condition}(\pi),
\]

其中 `κ/γ`、loss、condition aggregation、multiplicity 和 minimum active coverage 均在 outer test 前冻结。`R+<0` 才允许 claim 为训练侧 non-inferior/beneficial；outer test 仍完整评测，不因资格不佳删除失败行。

这里不估计 unique program 或 edge 的 effect；`program_frequency`、branch activation 和 rejection reason 只作机制诊断。

### 7. Online execution

```text
reveal past-only prefix
run frozen numerical experts
build and hash OriginPacket.v2
call one frozen VFPS policy
strict parse ForecastProgram AST
compile + execute all applicable tests
if valid: execute AST on numerical candidates
else: byte-identical numerical fallback
durably commit API attempt, AST/certificate hash and prediction
only then reveal next event
later mature and score
```

### 8. What the LLM can contribute

LLM 可把多个 past diagnostics 组合为 context-specific branch program，而不需要在线梯度训练。其必要性由以下等预算 controls 证伪：

- `ENUM-BFS`：同 DSL、同 discovery information、同 candidate-evaluation/wall-time budget 的 deterministic best-first search；
- `RAND-GRAMMAR`：同 program count 的随机 grammar sampling；
- `MANUAL`：专家手写小 program library；
- `NO-BRANCH`：普通 finite route/model selector；
- `DIRECT`：同模型同 one-call token ceiling 直接输出数值；
- `TOOL/FUSE`：同模型同 one-call ceiling 直接选 numerical tool/weights。

若 ENUM/MANUAL 匹配 VFPS，删除 LLM synthesis necessity；若 NO-BRANCH 匹配，删除 program-expressivity claim。

## Comparator and topology panel

### One-call matched block（主方法检验）

| Arm | 说明 |
|---|---|
| N0 | strong numerical-only，0 API |
| D1 | single direct LLM numeric forecast |
| H1 | single LLM selects/invokes numerical tool |
| RF1 | single LLM route/fusion |
| RC1 | single LLM bounded correction operator |
| VFPS1 | single LLM typed program synthesis + exhaustive verifier |
| ENUM-BFS | deterministic same-DSL search |

D1/H1/RF1/RC1/VFPS1 同 model、past information、one physical request、requested output ceiling、deadline、no retry、fallback。ENUM 的 CPU/search/program-evaluation预算按预注册方式匹配并单独报告。

### Four-call architecture block（secondary）

| Arm | 说明 |
|---|---|
| D4-H | homogeneous direct self-consistency |
| D4-X | heterogeneous direct agents，固定同一 synthesizer |
| VFPS4-H | homogeneous independent program proposals + deterministic selection |
| VFPS4-X | heterogeneous proposals + 同一 deterministic selection |
| REFLECT4 | same-backbone self-reflection control |

这组只回答 topology/model-diversity 问题，不为 VFPS1 的 core claim 提供替代证据。matched requested ceilings 与 realized-token caliper 分开报告。

## API Budget Contract

- 正式 accuracy block：每 logical slot 1 physical attempt、无 transport retry；失败计入 denominator；
- resilience block：所有 arms 另行允许一个共同 transport-only retry，不能混入 accuracy table；
- one-call ceiling、four-call sum ceiling、deadline 和 parallelism 在 capability probe 后冻结；
- `stream=false/store=false/cache disabled/tools none`，若 capability 不统一则对应模型 blocked；
- actual attempts、usage completeness、tokens、latency、fallback 和 model-return mismatch 均为结果；
- requested ceiling 不称实际 token matched；只有 usage 完整且落入 frozen caliper 才作 matched-spend sensitivity。

## Failure Handling

Data/target Gate fail、schema/type/test fail、provider fail、deadline/budget、model mismatch、unsupported AST、RUL ineligible 均返回同一 frozen fallback。Late response 不得覆盖 commit。No-event/unknown termination 不改写成 exact RUL。

## Novelty and Elegance Argument

VFPS 不声称 typed workflow、LLM routing、program synthesis、delayed validation 或 fallback 单独新颖。精确 delta 是：

> 对在线科学 forecast Agent，把 origin-specific executable program 的表达力与独立样本支持解耦：程序逐 origin 生成并确定执行，但 predictive qualification 在冻结 policy level 通过 mature whole-unit OOF replay 完成。

这条 delta 可被直接杀死：如果 structured direct output、finite router、manual programs 或同预算 symbolic search 匹配 VFPS，LLM executable-program framing不成立。

## Claim-Driven Validation Sketch

### Block 1 — Common benchmark table

- **Claim**：VFPS1 是否在 eligible independent units 上优于 N0 和最佳 one-call direct/hybrid。
- **Systems**：N0、D1、H1、RF1、RC1、VFPS1、ENUM-BFS。
- **Metric**：Freeze B unit-macro proper loss；worst-condition、interval score、active/fallback、FAIL、tokens/latency。
- **Success**：预注册最小相关 effect 和 cluster uncertainty 同时通过；Stress-2-only 结果无科学主张。

### Block 2 — Mechanism/LLM necessity

- **Claim**：typed contextual program synthesis而非普通 routing或搜索产生增益。
- **Ablations**：no verifier、no branching、manual、RAND、ENUM、untyped structured action；相同 numerical registry/fallback。
- **Kill**：ENUM/MANUAL/NO-BRANCH 任一匹配即相应删除 LLM/program claim。

### Block 3 — Safety qualification（非方法精度主张）

- **Tests**：future leakage、ID/unit/time、missing modality、malformed、timeout、late、budget、RUL eligibility、ledger tamper。
- **Criterion**：byte-identical fallback、no late overwrite、planned denominator、sealed lineage。

## Data and Feasibility Gate

- Stress-2：仅 parser/replay/scorer/API shadow sanity；不把 6 columns 当已证独立电容；
- Benchmark-L P1 真实执行总 Gate `FAIL`：EIS reference/column/chronology结构可解析，但 causal availability、ES10 reversal、ES12 alignment、identity、duplicate、capacity、ESR/SOH、outcome/RUL 均未放行；
- scientific run 前必须有足够 independent units、明确 target/timestamp/termination，并通过预注册 design simulation；
- 没有 eligible corpus 时，只实现 mock/fault harness并停止，不写 superiority 结果。

## Must-Prove / Kill Conditions

1. VFPS1 同时优于 N0 与最佳 one-call non-program hybrid；
2. VFPS1 优于 ENUM-BFS/MANUAL/RAND；
3. no-verifier 与 no-branch ablation 显著掉点或安全失败；
4. active coverage 达到 Freeze B；
5. matched-call 与 matched-token-caliper结论一致；
6. 任何增益不能由 fallback、额外信息、retry、模型异质性或 selected-success denominator 解释；
7. endpoint 不可识别时 RUL 恒 NA；
8. 若以上任一核心条件失败，转为 empirical/negative result，不扩充组件救火。

## Compute & Timeline

- 2–4 天：DSL/compiler/verifier/mock API、policy-level replay unit tests，CPU only；
- 1–2 天：Stress-2 sanity，真实 API 仅在 Gate-1批准后，不能形成主张；
- eligible corpus 后 1–2 周：one-call block；本地≤2 GPU h/candidate，API cached and budgeted；
- one-call block通过后才运行 four-call topology block；
- 未通过 Data Gate 则不进入 scientific experiment/paper claim。
