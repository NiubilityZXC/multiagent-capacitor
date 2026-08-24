# Research Proposal: MVES-CF——面向在线电容预测的最小验证证据支持图

**版本**：round 0  
**日期**：2026-08-24  
**当前裁决**：`REVISE / DATA-GATED`  
**review_independence**：`same-family`  
**acceptance_status**：`provisional`

## Problem Anchor

- **Bottom-line problem**：

  > Can a maturity-aware agent graph whose typed proposals are tested by executable counterfactual replay improve strictly causal, held-out capacitor forecasts over both direct LLM agents and strong specialized numerical models under matched call, token, and latency budgets?

- **Must-solve bottleneck**：在每个滚动 origin，仅使用当时可获得的电容量、ESR、工况与采集历史，判断大模型 Agent 是否能对强数值预测器产生可复现的增益；必须把 Agent 拓扑增益与更多信息、更多调用、更大 token、隐藏重试、模型异质性和回退选择分离。
- **Non-goals**：不把 fixed-role prompting、debate、majority vote、LLM-weighted ensemble、bitemporal ledger 或“首次把 LLM 用于电容”作为独立创新；不使用 LLM self-score/judge 替代数值真值；不在 endpoint 不可识别时生成 RUL；不承诺投稿结果。
- **Constraints**：公开电容数据极小；Stress-2 仅为 6 列×11 点 surrogate sanity，物理独立性未证；Benchmark-L 的 physical identity、capacity/ESR target、chronology 和 outcome Gate 尚未全部通过；主评测必须 whole-unit nested LOCO/LOVO、rolling replay、commit-before-reveal；单个 pilot 不超过 2 GPU h，并受预注册 API attempt/token/deadline 约束。
- **Success condition**：在通过 Data/Design Gate 的独立电容上，主方法同时优于强数值 champion 和最佳 matched-budget 非图混合/直接 Agent，机制消融表明 typed executable verification 与最小支持选择均不可删除；否则诚实转为负结果或审计型 empirical paper。

本提案中的“causal”只表示 **causally available past information**，不表示因果识别。没有已识别干预或有效 negative control 时，一律使用“perturbation / invariance test”，不使用因果效应语言。

## Technical Gap

已有路线分别覆盖了：数值状态空间与在线更新、RUL 动态选模、LLM residual correction、LLM ensemble routing、agentic falsification、延迟反馈路由和可追溯执行图。当前缺口不是“再加一个 Agent”，而是：

1. 直接 LLM、fixed multi-agent 和 LLM+数值模型经常允许自由修改预测，无法定位增益来自哪个可执行动作；
2. LLM critic/judge 的主观评分与未来真实预测误差没有等价关系；
3. 一条 proposal 在当前 prefix 看似合理，并不意味着它对小幅缺失、时间扰动、单位转换或身份置换稳定；
4. 普通稀疏 stacking 能选择模型，但不能检验 typed evidence、权限边界和 proposal-specific executable invariants；
5. 成熟标签稀疏且延迟，若 route cost 使用未成熟、外层或终局信息，会直接泄漏。

最小干预应当是：把 Agent 权限限制为有限的、可执行的预测路线 proposal；本地确定性验证器执行冻结的扰动测试；只用 outer-train 的成熟 inner-LOCO 数值损失估计路线成本；最后选择最小成本的已验证支持路线，任何失败逐 target 回到同一个冻结数值预测。

## Method Thesis

- **One-sentence thesis**：在固定调用和信息预算下，以成熟训练损失为成本、以可执行 typed tests 为资格约束的最小验证支持路线，能否比自由直接预测、普通数值融合和无验证混合 Agent 更准确且更可靠地完成在线电容多步预测。
- **Smallest adequate intervention**：一个有限 route library、一个 deterministic verifier 和一个 multiple-choice route selector；不训练新的大模型，不使用 LLM judge，不允许自由代码或自由连续 correction。
- **Frontier relevance**：LLM 只承担开放式但 schema-bounded 的 proposal 与 challenge selection；现代大模型的价值由“是否优于确定性枚举器”直接检验，而不是默认成立。

## Contribution Focus

