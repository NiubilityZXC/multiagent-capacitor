# 基于公开电容退化数据的直接与工具约束大模型Agent在线预测研究

## CAP-ACT候选裁决、证据边界与实验前冻结报告

**研究方向**：严格因果在线电容退化预测；比较纯大模型Agent、LLM Agent＋专用数值模型、最小多调用/多模型架构与强numerical-only方法  
**生成时间**：2026-08-24 15:16:18 CST  
**候选规模**：32个候选全部保留处置记录 → 3条最终执行路线 → 0个真实accuracy pilot  
**最终路线**：CAP-ACT empirical architecture study  
**审查保证**：same-family provisional  
**自动推进**：`AUTO_PROCEED=false`；human checkpoint required  
**当前状态**：mock implementation `GO`；scientific execution `BLOCKED`；paper `NOT READY`

## 摘要裁决

本项目不再把“多Agent图更复杂”或“LLM会选工具”当作贡献。VFPS的per-origin program-synthesis主张已被action-equivalence证明反驳：当分支predicate在生成前已知时，任意`IF`程序在当前origin只归约为一个可执行Action，语法数量不能证明预测表达力。候选12因此被拒为method；候选31仅保留为representation/metamorphic ablation。

当前最佳可证伪问题是：

> 在严格past-only、prediction-before-reveal、whole-capacitor sealed outer CV中，固定数据bytes、planned keys、physical attempts、requested ceilings、共同fallback和unit-level统计后，纯直接LLM、接收同一数值专家packet的直接LLM、有限typed numerical authority、以及最小四调用模型roster是否优于强numerical-only champion？

第一篇论文的dominant contribution只能是**受控的empirical architecture study**。CAP-ACT harness是支持性artifact，不是新的routing、program-synthesis、Graph Engineering或multi-agent learning原理。正、混合或严格负结果都可接受；任何结果都必须来自冻结数值Eval，不能以LLM主观评分替代。

## 1. 公开数据证据与资格

### 1.1 数据源裁决

| 数据源 | 已核验证据 | 可考虑任务 | 当前限制与裁决 |
|---|---|---|---|
| **Ren SCs**, Figshare 11522082 v1 | CC BY 4.0；DOI `10.6084/m9.figshare.11522082.v1`；`raw.rar` 2,114,703,017 bytes，发布MD5 `26a7a663217c59377c83fb2a8274466b`；113只真实Eaton 1 F/2.7 V EDLC，4 batches，最长约10,000 cycles | raw audit通过后：derived capacitance、capacitance-SOH、多步trajectory；另行Gate后可研究protocol RUL | **acquisition-only PASS**。payload尚未下载审计；无native ESR/EIS；物理failure未知；阈值EOL与删失必须冻结 |
| **Patrizi HSC**, Figshare 29153561 v2 | CC BY 4.0；DOI `10.6084/m9.figshare.29153561.v2`；MAT 225,986,697 bytes，发布MD5 `57e71c60cbae63142db44559edfa8ae0`；8只4.2 V HSC，含Ah capacity、IR、EIS描述 | 独立HSC外域的capacity-retention、IR/EIS、protocol-EOL stress | **acquisition-only PASS / separate domain**。payload尚未审计；一充电策略一device，strategy与identity完全混杂；Ah不是farad capacitance |
| Warwick energy dataset | CC BY 4.0；12 units被描述，约6条较完整trajectory | energy-SOH、anomaly或representation auxiliary stress | **AMBER**。native outcome是energy；外推EOL不得当observed RUL |
| NASA Benchmark-L / Capacitor Electrical Stress | 5.04 GB包已下载审计；reference-aware parser verifier PASS；1,752 events、9,316 slots（8,835 nonempty + 481 empty），EIS结构未见exact duplicate/nonfinite | 目前无科学建模任务 | **scientific overall FAIL**：target、physical identity、chronology/outcome/RUL仍blocked；不得因parser成功运行模型 |
| NASA Stress-2 | 6列surrogate × 11 points；C-loss与ESR-increase | parser、rolling replay、scorer和删失sanity | **sanity only**。physical independence未证明；约5个interval C-EOL、1个unknown/right-like endpoint；ESR无EOL；不能支持跨电容精度主张 |

