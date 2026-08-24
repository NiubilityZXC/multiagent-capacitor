# Round 3 Refinement: CAP-ACT——直接与工具约束大模型 Agent 的严格在线实证架构

**日期**：2026-08-24  
**前轮裁决**：VFPS method `RETHINK`；empirical architecture fork `REVISE`  
**当前路线**：接受 action-equivalence 证明，删除 per-origin program-synthesis 主张；首篇论文以可证伪的 Agent 架构实证为唯一 dominant contribution。

## Problem Anchor

> Can a maturity-aware agent graph whose typed proposals are tested by executable counterfactual replay improve strictly causal, held-out capacitor forecasts over both direct LLM agents and strong specialized numerical models under matched call, token, and latency budgets?

本文把问题落实为可测量版本：在 past-only whole-unit rolling replay 中，直接数值 LLM、单调用 typed-action LLM＋专用数值模型、以及后续多 Agent 拓扑，是否在预测误差、区间质量、失败率、延迟和 token 成本上优于强 numerical-only champion。

`maturity-aware` 限定为 sealed policy 在独立 whole-unit mature outcomes 上获得资格；首版不做 outer-test 在线策略更新。`counterfactual` 在实现中改称 deterministic metamorphic/perturbation testing，除非将来存在真实干预和识别假设。

## Method and Paper Thesis

### Paper thesis

通过字节级信息匹配、逐物理 attempt 预算、typed authority、确定性执行、prediction-before-reveal 和 sealed whole-unit outer CV，可以识别大模型 Agent 的预测价值究竟来自原始时序推理、 numerical expert 信息、动作约束、模型多样性，还是仅来自更多调用、token、fallback 与数据泄漏。

### Dominant contribution

一个面向真实电容在线预测的 **matched-budget Agent architecture study**：同时比较纯直接 LLM、同信息直接 LLM、受限 numerical tool selection/fusion/correction、统一 Action controller、强 numerical-only、以及在单调用有效后才启动的 homogeneous/heterogeneous multi-agent 拓扑。

### Supporting artifact contribution

CAP-ACT harness：arm-specific strict schemas、local deterministic numerical authority、exact fallback、durable attempt/prediction ledger、blind maturity service、fault qualification 和 policy-level whole-unit selection。

### Explicit non-claims

- 不声称 action-only routing 是新的学习原理；
- 不声称 `IF` 扩大 per-origin policy class；
- 不把 policy OOF、hash ledger、Graph Engineering、Data Gate 或 fallback 说成预测精度；
- 不在真实结果前声称 LLM、多 Agent、异构模型或 hybrid 有益；
- 不在 endpoint Gate 前输出 exact RUL。

## 1. Architecture Factorization

CAP-ACT 将架构拆成两个可独立检验的轴。

### Axis A: numerical authority（primary one-call block）

| Arm | Agent 输入 | Agent 输出权限 | 本地 authority |
|---|---|---|---|
| `N0` | 无 API | 无 | outer-training numerical champion |
| `D1-RAW` | raw causal packet | 完整数值 bundle | 只做 strict parse/fallback |
| `D1-PACKET` | hybrid packet | 完整数值 bundle | 只做 strict parse/fallback |
| `H1` | hybrid packet | 一个 `model_id`/key | 执行白名单模型 |
| `RF1` | hybrid packet | 一个 `weight_template_id`/key | 执行冻结凸融合 |
| `RC1` | hybrid packet | 外层训练侧冻结 `b_star(target,h)` 上的 identity/shift/inflate | 执行 trust-region correction |
| `ACT1` | hybrid packet | 统一 19-Action primary set 中一个 action/key | deterministic compiler/executor |
| `IF1` | hybrid packet | 已知条件 IF artifact | 仅 representation/metamorphic ablation |
| `ENUM-ACTION` | 同一 train-derived causal features | 无 API | 19 Actions穷举评分 |

`D1-RAW` 是用户要求的纯大模型直接预测。`D1-PACKET` 接收与 hybrid 相同的数据 bytes并直接输出数值，隔离 numerical candidate 信息优势。`H1/RF1/RC1` 是权限子集；`ACT1` 是这些权限的统一集合，因此只有 `ACT1` 对这些子臂的比较能讨论 action-union value，不能把 `IF1` 的语法规模当作解释。

### Axis B: deliberation topology（secondary）

只有 primary block 中至少一个 API arm 在 qualification units 上满足预注册 value/cost 门，才运行：

- `D4-H`：同 backbone 四个独立 direct forecasts＋固定本地 median/trimmed aggregation；
- `D4-X`：四个不同模型 direct forecasts＋同一 aggregation；
- `ACT4-H`：同 backbone 四个 action proposals＋固定本地选择；
- `ACT4-X`：不同模型 action proposals＋同一选择；
- `REFLECT4`：同 backbone sequential self-reflection，物理 attempts总数相同；
- fixed hierarchy、parallel debate、dynamic route 作为 appendix topology，仅在四调用核心比较后 add-one。