- **Dominant contribution**：`MVES`（Minimum Verified Evidence Support）——对每个 target×horizon，从枚举的可执行支持路线中，在 deterministic eligibility、conflict 和 fallback 约束下选择 outer-train mature-loss conservative cost 最小的路线。
- **Optional supporting contribution**：`CF challenger`——一个只从冻结 test library 选择附加测试的 typed Agent；每个 operator 的 mandatory tests 仍由本地 manifest 自动执行，challenger 无权跳过。
- **Explicit non-contributions**：bitemporal/append-only ledger、endpoint algebra、RUL abstention、randomized edge probes、capsule replay、conformal calibration、API retry/fallback 均为必要 Eval 或系统基础设施，不与主方法并列声称创新。

## Proposed Method

### Complexity Budget

- **Frozen / reused**：数值专家库、nested LOCO replay、预测/成熟账本、数据 Gate、单位/时间规范化、区间 scorer、API attempt harness。
- **New trainable components**：0 个梯度训练网络；route costs 只由 inner replay 统计估计。
- **New method objects**：有限 route grammar、typed proposal/test/certificate、mature-loss cost table、multiple-choice selector。
- **Intentionally excluded**：动态 Agent 数量、LLM judge、在线自我修改 prompt、自由 Python、自由连续权重、general MILP route generation、随机探针参与生产选择、跨测试电容共享 outer loss。

### System Overview

```text
Past-only OriginPacket
        │
        ├── frozen numerical experts ──> points / quantiles / survival-or-NA
        │
        ├── trajectory proposer ───────┐
        ├── context proposer ──────────┼──> Proposal.v1
        ├── sensor-integrity proposer ─┘
        │
        └── challenge selector sees typed proposals only
                                      │
                   mandatory tests + selected extra tests
                                      │
                         deterministic local verifier
                                      │
                       RouteCertificate.v1 + frozen cost
                                      │
                 minimum verified support route selector
                           │                    │
                     valid route          no feasible route
                           │                    │
                    numerical action     frozen per-target fallback
                           └──────────┬─────────┘
                               durable commit
                                      │
                              later maturity/scoring
```

Primary topology uses the same backbone for all four roles. Heterogeneous models are a separate secondary factor, never silently folded into topology gain.

### OriginPacket.v1

Allowed fields:

- opaque `origin_key` and hashes；
- event time、ingestion/availability cutoff、measurement schedule known at origin；
- canonical past C/ESR/SOH prefix with units and missingness masks；
- prespecified target×horizon keys；
- identical frozen numerical candidates and outer-train-only error summaries for hybrid arms；
- allowed operating exposure and acquisition diagnostics；
- data/endpoint/budget/protocol hashes。

Forbidden fields and proxies:

- actual/future/suffix/label/EOL/failure/termination/final length/row count；
- physical unit ID、file/path/HDF5 object/Test number；
- outer-test aggregate errors or ranks；
- full-life normalization or realized future timestamps not known at origin。

Unit identifiers may exist in split/audit ledgers but are never prompt features.

### Finite Route Grammar

每个 route 必须由 allowlisted numerical actions 组成：

1. `FALLBACK_EMIT`：原样输出冻结 champion；
2. `SELECT_MODEL`：原样选择已在 inner fold 合格的数值分布；
3. `CONVEX_FUSE_BIN`：从 inner-frozen finite weight templates 中选择一个；
4. `SHIFT_QUANTILES_BIN`：只对 C/ESR/SOH 使用离散训练尺度位移；
5. `INFLATE_QUANTILES_BIN`：只允许围绕中位数按冻结倍率扩大，不允许收窄；
6. `REQUEST_RUL_NA`：仅是请求，最终 eligibility 由 endpoint compiler 决定；
7. `NO_PROPOSAL`。

RUL 不允许 LLM 直接平移 survival curve。只有 data/outcome Gate 已通过且 frozen numerical survival model 有效时，route 才可选择它；否则唯一输出为 `NA`。

### Proposal.v1

每个 role×target×horizon 最多一个 proposal：

```text
schema_version, origin_echo, role, target, horizon
evidence_refs, operator_enum, candidate_model_id
parameter_bin, signed_effect_enum, reason_code
requested_extra_test_enums, abstain
```

