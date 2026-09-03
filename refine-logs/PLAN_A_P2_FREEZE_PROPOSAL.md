# Plan A / Plan B Joint P2 Freeze Proposal

**版本**：2026-08-28 20:30:00 +08:00  
**状态**：`DECISION_DRAFT / UNAPPROVED / BLOCKED_P1_REN / NO_MODEL_FIT / NO_API`  
**重要边界**：本文件提出完整字段、算法和候选阈值；它不是 P2 seal，也不授权 baseline fitting、power simulation、RUL scoring或API。

Ren RAR 的正式 P1 archive test 当前因 `Unsupported Method` 停止，尚无 row-level physical identity、target、origin 或 ending semantics。因而 `δ_min`、`δ_NI`、target/horizon grid、`O_R` 和实际功效现在不能科学冻结。把它们伪造为“已冻结”会违反 Data Gate 和用户关于 `δ_NI` 的工程依据要求。本文件明确区分可先批准的 policy values 与必须等待 P1 的数据依赖项。

## 1. Freeze matrix

| Item | Proposal | Current disposition |
|---|---|---|
| primary metric | canonical visible-prefix one-step unit-macro MASE | algorithm ready；`n_scale`/measurement epsilon/data eligibility blocked |
| `δ_min` | candidate `0.05` MASE units | `UNAPPROVED_EFFECT_ASSUMPTION`；需 P1 后 power audit |
| `δ_NI` | candidate `0.05` MASE units | `NOT_SEALABLE_WITHOUT_ENGINEERING_OWNER_ACCEPTANCE` |
| `π_min` | `0.80` simulated power | policy value ready for approval |
| `r_max` | `0.01` unit-macro `ERROR_FALLBACK` fraction | policy value ready for approval |
| `r_rec` | `0.99` no-retry crash-closure recovery | policy value ready for approval |
| `q_min` | `0.95` error-free closed completion by deadline | policy value ready for approval |
| WIS harm margin | `+0.05` outer-training-scale normalized unit-macro WIS | candidate, unapproved |
| error-fallback harm | `+0.01` absolute fraction vs comparator | candidate, unapproved |
| deadline completion harm | `−0.02` absolute fraction vs comparator | candidate, unapproved |
| coverage-deviation harm | `+0.02` absolute worsening in `abs(empirical−nominal)` at each 50/80/90 level | secondary harm candidate |
| operational superiority margin | `0.00` absolute; adjusted lower CI of `ARCH1−C_k` completion must be `>0` | candidate, unapproved |
| primary operational endpoint | `ERROR_FREE_CLOSED_COMPLETION_BY_DEADLINE` | candidate, unapproved |
| bootstrap | accuracy components: paired physical-unit, protocol/batch stratified, 10,000 resamples；`r_rec`: separate `resilience_v1` fault-cluster bootstrap | ready for code review only |
| multiplicity | seven composite hypotheses + Holm strong FWER `α=0.05` | candidate, unapproved |

`0.05 MASE` 在本 proposal 中仅是相对于 canonical visible-prefix one-step naïve scale 的未批准候选效应，不是“5% 容量损失”或“5% RUL误差”。当前没有外部证据把它转换成器件安全界。只有工程 owner 明确接受该归一化误差退化界，`δ_NI` 才能 seal；不得因为它容易通过而采用。

## 2. Target definitions and eligibility

每个 target 都必须绑定 `source_column(s) + physical unit + estimator + reference + direction + failure/censor semantics`：

| Target | Eligible definition | Automatic block |
|---|---|---|
| capacitance `C` | raw or deterministically estimated capacitance in farads under a frozen measurement protocol | Ah capacity、charge throughput或未标定 proxy 被重命名为 F |
| ESR | equivalent series resistance in ohms under a frozen frequency/time-domain estimator | generic `IR`、DC voltage-drop resistance或opaque EIS object被静默称 ESR |
| SOH-C | `C_t / C_ref`，其中 `C_ref`、conditioning period与方向在 unit registry冻结 | 没有 row-auditable `C_ref` 或混用 nominal/first-cycle references |
| SOH-ESR | `ESR_ref / ESR_t` 或另一预注册单调方向，reference完全冻结 | 未知 reference、频率/温度不一致 |
| RUL | 从 origin 到预冻结器件失效事件的剩余 cycle/time；支持右删失方法 | 没有可观察 terminal event、threshold只来自事后曲线、把 run termination当failure |
| anomaly risk | 未来冻结 horizon 内发生预注册 anomaly event 的概率 | 无事件标签、LLM主观风险分或以自身预测异常为真值 |