所有四调用 arms 使用同 worker 数、同本地 aggregation 类型、同总 requested ceiling、共同 workflow deadline和相同 failure denominator。异构模型优势不能自动解释为 topology 优势。

## 2. Packets and Information Parity

### `OriginPacketRaw.v1`

- opaque origin/policy/split hashes；
- availability cutoff；
- target、unit、horizon、known schedule；
- canonical past-only short window＋long-history summaries；
- missingness 和允许的 deployment context；
- outer-training-only normalization metadata。

### `OriginPacketHybrid.v1`

在 Raw 基础上加入：

- 所有 frozen numerical candidate point/quantile bundles；
- outer-training cross-fitted macro error summaries；
- train-defined disagreement/OOD/slope/curvature/gap bins；
- Action registry、fallback 和 numerical-model hashes。

`D1-PACKET/H1/RF1/RC1/ACT1/IF1` 的 data section 使用同一 canonical bytes；instructions 和 response schema 单独 hash。报告：data bytes、total serialized request bytes、provider input tokens、requested output ceiling、actual output tokens；不把它们合成“完全 token matched”。

packet 禁止 future/suffix/EOL/termination/final length、unit/file identity、full-life normalization、outer-test error/rank、未来实际 timestamp、raw Header/path。修改 held-out suffix 或 private unit ID 后 committed packet/prediction必须不变。

## 3. Exact 19-Action Primary Authority

每个 target×horizon 的 action：

```text
BaseAction := EMIT(model_id)              # M=6
            | FUSE(weight_template_id)   # W=5
            | FALLBACK                   # 1

ActionPrimary := BaseAction
               | SHIFT(b_star(target,h), s),  s in {-1.0,-0.5,+0.5,+1.0}
               | INFLATE(b_star(target,h), q), q in {1.25,1.5,2.0}
```

其中 `b_star(target,h)` **严格绑定为共同 `FALLBACK`**：它是该 outer fold 内只用 outer-training units、通过冻结 nested-LOCO 规则选出的 `N0` 数值冠军 bundle。`FALLBACK` 因而既是12个 BaseAction 之一，也是所有 API arms 遇到执行失败时提交的同一个数值锚点；禁止为不同 arm 另选更强或更弱的 fallback。故 primary union 为 `|ActionPrimary|=12+4+3=19`，并且逐 key 精确等于 `H1` 的6个 model actions、`RF1` 的5个 fusion actions和 `RC1` 的 `b_star` identity＋7 transforms 的并集。三者与`ACT1`的对比才能识别权限子集与union。

只在 appendix 保留 `ACT-COMP96`：transform 可作用于任意12个 BaseAction，故 `12(1+4+3)=96`。它是 compositional-authority 消融，不是 primary 架构，不得与 RC1 继续声称清晰权限隔离。真实 run 若 registry 或 `b_star` 规则改变，必须生成新 protocol hash和 cardinality。

执行语义：

- `SHIFT`：point与全部 quantiles同时加 `s * scale_train(target,h)`；不做结果后选择的 clipping；非有限或违反预冻结 target contract则整个 origin bundle fallback。
- `INFLATE`：point不变，`lower'=point-q(point-lower)`，`upper'=point+q(upper-point)`；interval只能扩大。
- transform不可嵌套；连续权重/阈值/修正禁止；一个 arm必须覆盖所有 planned keys，缺一个key则整 bundle fallback。
- Agent 合法输出 `FALLBACK` 记为 `DELIBERATE_FALLBACK`；timeout、transport、schema、verifier、deadline或crash触发的相同数值 bundle 记为 `ERROR_FALLBACK`。二者数值完全相同，但状态、active coverage和失败率不可合并。
- RUL endpoint不合格时 registry不含数值RUL Action，只允许 `RUL_NA`。

`ACT1` 对每个 planned key输出一个有限 Action ID。它不是 native tool continuation：一个 provider响应结束后，本地确定性 registry才执行。

## 4. `IF1` as an Ablation, Not a Method

`IF1` 保留 15 atomic predicates、AND/OR 和 depth-2 grammar，但 branch 只可用 primary 19 Actions，仅用于两个问题：

1. explicit branch schema是否改变有限模型的 elicitation/parse/fallback 行为；
2. 固定 artifact 在预注册 branch-flipping packet perturbation下是否满足 branch-specific metamorphic contract。