Ren与Patrizi的元数据、许可、payload route和published digest已核验，但“公开可下载”不等于“row-level target可用”。两者必须经过identity、chronology、units、duplicates、derivation、termination/censoring和whole-unit split Data Gate后才可进入accuracy。

### 1.2 冻结target语义

- **电容量 `C`**：farad-valued target只能由native字段或冻结的constant-current waveform derivation得到。Ren需审计`C=|I|Δt/|ΔV|`的segment、IR drop、符号、voltage bounds与聚合；Patrizi的`Cap_ch/Cap_dis`是Ah，不能重命名为farads。
- **ESR/IR**：Ren当前为`NA`。Patrizi的IR不自动等于ESR；EIS-based ESR必须冻结frequency selection、interpolation、units和measurement convention。
- **SOH**：例如`SOH_C(t)=C(t)/C_ref`，其中reference、stabilization period、per-device normalization和方向必须由outer-training规则冻结。Ah-SOH、farad-SOH、IR-SOH和energy-SOH分别报告。
- **EOL/RUL**：`RUL(o)=tau_EOL-o`只在time/cycle axis、threshold、first-crossing与censor rule可识别时定义。文件末尾、最大cycle或外推endpoint不是observed EOL。未知或删失endpoint不能进行ordinary exact-RUL point-error评分。
- **异常风险**：预注册未来horizon内threshold crossing、innovation异常或跨模态不一致；不能把生命周期后半段作为异常标签。

## 2. 文献与新颖性边界

同族web查新已发现强碰撞：TimeSeriesScientist、Nexus、REATS、TimeRouter、Time Series Augmented Generation、agentic forecasting position work、多Agent forecasting以及zero-shot direct LLM forecasting已经覆盖模型选择、融合、tool use、multi-agent decomposition与直接数值预测。现代supercapacitor state-space RUL和film-capacitor degradation/survival/Bayesian updating也要求强numerical controls。

因此当前新颖性裁决为：

| 主张 | 裁决 |
|---|---|
| 新的Agent forecasting/routing/fusion/multi-agent方法 | **LOW；禁止主张** |
| action-only typed controller作为预测机制 | **LOW；有限专家router** |
| capacitor-specific authority-factorized empirical study | **MEDIUM, unconfirmed** |
| top-ML method positioning | **RED** |
| PHM/reliability/industrial-AI empirical positioning | **AMBER pending evidence** |

安全表述是：

> 我们对在线电容退化预测中的直接与tool-grounded LLM Agent架构进行受控实证研究，采用whole-device rolling replay、information/attempt-aware controls、deterministic numerical authority和failure-retaining evaluation。

禁止使用“first agentic time-series forecaster”“novel LLM router”“new multi-agent framework”“program-synthesis expressivity”或“causal counterfactual verification”。冻结数据、arms、models和results后仍需独立full-text novelty audit。

## 3. 推荐路线（最终排名）

### 3.1 Rank 1 — CAP-ACT primary one-call study

- **Method（实际执行）**：
  1. 每个rolling origin只构造past-only `OriginPacketRaw.v1`和`OriginPacketHybrid.v1`；后者加入所有冻结数值候选及outer-training-only误差/状态摘要。
  2. 在同一planned-key manifest上运行numerical-only、纯direct LLM、same-packet direct LLM、tool selection、fusion、bounded correction、unified Action controller和non-LLM selector。
  3. 每个API arm只做一个physical attempt，无accuracy retry；provider响应结束后才允许本地deterministic execution。
  4. prediction durably committed后才揭示下一事件；outcome独立成熟后按physical unit计分。