Patrizi P1 已发现 `IR` 不等于 ESR、Ah 不等于 F、SOH reference不完整、RUL终局语义不成立，因此当前 B5这些 endpoint均按正式 ledger `NA/BLOCKED`，不能用 addendum修复。

## 3. Target/horizon priority and estimand selection

必须先按工程用途排优先序，再看 numerical-only power；Agent/API结果永远不能参与。

### 3.1 Provisional engineering priority

在 P1 能证明 endpoint 合法时，建议顺序为：

1. 预冻结失效事件的 RUL（若 terminal/censor Gate通过）；
2. measured capacitance `C` 长提前量；
3. measured ESR 长提前量；
4. SOH-C / SOH-ESR 长提前量；
5. 同 target 中等提前量；
6. 同 target短提前量。

“长/中/短”必须由 row-level sampling与工程维护提前量映射为确切整数 cycles 或 elapsed-time bins，不能用 full-life百分比，因为这会泄露终局长度。当前映射为 `UNRESOLVED_BLOCKED_P1_REN`。若 RUL Gate失败，从列表机械删除，不改名为“capacity proxy RUL”。

### 3.2 Power-only mechanical selection

P1/P2 数据就绪后：

1. 生成完整 eligible target×horizon grid及工程排序；
2. 只用 N0/numerical baseline 的 outer-training/inner whole-unit CV paired residuals；
3. 在 `δ_min=0.05` 候选效应、实际 unit/batch结构和完整 multiplicity程序下做≥10,000 Monte Carlo draws；
4. 取工程排序中第一个 estimated power `≥π_min=0.80` 的组合；
5. 预先发布完整 grid、power、CI与未选 reason；
6. 若无组合达标，`NO_CONFIRMATORY_POWER`，不调用 P3/P4 accuracy API。

不得使用 ARCH1、任一候选、真实 API arm、all-unit OOF winner 或 held-out suffix 来选择 estimand。

## 4. Exact canonical MASE denominator

本 proposal 不改变 canonical `EXPERIMENT_PLAN.md:127-131` 的 MASE 语义。对每个 eligible planned key `k=(u,o,t,h)`，scale **只能**来自同一 physical unit `u` 在 origin `o` 的 `availability_cutoff` 之前已可见的 target prefix；不能使用 outer-training fleet 的全局 scale、`h`-step future differences、held-out suffix、full-life normalization或其他 unit 的数值：

```text
visible_prefix[u,o,t] = target observations whose timestamps/cycles are <= availability_cutoff[o]
eligible_one_step_pairs[u,o,t]
    = consecutive, chronology-valid, measurement-valid pairs in visible_prefix[u,o,t]
n_scale[u,o,t] = count(eligible_one_step_pairs[u,o,t])
scale[u,o,t] = mean over eligible pairs i of abs(y[u,i] - y[u,i-1])
MASE_key[u,o,t,h] = abs(y_true[u,o,t,h] - y_hat[u,o,t,h]) / scale[u,o,t]
```

`h` 决定被预测的 matured outcome，但不改变 denominator 的 one-step 定义。每个 origin 的 prefix、`n_scale`、scale、epsilon、eligibility reason与 hash必须对全部 arms共用；不得按 arm 成功、预测值或 loss改变。先在 physical unit 内对 common matured eligible keys等权聚合，再跨 unit等权宏平均。

### 4.1 Mechanical `n_scale`, measurement epsilon, and zero-scale exclusion

P2 必须在任何 API/development result前冻结以下 parameter slots及其工程依据：

- `P2_SLOT_N_SCALE_MIN`：一个 origin-scale 至少需要的 chronology-valid one-step pairs数；
- `P2_SLOT_MEASUREMENT_RESOLUTION[t]`：来自 P1 schema、仪器分辨率或明确量化规则的 target-specific resolution；
- `P2_SLOT_SCALE_EPSILON_RULE`：只由 measurement resolution和可见 prefix 的有限值机械计算，不能由 API结果、通过难易或 held-out suffix决定；
- `P2_SLOT_ZERO_SCALE_EXCLUSION_RULE`：对 `n_scale`不足、scale非有限或 `scale <= epsilon` 的 key给出固定 reason code和统一 exclusion语义。

这些 slots 当前均为 `UNRESOLVED_BLOCKED_P1_REN`；不得伪填常数，也不得通过给 denominator 加 arbitrary epsilon 把不合格 key救活。建议的机器 reason codes至少为：`INSUFFICIENT_VISIBLE_PREFIX_PAIRS`、`NONFINITE_VISIBLE_PREFIX_SCALE`、`ZERO_OR_RESOLUTION_SCALE`、`CHRONOLOGY_INVALID_SCALE_PAIR`。