它与 `ACT1` 在 committed action class上严格等价。在225个 predicates、不同branch的规则下，raw canonical syntactic cardinality为 `19+225*19*18=76,969`，但 origin-specific quotient只有19。原 2,052,096 语法只作 `IF-COMP96` appendix ablation。任何 IF1增益只能表述为 schema/representation effect。对 perturbed packet 重新调用 LLM 是另一次 physical attempt，不能用固定AST replay冒充完整policy稳定性。

## 5. Deterministic `ENUM-ACTION`

对 development units 的 whole-unit cross-fitted records，机械执行全部19 primary Actions并生成每 target×horizon、context stratum 的 unit-level loss table。`ENUM-COMP96` 只与 `ACT-COMP96` 在 appendix 成对。

冻结 pessimistic score：

\[
S(a,x)=\mu_g(a)+I[n_z\ge n_{min}]\lambda_z\{\mu_z(a)-\mu_g(a)\}
+\kappa SE_{chosen}(a)+\eta complexity(a).
\]

- 若当前 `z(x)` 独立unit不足，机械回退 global mean/SE并记录 `stratum_unqualified=true`，不得全部设为 `+inf`；
- `pi_ENUM(x)=argmin_{a in A} (S(a,x), complexity(a), action_hash(a))`；
- mean、cluster SE、`n_min/lambda/kappa/eta`、loss、feature bins和 tie rule在 policy-validation前seal；
- 若没有冻结 confidence construction和multiplicity，不称 `UCB`；
- 每key独立选择仅在冻结 primary loss可加分解时允许；否则枚举预注册 bundle templates；
- 报告19次本地评分/执行的CPU、wall time和development label usage，不称与LLM pretraining compute匹配。

`ENUM-ACTION` 是 action necessity 的主要算法 control；`IF1` 的两百万语法不进入 primary search。

## 6. Policy Registry and No Adaptive Reuse

完整 policy identity包括：model/version rule、prompt、packet/response schemas、decode、Action registry、numerical models、fallback、compiler/verifier、budget、capability snapshot。

本研究选择 **sealed outer CV**，不再把同一批单位称为“全局 untouched shadow cohort”。

1. protocol-development sandbox：只允许 synthetic、Stress-2 sanity、mock/fault fixtures和 outer-data 的 schema-only metadata；确定 prompt、feature、Action、budget和全部验收规则；
2. sealed outer whole-unit CV：对每个 outer unit，numerical fit/scaler/calibration、`b_star`、ENUM risk table和任何 train-derived metadata只能来自其余 outer-training units；需要选择时在 outer-training 内再做 whole-unit inner CV；
3. single batch release：所有 outer folds 的 registry/split/commands在揭示任何 outer score前共同 seal；整批完成前不改 prompt、arm、阈值或 hypothesis，完成后才一次性分析。

一个单位可以作为别的 outer fold 的训练单位，因此它不是全局 untouched；可识别的量是 sealed outer-CV generalization。任何看过 outer 结果后的修改均是新 generation，旧 outer 数据只能作为 development，不能再宣称 confirmatory。Holm不能修复自适应复用。API replicates不能增加独立unit数。Patrizi 等独立语料若全程不参与 Ren policy/模型/claim 冻结，可另报真正 untouched external-domain stress test，但不得与 Ren outer-CV 池化。

每个 arm 在回放开始前获得完全相同的 `PLANNED` key manifest。每个 planned key 必须恰有一个 `execution_status ∈ {ACTIVE, DELIBERATE_FALLBACK, ERROR_FALLBACK}`，流结束后再恰有一个 `maturity_status ∈ {MATURED, NEVER_MATURED}`。主准确率只在共同 `MATURED` keys 上比较并保留所有 fallback；active-only结果为次要诊断，`NEVER_MATURED` 不得删除且不伪造标签。origin先unit内聚合、再unit宏平均。

## 7. Attempt, Budget and Blind Replay Contracts

`accuracy_v1`：每logical slot恰好一个physical attempt、无retry。`resilience_v1`：共同的transport-only retry规则，独立 protocol hash和结果表。

```text
reveal prefix snapshot
-> local numerical candidates
-> canonical packet
-> fsync STARTED attempt and parent dir
-> provider request
-> FINISHED or consumed-ambiguous failure
-> strict parse/local execute or exact fallback
-> fsync prediction/checkpoint and atomic durable marker
-> reveal service verifies marker
-> reveal next event
-> independent maturity service opens labels and scores
```

未匹配 `STARTED` 在crash recovery中算已消耗attempt并提交fallback；accuracy run不得重发。late response不可覆盖fallback。每次physical attempt独立记录provider-returned model、usage completeness、tokens、latency、status和hashed response ID；raw response/reasoning和凭据不进入public ledger。

## 8. Graph Engineering Scope

Graph Engineering 用于开发治理，不进入主方法图：

- data/evidence audit；
- Eval freeze与leakage guardian；
- numerical model/feature discovery；
- Agent policy development；
- error/fault diagnosis与recovery；
- zero-context code/result/claim review；
- sealed outer-CV release arbitration；
- mechanical release arbitration。

