# Round 2 Refinement: VFPS-Lite 与等信息 one-call Agent 架构试验

**日期**：2026-08-24  
**前轮评分**：6.58/10，`REVISE`  
**路线**：保留一个极简 typed-program 候选，同时预注册 empirical fallback；四调用、多角色和异构模型拓扑不进入首轮主张。

## Problem Anchor

> Can a maturity-aware agent graph whose typed proposals are tested by executable counterfactual replay improve strictly causal, held-out capacitor forecasts over both direct LLM agents and strong specialized numerical models under matched call, token, and latency budgets?

这里的 `strictly causal` 仅表示 origin 时可获得的 past-only 信息。没有干预或识别假设时，所有 verifier 测试只称 temporal、authority、perturbation 或 metamorphic checks，不称因果效应。

## Anchor Check

- **必须回答的问题**：大模型直接数值预测和大模型＋专用数值模型，是否在真实 held-out 电容在线回放中取得可重复的数值增益；若没有，必须给出可审计的负结果。
- **VFPS-Lite 的角色**：把 LLM 的自由数值权限限制为一个有限、可编译、可回退的 forecast program，并把预测资格赋给冻结 policy 的 whole-unit mature risk，而不是临时 AST。
- **不得漂移的边界**：数据审计、账本和泄漏测试是科学资格设施；不把它们冒充预测精度或方法创新。

## Simplicity Check

- 一个 online proposer；一个物理请求；无 accuracy retry；一个确定性 compiler/verifier；本地 numerical registry。
- 第一实现每个 target×horizon 一个 AST，depth≤2；禁止任意代码、连续权重、自由阈值、native tool continuation、LLM judge、自评分和在线测试器件重训。
- `D1-RAW`、`D1-PACKET`、`H1`、`RF1`、`RC1`、`VFPS1` 是不同权限的 one-call arms；不把同一个宽松 schema 复用给所有 arm。
- homogeneous/heterogeneous four-call Agent 只在 one-call 结果证明有 API value 后作为 secondary study。

## Method Thesis

一个冻结的 online LLM policy 能否在每个 origin 合成受限 typed forecast program，经确定性 temporal/unit/authority verification 后调用专用数值模型，并以 policy-level mature whole-unit qualification 获得比直接 LLM、普通 tool selection、融合、受限修正和强 numerical champion 更好的 held-out 风险。

若 `NO-BRANCH`、`ENUM` 或 `MANUAL` 与 VFPS 匹配，则删除 program-synthesis necessity，只保留严格 matched-budget 的 Agent 架构实证研究。这个 fork 在看外层结果前冻结。

## Dominant and Supporting Contributions

- **条件性 dominant contribution**：two-level validity separation——每个 origin-specific AST 只获得确定性合同证书，完整冻结 stochastic policy 才获得 mature whole-unit predictive qualification。
- **supporting contribution**：直接 LLM 与 LLM＋专用模型的字节级信息匹配、逐物理 attempt 计费和盲标签滚动回放。
- **显式非贡献**：whole-unit OOF 本身、hash ledger、Data Gate、fallback、RUL=`NA`、Graph Engineering 节点数量。

## 1. Frozen Numerical Registry

第一阶段只允许已通过 inner whole-unit qualification 的候选：

1. last value；
2. held-prefix drift；
3. local linear；
4. log-linear exponential；
5. causal local-trend KF；
6. ridge causal increment；
7. 若 Data/sample Gate 允许，可 add-one GPR 或现代时间序列模型，但不得替换主表已有模型。

每个 model 固定 target、horizon、unit、训练集 hash、参数 hash、point 和可用 quantiles。不同 target 的模型不可共用错误尺度。RUL endpoint 不合格时 registry 只暴露 `RUL_NA`。

Fallback 是 outer-training 内按 frozen loss/tie rule 选择的完整 `ForecastBundle`。任何 arm 少一个 planned key、超时、解析失败、模型 hash 不一致或 verifier 拒绝，都提交这份逐字节相同 fallback；不得修复响应或 reprompt。

## 2. OriginPacket Contracts

### `OriginPacketRaw.v1`

提供给 `D1-RAW`：

- opaque origin hash 与 availability cutoff；
- target 名、单位、horizon；
- canonical past-only prefix、known schedule、missingness；
- train-frozen normalization metadata 和允许的工况字段。