若首选 target×horizon 在某些 keys不合格，只能按冻结的 common-key/zero-scale exclusion规则处理；不得只对难看的 arm、fold或key换 metric。若 P1/P2 证明 canonical MASE 在整个预注册 task grid 上机械不可定义，则在任何 P3、development API或P4/P5前：

- 触发 canonical `NO_CONFIRMATORY_POWER`；或
- 经新的明确人工批准与新 protocol hash，将**整个** primary metric统一切换为 canonical 允许的 outer-training-scale normalized macro-MAE fallback。

解封后禁止 metric fallback、epsilon移动或 denominator重算。

## 5. Operational measurements

唯一 primary proposal：

```text
ERROR_FREE_CLOSED_COMPLETION_BY_DEADLINE
= unit-macro fraction of planned origin bundles that,
   without retransmission, durably close by the frozen workflow deadline as
   ACTIVE or DELIBERATE_FALLBACK with a valid full-key schema.
ERROR_FALLBACK, FORMAL_INVALID, unclosed and late-only bundles count 0.
```

Plan A 基础档要求：绝对完成率 `≥q_min=0.95`，且存在 `C_k` 时 `ARCH1−C_k` 的 Bonferroni simultaneous one-sided component lower bound超过 P2 冻结的 operational margin。该 bound不是“Holm CI”；Holm只作用于七个 composite p-values。没有合格 `C_k` 时 primary operational claim为 NA，Plan A基础档不能靠设计属性代替它。

四项结果：

| Dimension | Numeric protocol | Claim role |
|---|---|---|
| 免人工模型选择 | 需要人工干预的 fold/origin数；机械选择完成率；selection manifest completeness | secondary；设计属性本身不能触发Plan A |
| 故障韧性 | no-retry crash closure recovery；ERROR_FALLBACK；late/ambiguous/unclosed；worker failure tolerance | reliability gate + secondary |
| 自审计证据链 | expected artifacts中 schema/hash/parent/request/attempt linkage全部通过的比例；orphan/duplicate数 | secondary；设计属性本身不能触发Plan A |
| 任务完成/有效覆盖 | primary endpoint；ACTIVE、DELIBERATE、ERROR分解；full planned-key coverage | unique primary operational endpoint |

`r_rec` 只来自一个在 P2 seal前单独冻结并 hash-pinned 的 `resilience_v1` fault manifest。其分母恰为 manifest 中预注册、实际触发并验证为 `STARTED` 后 crash/transport-close failure 的 fault slots；分子是在不重发该 slot的情况下，workflow形成可验证 active output或 exact common fallback closed state的 cases。fault case、fault class、cluster ID、injection point、expected closure、attempt-consumption语义、seed与实现 hash全部预冻结。

`accuracy_v1` formal run 中自然发生的 crash/transport failures必须另表报告，不能与 `resilience_v1` 注入 cases池化、补足分母或改变 `r_rec` Gate。若冻结 fault manifest没有合格暴露，`r_rec=NA_NO_FAILURE_EXPOSURE`，不得报告100%，且 Plan A base/aggressive tier不能把该 Gate视为PASS。

## 6. Harm gates

所有差值为 `ARCH1−comparator`：

- normalized WIS：Bonferroni simultaneous one-sided component upper bound低于 P2 冻结 harm margin；
- `ERROR_FALLBACK` fraction：Bonferroni simultaneous upper bound低于 P2 冻结 comparative harm margin，且 ARCH1绝对率不超过 P2 冻结 `r_max`；
- deadline completion：Bonferroni simultaneous lower bound高于 P2 冻结 comparative harm margin，且 ARCH1绝对率不低于 P2 冻结 `q_min`；
- no-retry recovery：只用 separate `resilience_v1` fault manifest，one-sided lower bound `≥r_rec`；自然 execution failures另报且不池化；无合格暴露时机械 NA而非PASS；
- coverage deviation作为 secondary harm：50/80/90每档 `abs(coverage−nominal)` 的 worsening不超过0.02。

WIS normalization由独立的 `P2_SLOT_WIS_NORMALIZATION_RULE`冻结；它不能覆盖、重定义或借用 primary MASE denominator。quantile crossing先由冻结 validator判 invalid并触发 exact common fallback，不能 post-hoc rearrange以改善 WIS。

## 7. Joint multiplicity

整体 FWER `α=0.05`。提议对七个 composite intersection-union hypotheses 的有效 p-values应用 Holm step-down；Plan A与Plan B不各自获得完整 alpha。七槽及其 component、margin slot、resampling、p-value和NA语义的机器可读定义见 `PLAN_A_HYPOTHESIS_REGISTRY.json`；该 registry当前为 `UNAPPROVED_P2_BLOCKED`，不能替代 P2人工冻结。