- **Hypothesis**：至少一种LLM authority边界能在不牺牲failure-retaining coverage与proper interval score的前提下优于强`N0`；若没有，则形成严格negative result。
- **Minimum scientific experiment**：一个通过Data Gate的multi-unit primary fleet、多个authenticated backbones、sealed outer whole-unit CV、完整one-call arms和paired unit-level inference。
- **Expected outcome**：允许direct positive、hybrid-only positive、simple-subset positive或all-negative；每种分支对应不同且受限的claim。
- **Novelty**：empirical design `MEDIUM, unconfirmed`；method novelty `LOW`。
- **Feasibility**：mock实现可行；真实运行受约2.34 GB新payload、数据审计、API capability、请求成本与whole-unit样本量约束。
- **Risk**：HIGH scientific risk；数据target或API Gate可能阻断，也可能得到null。
- **Contribution type**：empirical/diagnostic + reproducibility artifact。
- **Pilot result**：`SKIPPED/BLOCKED`；尚无真实accuracy结果。
- **Reviewer likely objection**：这是拥挤的Agent benchmark模板，且typed authority、serialization与fallback仍是package effect。
- **Why do this**：无论结果正负，都直接回答LLM在物理退化预测中是否有可测数值价值，而不是展示更复杂的Agent图。

### 3.2 Rank 2 — Minimal `D4-H` / `D4-X`

- **Method（实际执行）**：
  1. 预先seal同backbone四次随机direct forecasts与四模型roster各一次forecast。
  2. 使用同一compact numeric schema、四attempt envelope、workflow deadline和componentwise median aggregator。
  3. 本地验证quantile/interval nesting；whole-bundle失败提交共同fallback。
  4. 把四次输出视为一个origin cluster，并与每个constituent的one-call结果比较。
- **Hypothesis**：repeat sampling或sealed heterogeneous roster可能改善forecast risk/cost Pareto；它们不自动证明multi-agent reasoning或diversity causality。
- **Minimum scientific experiment**：primary one-call block之后，在相同eligible keys运行`D4-H,D4-X`；若要声称diversity，增加每个constituent的homogeneous four-repeat control。
- **Expected outcome**：`D4-H`增益只支持sampling+aggregation；`D4-X`增益默认只支持roster package。
- **Novelty**：LOW method / useful required control。
- **Feasibility**：API成本约为one-call arm的四倍；只有能力与成本Gate通过后运行。
- **Risk**：MEDIUM-HIGH；可能只增加成本、延迟和failure surface。
- **Contribution type**：empirical resource-response/roster diagnostic。
- **Pilot result**：`SKIPPED/BLOCKED`。
- **Reviewer likely objection**：这只是multi-call ensemble，不是多Agent推理。
- **Why do this**：用户明确要求multi-agent路线；最小matched control可以检验它，而不先引入debate/hierarchy/dynamic routing混杂。

### 3.3 Rank 3 — Numerical-only negative-result fallback

- **Method（实际执行）**：
  1. 在每个outer fold的training units内用nested whole-unit CV选择强numerical champion。
  2. 注册last value/drift、local linear/exponential、KF/state-space/PF、ridge/GPR/传统ML、数据许可的专用RUL模型与现代时序模型。
  3. 使用与Agent arms相同的causal origin、target、horizon、interval和planned denominator。
  4. 若API arms不胜，冻结`N0`为最终结果并停止增加Agent复杂度。
- **Hypothesis**：在小样本物理退化数据上，强numerical-only可能在accuracy、reliability与cost上占优。
- **Minimum scientific experiment**：同一sealed outer CV中的`N0`对全部API arms。
- **Expected outcome**：一个跨backbone、跨primary/external scope、unit-level power充分的null可形成有价值negative result；单模型/单小数据null只算local finding。
- **Novelty**：方法LOW；严格Agent负结果的实证价值取决于范围和power。
- **Feasibility**：CPU优先，数据Gate通过后先于API runs执行。
- **Risk**：LOW implementation / MEDIUM publication。
- **Contribution type**：numerical empirical baseline / negative-result fallback。
- **Pilot result**：尚未在新合格fleet上运行。
- **Reviewer likely objection**：没有Agent正增益时论文是否足够重要。
- **Why do this**：它防止项目为了保住Agent叙事而弱化baseline，也是任何高水平结论的必要可信度来源。

## 4. CAP-ACT系统架构

### 4.1 Primary arms