### `OriginPacketHybrid.v1`

在 Raw packet 上增加：

- 全部 numerical candidate bundles；
- train-only cross-fitted error summaries；
- train-defined disagreement、OOD、sampling-gap 和 local-shape bins；
- frozen action/predicate manifests；
- fallback bundle hash。

`D1-PACKET/H1/RF1/RC1/VFPS1` 的 packet data bytes 完全相同；只允许 instruction 与 response schema 不同。packet 禁止 unit/file identity、future/suffix/EOL/termination/final length、outer-test rank/error、全寿命归一化、未来实际时间戳和 raw Header 路径。变更 held-out suffix 后 packet hash 必须不变。

## 3. Arm-Specific Permissions

| Arm | 单次响应权限 | 本地执行 |
|---|---|---|
| `N0` | 无 API | numerical champion/fallback |
| `D1-RAW` | 从 raw causal packet 直接输出完整 point/quantile bundle | strict parse；失败 fallback |
| `D1-PACKET` | 从与 hybrid 相同的 packet 自由输出完整 bundle | strict parse；失败 fallback |
| `H1` | 输出一个白名单 `model_id` | 本地执行该 model；没有第二次 LLM/tool call |
| `RF1` | 输出白名单 `weight_template_id` | 本地固定凸组合；不得输出连续权重 |
| `RC1` | 输出 `base_action_id` 和有限 correction bin | 本地 trust-region shift/inflate |
| `VFPS1` | 输出 bounded canonical AST | 编译、执行全部适用测试、再本地运行 |
| `ENUM` | 无 API；冻结 label-blind search policy | 同 DSL、registry 与 verifier |
| `RAND/MANUAL/NO-BRANCH` | 无 API或预先冻结 policy | 同 planned denominator |

Direct arms 必须输出所有 target×horizon；禁止只返回容易的 keys。interval 必须满足 quantile monotonicity；无法提供时使用预注册 fallback interval，不能事后把点预测包装成窄区间。

## 4. ForecastProgram.v1 Exact Grammar

第一实现的 mock manifest 固定：

- `M=6` model actions；
- `W=5` frozen fusion templates；
- 一个 `FALLBACK`；因此 base actions `A0=M+W+1=12`；
- shift bins `S={-1.0,-0.5,+0.5,+1.0}`，乘 outer-training target residual scale；
- inflation bins `Q={1.25,1.5,2.0}`；
- 五个 past-only feature，每个三个 frozen bins，共 `P=15` atomic predicates。

```text
BaseAction := EMIT(model_id)
            | FUSE(weight_template_id)
            | FALLBACK

Action := BaseAction
        | SHIFT(BaseAction, shift_bin)
        | INFLATE(BaseAction, inflation_bin)

Predicate := ATOM(feature_id, bin_id)
           | AND(ATOM_i, ATOM_j)   where i < j
           | OR(ATOM_i, ATOM_j)    where i < j

Program := Action
         | IF(Predicate, Action_true, Action_false)
```

限制：transform 不嵌套；两个 branch 不得相同；每个 AST 只负责一个 target×horizon；一个 origin 的 AST 集必须覆盖完整 bundle。由此：

\[
|A|=12(1+4+3)=96,
\]

\[
|Predicate|=15+2\binom{15}{2}=225,
\]

\[
|Program|=96+225\times96\times95=2{,}052{,}096.
\]

真实 run 的 M/W/P 由 sealed manifest 决定并重新机械报告 cardinality。canonicalization 只做：严格 key order、AND/OR child hash 排序、重复 child 拒绝、相同 branches 折叠、enum canonicalization；不声称一般逻辑等价判定。

重要限制：per-origin condition 的 active branch 在当前 packet 已知，因此不预设 branching 一定增加表达力或精度。`NO-BRANCH` 具有同样 96 个 Action；若其匹配 VFPS，branch/program claim 被证伪。

## 5. Deterministic Verification

对每个 AST 执行全部适用检查：

1. strict JSON、duplicate-key、finite、exact keys、enum、depth/node size；
2. `available_at<=origin`、past-only feature lineage、known-schedule rule；
3. target/horizon/unit/type 和完整 bundle coverage；
4. key 与字符串 value 的 identity/future/termination proxy scan；
5. model/feature/bin/fallback/registry hash allowlist；
6. convex hull、shift trust region、interval只能扩大、quantile order；
7. referenced/unreferenced modality masks；
8. suffix mutation、ID permutation、time-order rejection、boundary values；
9. endpoint removal强制 RUL=`NA`；
10. deterministic execution、fallback bytes、certificate hash。