| ID | Composite alternative required for rejection |
|---|---|
| `A-SUP-N0` | `ARCH1−N0 < −δ_min` 且 WIS/failure/deadline harm gates通过 |
| `A-SUP-CK` | `ARCH1−C_k < −δ_min` 且同 harm gates通过 |
| `A-NI-N0` | `ARCH1−N0 < +δ_NI` 且同 harm/reliability绝对门通过 |
| `A-NI-CK` | `ARCH1−C_k < +δ_NI` 且同 harm/reliability绝对门通过 |
| `A-OP-CK` | primary operational improvement `>0` 且绝对 `q_min/r_max/r_rec` 门通过 |
| `B-D1-N0` | canonical `D1-RAW−N0 < −δ_min` 且其 WIS/failure harm gates通过 |
| `B-ACT-N0` | canonical `ACT1−N0 < −δ_min` 且其 WIS/failure harm gates通过 |

每个 composite p-value取其所有必要 component one-sided p-values的最大值；这是 conjunction claim 的有效 p-value。对7个 composite p-values执行 exact Holm：按 `(p_value,hypothesis_id)` 升序排序，rank `i` 依次比较 `α/(7−i+1)`，首个不拒绝处停止；Holm adjusted p-value按 `min(1,max_{j<=i}((7-j+1)p_(j)))` 计算并映射回固定 hypothesis ID。

Holm只调整七个 composite p-values。**不得**把 component effect bounds称为“Holm CI”或声称由 Holm threshold直接反演。为完整报告所有必要 component effect，使用 registry中固定 unique component family 的 Bonferroni simultaneous one-sided bounds；family size包含预注册 NA slots且不回收 alpha。每个 bound必须标为 `BONFERRONI_SIMULTANEOUS_COMPONENT_BOUND_NOT_HOLM_CI`。

若 `C_k=NA_NO_MATCH`，`A-SUP-CK/A-NI-CK/A-OP-CK` 在 seal 时固定 `p=1, status=NA`；不回收其位置或根据结果重新分配 alpha。Plan A aggressive tier需要前两个 superiority hypotheses都拒绝；base tier需要两个 NI hypotheses及 `A-OP-CK`拒绝。无 `C_k` 时这些固定槽不能拒绝，因此两个 Plan A tier均不能触发。

Plan B storyline状态机固定为：frozen statistics完成后先记 `PENDING_P6`；只有 P6 independent audit `PASS` 且 Plan A base仍未达标时，才转为 `PLAN_B_TRIGGERED_AFTER_P6_PASS`。P6为 `FAIL/BLOCKED` 时转为 `STOP_P6_AUDIT`，不得触发 Plan B性能叙事、不得新增检验或执行。

Secondary C2、IF representation、D4 roster、coverage levels与所有探索性 comparisons另用冻结 secondary Holm families并明确标注，不能升级为主 claim。

## 8. Unit-level inference and bootstrap

- independent sample：physical capacitor unit；origin/window/horizon/row/API replicate都不独立；
- unit内：common matured planned keys等权聚合；API replicates先按冻结规则聚合；
- cross-unit accuracy components：paired differences，batch/protocol strata内等概率 cluster resample physical units；
- `r_rec` component：只在 separate `resilience_v1` manifest内按冻结 `fault_cluster_id`、fault class分层cluster resample；不与physical-unit accuracy bootstrap或自然 failures池化；
- resamples：10,000；公开 root seed `69b4d58eb0c62268f69352faf6fe9c523dd8ba759fa1ca58b4c62fd31f1dd37a`；
- inference：component使用 registry冻结的 one-sided centered studentized bootstrap p-value；报告固定20个 unique primary components的 Bonferroni simultaneous one-sided bounds，不报告“Holm CI”；
- 小样本：若 eligible independent units或 strata支持不足以达到预注册 power，触发 `NO_CONFIRMATORY_POWER`，不把 origins当样本补足。

## 9. What remains blocked

以下必须等待经人工批准的新 Ren archive parser/tool plan及重跑 P1：

- exact physical unit registry、protocol/batch strata、target/unit/censor eligibility；
- exact long/medium/short horizon integers；
- `O_R`、outer/inner folds、planned/matured key counts；
- canonical visible-prefix one-step MASE的 `n_scale`、measurement-resolution epsilon、zero-scale exclusion、effect variance与power；
- `δ_NI` 工程 acceptance record；
- final P2 code hash与seal。

因此当前裁决是 `P2_NOT_FROZEN / BLOCKED_P1_REN`。任何 baseline fit、power score或API调用都必须继续停止。