| Arm | Agent看到什么 | 可输出什么 | 本地authority |
|---|---|---|---|
| `N0` | 无API | 无 | outer-training numerical champion |
| `D1-RAW` | raw causal packet | 完整数值bundle | strict parse/common fallback |
| `D1-PACKET` | hybrid packet | 完整数值bundle | strict parse/common fallback |
| `H1` | hybrid packet | 一个`model_id` | 执行冻结模型 |
| `RF1` | hybrid packet | 一个fusion template ID | 执行冻结凸融合 |
| `RC1` | hybrid packet | identity/SHIFT/INFLATE ID | 只变换共同`b_star` |
| `ACT1` | hybrid packet | 一个19-Action ID | deterministic compile/execute |
| `ENUM-ACTION` | deterministic causal features | 无API | 19 Actions的sealed risk selector |
| `IF1` | hybrid packet | known-condition branch artifact | representation/metamorphic ablation |

`D1-RAW`是纯大模型直接预测。`D1-PACKET`接收与hybrid相同的numerical candidate bytes并直接输出数值，用于隔离expert packet信息。`H1/RF1/RC1`是authority subsets，`ACT1`是其有限union；`ENUM-ACTION`检验LLM controller是否必要。

### 4.2 Exact 19-Action authority

```text
BaseAction := 6 x EMIT | 5 x FUSE | FALLBACK
ActionPrimary := BaseAction
               | 4 x SHIFT(b_star, s)
               | 3 x INFLATE(b_star, q)
```

`b_star(target,h)`严格绑定为共同`FALLBACK/N0`champion，因此primary union为19。合法选择`FALLBACK`记为`DELIBERATE_FALLBACK`；transport/schema/verifier/deadline/crash导致相同数值bundle时记为`ERROR_FALLBACK`。`ACT-COMP96`只在appendix与`ENUM-COMP96`配对。

### 4.3 AgentPlan model boundary

用户界面中出现的模型ID目前仅是provisional roster：`doubao-seed-2.0-mini`、`glm-5.3`、`deepseek-v4-flash`、`kimi-k3`、`glm-5.2`、`kimi-k2.7-code`、`minimax-m3`、`deepseek-v4-pro`。它们的实际可调用性、returned model identity、JSON/schema能力、usage completeness、reasoning/output accounting、deadline行为和retirement状态均未通过authenticated discovery，不能写成已用模型或结果。

真实运行只从Gate通过的模型中预注册one-call backbones与D4-X roster。任何凭据必须轮换并仅由本地未跟踪环境注入；不得进入prompt、ledger、trace、配置、论文或Git历史。

### 4.4 Graph Engineering治理

Graph只组织研究过程，不直接产生预测证据：

```text
Data/source audit -> target/identity gate -> Eval freeze
 -> numerical feature/model development
 -> direct/hybrid Agent policy development
 -> deterministic code/fault review
 -> sealed replay release
 -> blind maturity/scoring
 -> zero-context result/claim review
 -> human publication/deployment decision
```

节点只交换typed、hash-addressed artifacts。任何新feature、Skill、prompt、candidate model、arm或target生成新policy generation；旧outer结果只能作为development，不能继续宣称confirmatory。Graph节点数、debate文本和LLM judge分数不计作accuracy。

## 5. 固定评测协议

### 5.1 Sealed outer whole-unit CV

本研究选择sealed outer CV，不使用矛盾的“全局untouched shadow + 同池LOCO”说法：

1. protocol development只用synthetic、mock、fault、Stress-2 sanity和schema-only metadata冻结prompt、packet、Actions、budget、metrics、failure semantics与confirmatory contrasts；
2. 每个held-out capacitor的所有fit、normalization、calibration、`b_star`、ENUM table和train-derived features只来自其余outer-training units；需要选择时在training units内做whole-unit inner CV；
3. 所有outer fold的registry、split和commands在打开任何outer score前作为单一batch seal；
4. origin先在physical capacitor内聚合，再做paired unit-level inference；rolling origins和API replicates不增加独立样本数；
5. 独立外部语料若从未参与Ren的policy/claim freeze，可作为truly untouched external-domain stress，不能与Ren池化。

### 5.2 Common planned-key state machine

每个arm收到相同有序manifest：origin、target、horizon、interval levels、availability mask和maturity rule。每个key：

```text
PLANNED
  -> execution_status in {ACTIVE, DELIBERATE_FALLBACK, ERROR_FALLBACK}
  -> maturity_status in {MATURED, NEVER_MATURED}
```