证书只证明合同合规，不证明预测正确。未通过任何一项时整 origin bundle fallback。

## 6. `ENUM-UCB` as a Frozen Online Policy

`ENUM` 不得在 origin 使用当前或未来 label。其 development 阶段在 whole-unit cross-fitted numerical records上机械执行候选 program，并对预声明 context stratum `z` 估计 per-unit loss。

冻结分数：

\[
S_{enum}(p,x)=\widehat L_{global}(p)
+\lambda_z\widehat L_{z(x)}(p)
+\kappa SE_{unit,z(x)}(p)
+\eta\,nodes(p).
\]

- 缺少 minimum independent units 的 stratum 项取 `+inf`；
- `lambda_z/kappa/eta`、loss 和 unit weighting 在 policy-validation 前冻结；
- BFS expansion order：`node_count, canonical_program_hash`；
- final tie：`S_enum, node_count, program_hash`；
- offline `max_expansions/max_program_evaluations` 和 online lookup/CPU/deadline 单独记录；
- `RAND` 每 origin 产生与 VFPS 相同数量的 AST；`MANUAL` 在 validation 前 seal；`NO-BRANCH` 保留所有 base/transform actions。

开发人时、prompt revisions、API calls、CPU expansions、admitted policy count 与 online cost 分账报告，不把 hidden LLM compute 假装成可精确匹配的 CPU expansions。

## 7. Sealed Policy Qualification

完整 `AgentPolicy` hash 包含：provider/model version rule、prompt、packet schema、response schema、grammar/registry、decode parameters、one-call budget、compiler/verifier、fallback、API capability snapshot。

正式数据分三层：

1. **development units**：prompt、grammar、feature bins、manual programs、ENUM heuristic；
2. **policy-validation units**：在全部 policy seal 后只运行一次完整 rolling replay；
3. **shadow outer units**：不得参与任何 policy修改或选择，用于最终结果。

若进行 outer LOCO，则每个 fold 的 numerical fit 和 train-side summaries 只用 outer-train；任何 policy 改动需新的未使用 validation units。所有 unique AST、invalid、timeout、fallback 和 stream-end NA 都留在 planned denominator。origin loss 先在物理 unit 内聚合，再按 unit 宏平均。API replicates 只反映同 unit 的随机性，不增加独立样本数。

一个 policy 相对 N0 的每-unit配对差为：

\[
d_i(\pi)=\bar L_i(\pi)-\bar L_i(N0).
\]

固定 registry 的 simultaneous upper bound 在 qualification 前冻结；不足功效返回 `NO_CHAMPION`。不报告 per-AST 或 per-edge performance guarantee。

## 8. Online Replay and Durable Attempts

```text
BlindEventService reveals prefix snapshot
-> numerical registry generates candidate bundles
-> build/hash arm-specific packet
-> append+fsync STARTED attempt before provider access
-> one physical request, no retry in accuracy_v1
-> strict parse, compile, verify, local execute or exact fallback
-> append+fsync FINISHED + prediction + checkpoint
-> only then reveal next event
-> independent maturity process verifies seals, opens label, scores
```

调用前预占 physical slot、requested tokens 与 deadline。timeout/late/usage-missing/model-mismatch 都占 slot；late result 不可覆盖已提交 fallback。`accuracy_v1` 与允许共同 transport retry 的 `resilience_v1` 使用不同 protocol hash 和结果表。

## 9. Graph Engineering Development DAG

Graph Engineering 组织研究过程，但不替代数值评测：

1. `Evidence/DataAuditAgent`：只生成 source/target/identity/censor ledger；
2. `EvalGuardianAgent`：冻结 split、origin keys、leak tests 与 shadow fold；
3. `NumericalLabAgent`：在 inner units 发现特征与训练候选；
4. `PolicyBuilderAgent`：只在 development units 设计 prompt/DSL/policies；
5. `FaultInjectionAgent`：执行未来后缀、身份、时间、模型 hash、超时和账本篡改；
6. `IndependentReviewAgent`：零上下文检查代码、结果与 claim；
7. `ShadowValidationAgent`：只运行 sealed policies，不给开发节点返回逐样本 label；
8. `ReleaseArbiter`：机械读取 Gate、数字指标、成本和失败账本，输出 PASS/NO_CHAMPION/BLOCKED；不得用 LLM 主观分代替指标。