节点只交换 typed、hash-addressed工件。任何新feature、Skill、prompt、model或arm都触发新policy generation和新的 qualification要求。Graph节点数、辩论文本和LLM judge不计预测证据；完整图放 artifact/reproducibility appendix。

## 9. Data and Target Scope

- **Ren SCs 113-unit EDLC**：仅 acquisition PASS。下载审计后若identity/chronology/derivation通过，主任务为derived capacitance、capacity-SOH、多步trajectory；ESR=`NA`。protocol EOL/RUL需另行阈值/删失Gate。
- **Patrizi HSC 8-unit**：独立外域，Ah capacity、IR/EIS；一策略一unit导致condition-device混杂。
- **Warwick**：energy-SOH auxiliary。
- **NASA Benchmark-L**：P1 overall `FAIL`，禁止建模/RUL。
- **Stress-2**：mock/replay/scorer sanity，不证明物理跨器件精度。

在 Ren/Patrizi raw Data Gate与authenticated AgentPlan capability Gate前，只运行 mock、synthetic、fault和no-network测试。

## 10. Claim-Driven Experiment Blocks

### B1 — Direct versus hybrid one-call anchor

`N0,D1-RAW,D1-PACKET,H1,RF1,RC1,ACT1,ENUM-ACTION` 在共同成熟keys比较：macro-MASE/MAE/RMSE、50/80/90 interval score/coverage、FAIL/active coverage、attempts、tokens、end-to-end latency和cost Pareto。

### B2 — Authority and representation isolation

- `D1-RAW` vs `D1-PACKET`：numerical-candidate信息；
- `D1-PACKET` vs `ACT1`：自由数值authority vs typed local authority；
- `H1/RF1/RC1` vs `ACT1`：权限子集 vs union；
- `ACT1` vs `ENUM-ACTION`：LLM controller vs deterministic train-risk selector；
- `ACT1` vs `IF1`：action-only vs branch representation。

### B3 — Safety qualification

suffix、identity、time、missing modality、endpoint removal、hash tamper、timeout、late response、crash START、ledger reorder/truncate、secret canary。安全表与预测精度表分开。

### B4 — Multi-agent topology（conditional must-run）

若任何 one-call API arm通过qualification value/cost门，再运行 `D4-H,D4-X,ACT4-H,ACT4-X,REFLECT4`；若pilot为负，最终论文仍需运行最小 `D4-H/D4-X`，以满足“单Agent负结果不能代表多Agent”的预注册边界，但不扩展到所有 hierarchy/debate/dynamic variants。

## 11. Falsifiable Hypotheses

- `E1`：是否任何API Agent在sealed outer-CV held-out units上相对N0改善primary loss且不伤FAIL/interval score；否则LLM预测价值结论为negative。
- `E2`：`D1-RAW`是否优于N0；这是纯大模型直接预测问题。
- `E3`：`ACT1`是否优于`D1-PACKET`和`ENUM-ACTION`；否则typed authority没有accuracy优势。
- `E4`：`IF1`是否优于严格matched `ACT1`；即使positive也只支持representation effect。
- `E5`：`D4-X`相对`D4-H`是否在matched aggregate budget下改善；必须同时报告backbone能力差异。
- `E6`：任何增益是否在batch/protocol holdout、context 3/4/5、不同horizon和API replicate中保持方向。

结果分支：

- direct弱、hybrid强：支持numerical authority，不支持纯LLM；
- direct/hybrid均弱：高价值负结果，停止增加Agent复杂度；
- ACT1不胜简单RF1/RC1：删除统一controller贡献；
- only heterogeneous强：作为model-diversity结果，不称多Agent graph创新；
- only fallback安全：报告active coverage，禁止“安全提升”包装；
- Data/API Gate失败：BLOCKED/NA，不用mock结果替代。

## 12. Publication Positioning

首选是 PHM/可靠性/工业AI领域的严格实证论文，题目可为：

> **Do LLM Agents Improve Online Capacitor Prognostics? A Strictly Causal, Matched-Budget Study of Direct and Tool-Grounded Forecasting**

若在至少一个113-unit主域和一个独立外域取得稳定结果、完整直接/混合/多Agent比较、并有可复现 harness，可争取高水平 PHM、IEEE TII/TIM、MSSP 或系统实证方向。没有persistent program或一般理论时不定位成NeurIPS/ICML方法创新。

## Current Readiness

CAP-ACT 已足够进入 mock-only `experiment-bridge`。真实科学结果仍有两个硬门：新公开数据的raw target/identity/split audit，以及使用轮换凭据的authenticated AgentPlan model/capability snapshot。二者通过前不运行 accuracy或RUL。