primary accuracy只在共同`MATURED` keys上比较并保留所有fallback。active-only error是selection-biased secondary diagnostic。全局不合格endpoint是protocol-level `NA`，不是arm failure。

### 5.3 Rolling replay与attempt contract

```text
reveal causal prefix
-> generate numerical candidates and canonical packet
-> fsync STARTED attempt
-> one provider attempt, no accuracy retry
-> strict parse/local execute or common fallback
-> durably commit prediction
-> reveal next event only after marker verification
-> independent maturity service opens labels and scores
```

未闭合`STARTED`在recovery时消耗attempt并fallback，不得重发；late response不可覆盖fallback。另设`resilience_v1`测试transport-only retry，但它不能混入accuracy结果。

### 5.4 Metrics与推断

- trajectory：unit-macro MASE/MAE/RMSE，按target×horizon报告；
- uncertainty：50/80/90 interval score、coverage、width/nesting；
- RUL/survival：仅在endpoint/censor Gate后使用相应proper scores；
- anomaly：AUPRC/Brier/ECE、lead time和false alarms；
- reliability/cost：planned/matured/active/deliberate/error/never-matured counts、attempts、requested/actual tokens、usage completeness、latency、local CPU与cost Pareto；
- inference：先unit macro，再paired unit-level CI/test；预注册familywise或simultaneous selected-arm rule。

不把LLM文本、自评分、理由长度或Agent投票转成综合性能分。

## 6. Claim-driven实验路线

### Phase M — mock/no-network（当前可执行）

- strict canonical JSON、packet proxy/leakage scan、Action registry/verifier；
- exact common fallback、attempt/prediction ledger、crash/late/timeout恢复；
- `ACT1/RC1/ENUM-ACTION/IF1` cardinality与metamorphic tests；
- synthetic rolling replay、secret canary、hash reorder/truncate/tamper tests；
- fresh zero-context code review。

这只能证明contract/fault行为，不证明预测精度。

### Human checkpoint H-Data/API

在继续前需要人类明确批准：

1. 下载并审计Ren约2.115 GB与Patrizi约226 MB payload，按published digest验证；
2. 使用已轮换、未跟踪的凭据执行authenticated AgentPlan discovery/capability probes；
3. 确认下载空间、API预算和将要预注册的模型roster。

对话中曾暴露的credential不得复用或入库。Gate失败时保持`BLOCKED/NA`，不能用mock结果代替。

### Phase D — Data Gate

- archive digest、extraction inventory、license/provenance；
- physical identity、chronology、units、duplicates、missingness、termination；
- target derivation与reference值；
- EOL/right/interval censor semantics；
- whole-unit/batch/protocol split feasibility；
- target×corpus eligibility matrix。

### Phase N — numerical registry

- naive/drift/local trend；
- statistical degradation与state-space/KF/PF；
- ridge/GPR/tree/boosting；
- censor-aware/specialized RUL only where eligible；
- modern time-series/TSFM only with sufficient context, units and contamination/license checks；
- nested whole-unit selection of`N0`和all-candidate packets。

### Phase A1 — authenticated one-call arms

先做capability/contract/failure probes，再在sealed eligible keys运行`D1-RAW,D1-PACKET,H1,RF1,RC1,ACT1`与`ENUM-ACTION/N0`。没有accuracy retry。多个backbone的结果分别报告并按预注册规则合成结论。

### Phase A4 — minimum multi-call

预封`D4-H,D4-X` prompt、roster、decode、aggregator、deadline和token envelope。只有完成one-call主块后打开结果；debate/hierarchy/reflection/dynamic route不属于首轮必跑。

### Phase R — result and paper gate

- experiment-integrity audit；
- unit-level statistics与worst batch/protocol analysis；
- result-to-claim矩阵与kill argument；
- independent full-text novelty、citation和numeric-claim audit；
- 只有eligible结果支持的ablation；
- 最终再生成/改进paper并同步可复现代码与非敏感artifacts。

## 7. 可证伪假设与允许主张