所有节点通过 hash-addressed typed artifacts 通信。任何新 feature、Skill、model、prompt 或 program policy 都产生新 policy generation；不能在同一 shadow fold 上反复改进。

## 10. Data Plan and Current Eligibility

- **Ren SCs 113-unit EDLC**：source-level acquisition PASS；下载后若 parser/identity/target gate通过，主任务为 derived capacitance、capacity-SOH 和多步轨迹。无原生 ESR；RUL需独立 threshold/censor Gate。
- **Patrizi 8-unit HSC**：独立外域；Ah capacity、IR 与 EIS 可审计，但八种策略各一只，condition-unit 完全混杂。
- **Warwick**：energy-SOH auxiliary，不能改名为 capacitance。
- **NASA Benchmark-L**：P1 `overall_status=FAIL`；禁止模型/RUL。
- **Stress-2**：只做 parser/replay/scorer/mock API sanity，物理独立性未证明。

在新数据下载审计与 AgentPlan capability Gate 之前，只实现 mock、synthetic、fault、blind replay 和 no-network tests，不产生科学准确率主张。

## 11. Minimal Claim-Driven Experiments

### Block A — one-call anchor table

`N0, D1-RAW, D1-PACKET, H1, RF1, RC1, VFPS1, ENUM` 在共同 mature keys上比较 capacity/SOH macro-MASE、macro-MAE/RMSE、interval score/coverage、FAIL rate、attempts、tokens和latency。

### Block B — mechanism kill tests

`VFPS1` 对 `NO-VERIFIER, NO-BRANCH, ENUM, RAND, MANUAL`。若 ENUM/MANUAL/NO-BRANCH 匹配，则 method claim删除；若 verifier只降低 malformed rate、不改善 held-out risk或shift robustness，则只保留contract/systems claim。

### Block C — safety qualification

suffix、identity、time、missing modality、unknown termination、model hash、timeout、late response、ledger tamper 和 secret canary fault injection。此表证明运行资格，不计入预测性能优势。

Four-call homogeneous/heterogeneous/hierarchy/debate/dynamic routing 不属于首轮 must-run；只有 Block A 显示 API arm相对 N0 的数值或可靠性增益后才启动。

## Falsifiable Hypotheses and Kill Rules

- `H1`：至少一个 sealed Agent arm 在 shadow units 上显著优于 N0 且无 FAIL/coverage 伤害；否则“大模型提高预测精度”不成立。
- `H2`：VFPS1 优于 D1-PACKET、RF1、RC1 和 ENUM；否则 typed program synthesis superiority不成立。
- `H3`：D1-RAW 相对 N0 的结果直接回答纯大模型预测是否有用，不得用 D1-PACKET代替。
- `H4`：hybrid相对 D1-PACKET的差异隔离 numerical authority/constraint，而不是输入信息优势。
- **kill**：任何未来后缀改变 committed prediction；任何 test unit参与全局fit/policy qualification；任何 arm删除失败keys；任何 API结果无法对应 physical attempt；任何 RUL endpoint不合格却输出 exact RUL。

## Failure Interpretations

- Direct LLM差、hybrid好：数值 authority 有价值，不支持纯 LLM prognostics。
- Direct/hybrid均不胜 N0：报告严格负结果，停止增加 Agent数量。
- VFPS不胜普通 RF1/RC1：删除方法新颖性，保留 matched-budget architecture study。
- 只有异构模型好：先排除能力/成本差异，再讨论 diversity；不得称 topology gain。
- 数据 Gate失败：输出 BLOCKED/NA，不换阈值、不改 split、不用 synthetic结果替代真实结论。

## Current Verdict

方案已足够进入 **mock-only implementation**，尚未达到科学 accuracy run 或 top-venue READY。下一门是：实现独立 `experiments/vfps_agent/`、通过 no-network/blind-ledger/fault tests、冻结协议；随后在人工批准下下载并审计 Ren/Patrizi，完成 authenticated AgentPlan capability probe。任何真实预测结论必须等待这两个 Gate。