`additionalProperties=false`；所有引用必须 `available_at <= origin_cutoff`；禁止 free text 进入数值路径、禁止任意 forecast/cost/confidence/code/tool。自然语言可单独隔离保存，但不能进入 validator、selector 或 Eval。

### TestSpec.v1 与验证器

每个 route signature 的 mandatory tests 由 versioned manifest 冻结；challenger 只能额外选择，不能删除。最小 library：

- `FUTURE_SEAL`：改变不可访问 suffix，packet/route/output hash 不变；
- `IDENTITY_PERMUTE`：置换 ID/path/Test 元数据，模型输入与结果不变；
- `UNIT_EQUIVALENCE`：等价单位 canonicalize 后预测相同；
- `REFERENCED_SENSOR_MASK`：遮蔽被引用输入后 proposal 必须 invalid/unavailable；
- `UNREFERENCED_MASK`：遮蔽未引用辅助字段不得改变执行结果；
- `TEMPORAL_PLACEBO`：冻结的过去时序 placebo；
- `NOISE_STABILITY`：训练尺度内固定种子微扰不得跨越非相邻 action bin；
- `BAD_TIME_ORDER`：逆序/重复/未来时间必须 hard fail；
- `PARAMETER_BOUNDARY`：边界可执行，越界、interval shrink、非单调 quantile 拒绝；
- `ENDPOINT_REMOVE`：移除 endpoint support 后 RUL 必须为 NA，其他 target 不变；
- `MODEL_HASH_TAMPER`：数值模型 hash 改变时对应 route 拒绝；
- `DECLARED_CONFLICT`：相反 correction 不得同时选择。

这些是 perturbation/invariance tests；只有存在真实或已识别 intervention 时才称 counterfactual。

`RouteCertificate.v1` 记录 proposal hash、lineage/unit/type/forbidden-field 结果、mandatory/extra tests、training replay support、eligible 与 rejection code。LLM 无权输出 certificate。

### Mature-only Route Cost

在 outer-training 的 inner-LOCO rolling replay 中，先提交 fallback 与每条 schema-valid shadow route；target 成熟后才计算 route 相对 fallback 的 paired proper-loss difference：

\[
\Delta\ell_{p,i,\tau}=\ell(y_{i,\tau},q_{p,i,\tau})-\ell(y_{i,\tau},q_{0,i,\tau}).
\]

冻结 conservative cost：

\[
C_{p,\tau}=
\widehat{\Delta L}_{p,\tau}
+\kappa\,\widehat{SE}_{unit}(\Delta L_{p,\tau})
+\lambda |E_p|
+\gamma\,Instability_{p,\tau}.
\]

- loss、`κ/λ/γ`、最小成熟 unit 数和 tie rule 全在 inner training 冻结；
- 标准误按物理 unit/duplicate group 聚类，不按 windows；
- instability 为训练 condition 间的 worst deviation；
- insufficient support、invalid censoring 或 hash mismatch → `+∞`；
- outer-test unit、其他 outer folds 和未成熟 outcome 不进入 cost；
- primary outer replay 开始前封存 cost table，测试期间不修改。使用当前 device 已成熟短 horizon loss 的版本只作独立 estimand/sensitivity。

### Exact Selector

对每个 target–horizon terminal `τ` 枚举有限 executable route set `Pτ`。fallback 属于每个集合且 cost 为 0。选择：