| 观察结果 | 允许主张 | 禁止主张 |
|---|---|---|
| Gate blocked | mock/fault harness已实现 | forecast、Agent value、RUL或venue claim |
| `N0`跨eligible corpora/backbones占优 | 测试的LLM架构在冻结条件下无增益 | “LLM永远无用” |
| `D1-RAW>N0` | 指定模型/target/horizon/budget下direct LLM有效 | general LLM superiority |
| `D1-PACKET>D1-RAW` | numerical-candidate packet package有益 | local tool authority必要 |
| `ACT1>D1-PACKET`且coverage匹配 | tested typed-authority architecture package有效 | serialization/fallback之外的纯authority因果效应 |
| `ACT1>ENUM`且胜所有subset | tested LLM controller超越deterministic selector与受限权限 | 新learning theory或universal Agent advantage |
| `ACT1`不胜`H1/RF1/RC1` | unified authority不必要 | 用复杂度或解释挽救贡献 |
| `IF1>ACT1` | branch representation改变有限proposer表现 | IF增加逐origin expressivity |
| `D4-H>one-call` | repeated sampling+aggregation在四call成本下有益 | multi-agent topology intrinsically superior |
| `D4-X>D4-H` | sealed heterogeneous roster有益 | diversity造成增益，除非能力受控 |
| 只有failure/fallback改善 | operational reliability改善 | accuracy改善 |

## 8. 泄漏与完整性硬门

以下任一项使结果失效：

1. window后随机按行切分或同一physical capacitor跨train/test；
2. scaler、feature、calibration、prompt、Action或fallback使用held-out labels/future suffix；
3. 使用final length、termination、private identity、full-life normalization或`RUL=max_cycle-cycle`；
4. prediction未durably commit就reveal下一事件；
5. error fallback被删除、重试或只在active subset报告主结果；
6. rolling origins/API calls被当作独立样本；
7. 看outer结果后继续修改同一generation并仍声称confirmatory；
8. 不合格ESR/RUL target被强行输出数值；
9. secret进入packet、response、ledger、trace、配置、paper或Git；
10. 用LLM judge或文字review替代冻结数值Eval。

## 9. 复现要求

必须公开或提供可审计替代：

- source landing/direct URLs、licenses、sizes、digests与raw-to-canonical parser；
- target/units/censoring/eligibility matrix；
- environment lock、code commit、commands与seeds；
- outer/inner split、planned-key、model/action/prompt/schema/budget manifests及hash；
- capability snapshot与provider-returned model identity；
- compact prediction/attempt ledgers、usage completeness和unit-level sufficient statistics；
- deterministic fault suite、claim matrix、已知失败与taint状态；
- 不包含credential、raw provider reasoning或受限原始数据的Git仓库。

## 10. 当前最终裁决

1. **最佳idea**：CAP-ACT one-call authority-factorized empirical study。
2. **必要multi-agent extension**：只先做matched `D4-H/D4-X`；其余拓扑后置。
3. **可靠fallback**：强numerical-only champion和可发表的negative-result路径。
4. **已拒method**：候选12/VFPS per-origin program synthesis；action-equivalence使其不能成为新方法。
5. **数据状态**：Ren/Patrizi仅acquisition-level；Benchmark-L blocked；Stress-2 sanity。
6. **新颖性状态**：Agent method LOW；empirical study MEDIUM-unconfirmed。
7. **执行状态**：只允许mock/no-network和固定实验计划；真实data/API/accuracy等待human Gate。
8. **论文状态**：`NOT READY`。在真实eligible结果、独立外域、完整matched controls、实验审计和独立查新前不得生成submission claim。

## 证据工件

- `idea-stage/DATASET_EXPANSION.md`：公开数据metadata、license、payload和target Gate；
- `idea-stage/CAP_ACT_NOVELTY_CHECK.md`：最近邻与安全新颖性措辞；
- `refine-logs/FINAL_PROPOSAL.md`：CAP-ACT clean final proposal；
- `refine-logs/REVIEW_SUMMARY.md`：四轮路线演化与同族审查；
- `refine-logs/REFINEMENT_REPORT.md`：评分、剩余风险与下一Gate；
- `idea-stage/IDEA_CANDIDATES_20260824_151618.md`：32候选最终逐项处置。

这些工件记录的是proposal与evidence boundary，不包含或暗示任何未运行的accuracy结果。