\[
\begin{aligned}
\min_x\quad &\sum_\tau\sum_{p\in\mathcal P_\tau}C_{p,\tau}x_{p,\tau}\\
\text{s.t.}\quad
&\sum_{p\in\mathcal P_\tau}x_{p,\tau}=1,\\
&x_{p,\tau}\le V_{p,\tau},\\
&x_{p,\tau}+x_{q,\tau'}\le1\quad\text{for declared conflicts},\\
&x_{p,\tau}\in\{0,1\}.
\end{aligned}
\]

`V` 是 deterministic certificate。若 joint route 同时覆盖多个 terminals，则使用对枚举 support subgraphs 的 set-partitioning MILP；不把它称为 set cover、Steiner tree 或 minimum cut。Pilot `MVES-1` 限制每 terminal 一条 route，通常可线性扫描；只有跨 target conflict 才需要小型 exact solver。

只有 conservative excess cost `<0` 的非 fallback route 有资格；否则 fallback。必须另冻结最低 active non-fallback coverage，防止“几乎永远回退”冒充安全改进。

### Numerical Backbone

所有 hybrid arms 共享：last value、held-prefix drift、local linear、log-linear exponential、causal local-trend KF、ridge causal increment、inner-frozen nonnegative convex ensemble。GPR、TSFM 或其他专用 RUL model 仅在对应 Data/sample/outcome Gate 通过后 add-one。

点预测、quantile 和 interval 均由 numerical candidate 或训练侧 calibration 产生；LLM self-confidence 不是区间。Direct LLM comparator 可输出预注册 quantiles，但必须作为未校准分布单独评分，若校准则只使用 inner-training replay。

### Online Inference

1. label service 揭示当前 prefix；
2. 生成并哈希 OriginPacket；
3. frozen numerical experts 输出候选；
4. 四个逻辑角色按固定 slots 调用；
5. strict parse，运行 mandatory + selected extra tests；
6. 读取 outer-fold frozen cost table，exact select；
7. 合同检查失败则逐 target fallback；
8. append+fsync prediction/API/route ledger并 seal checkpoint；
9. seal 后 label service 才 reveal next；
10. 独立 maturity service 成熟并计分。

任何 timeout、malformed、semantic failure、insufficient support、solver/deadline/budget failure 都返回 byte-identical numerical fallback。迟到响应不能改写已提交行。

### AgentPlan Role

LLM 的唯一方法角色是生成有限 proposal 和选择额外 test；不充当冠军裁判。Primary topology 使用同一 backbone，以隔离 topology；heterogeneous models 单独作为 diversity factor。模型发现、能力、store/cache、token、retry 和 privacy 服从 `ARK_AGENTPLAN_GATE1_PROTOCOL.md`。

## Training / Construction Plan

1. **Numerical qualification**：在每个 outer fold 的 inner units 上选择数值模型、calibration 和 fallback。
2. **Route shadow replay**：对 inner rolling origins 运行固定 prompts；缓存 provider response；提交所有合法 route 的 shadow predictions。
3. **Maturity scoring**：label 到达后计算 normalized proper loss；RUL 使用 interval/right-censor-aware score，否则 NA。
4. **Cost freeze**：按 route signature×target×horizon 估计 unit-cluster conservative cost，封存表和 eligibility。
5. **Outer replay**：只用 frozen table 和 held-out unit 已揭示 prefix；不得用 outer result tuning。
6. **Capability replication**：每 selected API model 的合成 strict-schema probe 做 3–5 repeats；正式随机性使用冻结 repeats/seeds，provider 无 seed 时如实记录。

## Comparator Arms and Budget

| ID | Arm | 作用 |
|---|---|---|
| `N0` | strong numerical-only champion/ensemble | 0-call 锚点 |
| `D1` | one direct LLM | 直接数值预测 |
| `D4-H` | homogeneous call-matched direct | 同 backbone 四个隔离直接 forecast + deterministic aggregate |
| `D4-X` | heterogeneous direct | 模型多样性因素 |
| `NT` | LLM invokes/selects numerical tool | 直接 LLM+专用模型 |
| `RC` | bounded correction-operator tribunal | 最小 hybrid viability pilot |
| `RF` | LLM route/convex fusion | 普通 hybrid 强对照 |
| `A` | MVES without executable challenger | 主机制删减 |
| `B` | MVES-CF narrow | 提议主方法 |
| `ENUM` | deterministic route/test enumerator | LLM necessity control |

四调用比较同时要求 matched-call 和 matched-token；one-call D1 另给 combined output ceiling。所有 arms 共享 causal information、numerical library、fallback、planned keys、deadline 起点、retry policy。主要架构结果默认同 backbone；heterogeneous 对比不能代替 topology ablation。

## Failure Modes and Diagnostics

- **Data Gate 不通过**：对应 target 全部 NA/blocked，不让 Agent 绕过。
- **路线几乎全 fallback**：若 active coverage 低于 Freeze B，禁止 improvement claim。
- **确定性枚举器匹配 B**：删除 LLM necessity，保留 numerical verified-route result。
- **B 不优于 A**：删除 challenger contribution。
- **普通 sparse stacking 匹配 MVES**：删除 graph novelty。
- **多条等价最优 route 不稳定**：保留预测，删除 edge necessity/attribution。
- **模型 drift/alias**：returned model 不匹配即 fail；不声称 bitwise reproducibility。
- **provider failure**：保留 attempt denominator，byte-identical fallback。
- **物理关系不可靠**：对应 test 不启用；capacity monotonicity 不作为 universal validator。
- **censoring 假设不成立**：RUL credit/score NA，不用 complete-case 替代。

## Novelty and Elegance Argument

最接近的工作已覆盖 LLM forecast routing、residual correction、agentic falsification、delayed feedback 和 evidence graph。MVES-CF 的可证伪 delta 不是这些组件本身，而是：

1. production action 限于有限 executable route；
2. 每条 route 必须持有 deterministic perturbation certificate；
3. route cost 只来自 mature inner-LOCO proper-loss evidence；
4. 选择是数学上明确的 multiple-choice/set-partitioning support problem，fallback 保证可行；
5. matched-budget deterministic enumerator 直接检验 LLM 是否必要。

若 4 或 5 不成立，本工作不能包装为 Agent 方法论文。随机 edge probes、capsule replay 和 semantic stress suite只用于诊断，不加入方法标题。

## Claim-Driven Validation Sketch

### Claim 1: MVES-CF 是否提升真实未见电容预测

- **Minimal experiment**：在通过 Gate 且 Design simulation 有效的主 corpus 上做 nested whole-unit LOCO/LOVO rolling replay。
- **Baselines**：N0、D1、D4-H、NT、RC、RF、A、B、ENUM；D4-X 单独报告 diversity。
- **Primary metric**：Freeze B 指定的 unit-macro proper loss；同时报告 worst-condition、interval score、fallback coverage、FAIL、attempts/tokens/latency。
- **Expected evidence**：B 相对 N0 与最佳 matched-budget non-graph arm 的预注册最小相关改善候选为 5%，cluster uncertainty 排除无意义增益；阈值须由 Design Gate 冻结。

### Claim 2: executable challenger 与 LLM proposal 是否必要

- **Minimal experiment**：B vs A、ENUM、full verified graph、size-matched random support、generic sparse stacking；remove-one role/test/validator。
- **Metric**：同一 held-out loss、active coverage、false-admission on hidden perturbations、deadline/fallback rate。
- **Expected evidence**：B vs A 候选改善 2% 或 worst-shift 有预注册改善且 mean non-inferior；B 必须优于 ENUM 才允许 LLM necessity claim。

### Claim 3: 系统失败是否安全（支持性、非方法主张）

- **Minimal experiment**：合成 hidden failure injection：timeout、malformed、late response、ID/time/unit leakage、missing modality、budget exhaustion。
- **Metric**：byte-identical fallback、no late overwrite、planned denominator、ledger/seal validation。
- **Expected evidence**：所有预注册失败均被记录并安全回退；不以此替代预测精度。

## Experiment Handoff Inputs

- **Must-prove**：B 优于 N0 与最佳 matched-budget non-graph；B 优于 A；B 优于 ENUM。
- **Must-run ablations**：challenger、typing、mature cost、minimum support、role views、conflicts、validator、fallback coverage、matched-call/token。
- **Critical data**：独立物理 unit、target/units/timestamps、termination semantics；外部 corpus 优先。
- **Highest-risk assumptions**：公开数据功效不足；route signature support 稀疏；LLM proposal 可能不优于 deterministic enumeration；provider variability；所有 apparent gain 可能来自 fallback。

## Compute & Timeline Estimate

- **Gate-1 / no-network**：2–4 天，CPU only；schema、solver、mock server、fault/leak tests。
- **RC viability pilot**：1–2 天 API/cached calls，0 GPU h；Stress-2 只作 sanity。
- **MVES pilot**：通过数据 Gate 后 1–2 周；每 candidate ≤2 GPU h，本地主要为 CPU，API calls 按 frozen budget。
- **Full outer evaluation**：由独立 units/origins 和 API repeats 决定；必须先做 design simulation 与 cost estimate。
- **Paper timeline**：只有 Data Gate、main result、experiment audit、result-to-claim 通过后才进入正式 paper-writing；否则写负结果/benchmark paper。
