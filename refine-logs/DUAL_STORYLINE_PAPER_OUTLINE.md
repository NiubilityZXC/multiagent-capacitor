# Dual-Storyline Paper Outline and Unified Claim Ladder

**版本**：2026-08-28 00:30:00 +08:00  
**状态**：`PRE-RESULT OUTLINE / UNAPPROVED / NO PERFORMANCE CLAIMS`  
**共同实验**：Plan B canonical 11 arms `∪ {ARCH1}`，一套 sealed data/common keys/ledgers/statistics，一次 barrier与joint unseal

## 1. Working titles

Plan A（只有基础档及以上通过）：

> **Audit-Grade Agentic Forecasting under Whole-Device Causal Replay: A Matched Study of Direct, Hybrid, and Multi-Agent Capacitor Prognostics**

Plan B（Plan A基础档在完整审计后未通过）：

> **Do LLM Agents Improve Capacitor Degradation Forecasting? A Sealed Whole-Device Study with Numerical, Direct, Hybrid, and Multi-Call Controls**

两者都不能使用“first”“novel”“SOTA”“field-deployed”或“最强”，除非 P6最终检索与数值证据单独支持。2026-08-28 fresh novelty review评分仅 `5.0/10, PROCEED WITH CAUTION`，推荐把贡献定位为 evaluation contract和可证伪 empirical finding，而不是新 Agent topology。

## 2. Shared scientific spine

1. **Problem**：历史回放中常见 row/window leakage、事后挑任务、只计成功调用、不同信息/调用量与分阶段看结果，使 Agent增益不可归因。
2. **Evaluation contract**：whole-capacitor held-out units、past-only rolling replay、common planned/matured keys、physical no-retry、late non-overwrite、typed/hash artifacts、all-arm prediction-before-reveal、one joint unseal、unit-level inference。
3. **Compared policies**：preregistered fold-local numerical champion candidate `N0`（baseline adequacy pending）；direct LLM；same-information direct；restricted/unified hybrid actions；deterministic action selector；fixed homogeneous/heterogeneous four-call controls；fold-local selected `ARCH1`。
4. **Outcomes**：point error、WIS/coverage、fallback/valid coverage、deadline、no-retry recovery、audit linkage；tokens/attempts/latency仅作执行与matching事实。
5. **Falsifiability**：正、混合、空、负和机械 NA/BLOCKED均为预注册合法结果；Plan A结果不决定哪些 admitted arms运行。

## 3. Paper structure shared by both storylines

### 1. Introduction

- 电容器退化预测的物理单位、工况迁移和终局语义困难；
- LLM数值外推的负面证据与 Agent/hybrid路线的迅速拥挤；
- 论文问题不是“怎样让大模型看起来有效”，而是“在匹配、无泄漏、含失败分母的条件下是否仍有可测增量”；
- 贡献列表随 claim ladder机械生成。

### 2. Data, target semantics, and audit gates

- Ren与Patrizi来源、bytes/digests/license/provenance；
- physical identity、schema/unit、chronology、duplicate、censor、split audit；
- `C`、ESR、SOH、RUL定义和机械 NA；
- 当前事实：Ren archive-test blocked；Patrizi scientific eligibility blocked。未解除前本节只能写 data-audit paper state，不能写 forecast result。

### 3. Retrospective online replay

- observation prefix、rolling origin、multi-horizon target、maturity；
- common planned keys与fixed outcome-availability rule；
- unit-macro MASE/WIS；primary MASE对每个 origin只使用其 visible prefix 的 one-step naïve differences，并采用统一 zero-scale处理；
- sealed whole-unit outer CV、inner-only selection、cross-condition test。

### 4. Compared systems

- numerical baseline registry；modern adequacy additions只有在 `BASELINE_ADEQUACY_DECISION.json` 获明确人工批准并在结果前 hash-freeze 后才可进入 training-side pool；
- seven one-call policies、ENUM、D4-H/D4-X；
- `ARCH1`的3-candidate finite tournament；
- `C_{4,f}` matching与无匹配 claim ceiling；
- direct multi-Agent A02和 LLM+specialized-model A03均明确出现。

### 5. CAP-ACT audit harness

- typed packet/response/worker artifacts；
- attested transport与one-use credential lease；
- attempt/prediction/failure ledger；
- generation-wide barrier、master authorization与joint unseal；
- failure recovery、不重发、late response；
- reproducibility bundle。

### 6. Pre-registered statistical protocol

- physical unit独立性；
- seven-slot composite Holm family；
- `δ_min/δ_NI`、harm/reliability/operational gates；
- power/estimand selection；
- positive/null/negative mapping。

### 7. Results

结果解封后一次性填表，不移动顺序：

- Table 1：data/estimand/audit eligibility；
- Table 2：numerical floor（不改 canonical语义）；
- Table 3：one-call anchors；
- Table 4：canonical contrasts + 独立 Plan A panel；
- Table 5：D4-H/D4-X + ARCH1 aggregate/worker audit；
- Table 6：Patrizi external boundary，固定ARCH1 row及 NA/BLOCKED；
- Supplement：12-arm consolidated table、完整五因素contrast matrix、all failures、candidate/control matching ledger。

### 8. Error and failure analysis

- 按 unit/batch/protocol/horizon的 paired residual；
- ACTIVE/DELIBERATE/ERROR和deadline分解；
- selected candidate/roster频率；
- leakage/fault tests；
- 不用 LLM judge解释“质量”。

### 9. Discussion and limitations

- retrospective replay不是field deployment；
- fleet/condition/model/provider scope；
- public TSFM contamination不确定性；
- fold-selected ARCH1只识别selection-policy/package，非三个 topology各自 confirmatory effect；
- 无 matched control时的归因限制；
- blocked targets/domains和功效限制。

## 4. Plan A narrative branch

只有 P6 PASS 且 claim ladder达到对应档位才采用。

### Dominant message

在相同信息与预冻结执行包络下，tested fold-local Agent system package在 whole-device causal replay中相对 N0和严格 matched `C_{4,f}`达到预注册 superiority，或在准确率非劣的同时达到唯一 comparative operational improvement。

### Required Plan A evidence

- 每个 required fold都有 qualified ARCH candidate和 `C_{4,f}`；
- 7-slot Holm family完整；
- base prerequisites全部通过；aggressive在base之上通过两项 superiority；
- WIS/failure/deadline与absolute reliability门；
- worker artifacts与constituent abilities；
- P6 claim/code/citation audit。

### Plan A contributions allowed

1. audit-grade all-arm evaluation contract；
2. tested ARCH1 selection-policy/full-package result；
3. matched orchestration evidence（只有 `C_{4,f}`合法）；
4. reproducible CAP-ACT artifact。

不得把 A01/A02/A03 inner tournament称为三项 confirmatory topology comparison。

## 5. Plan B narrative branch

触发条件：全部 admitted arms完成、barrier PASS、joint unseal、frozen statistics与P6 PASS之后，Plan A base未达标。

### Dominant message

在严格whole-device、failure-inclusive评测中，直接LLM、typed hybrid、deterministic selector、fixed multi-call和fold-selected multi-Agent package究竟在哪里改善、持平或伤害 capacitor forecasting；负结果揭示更多calls、candidate information、fallback与roster能力的混杂。

### Plan B contributions allowed

1. complete preregistered positive/mixed/null/negative map；
2. direct LLM与LLM+specialized-model的清晰边界；
3. data/target audit和cross-condition limits；
4. CAP-ACT reproducibility artifact；
5. ARCH1 negative/mixed row完整保留。

Plan B不是第二次实验，也不能在触发后新增 arms或重跑。

## 6. Unified claim ladder

| Level | Mechanical evidence | Maximum wording |
|---|---|---|
| `L0-AUDIT` | P1/M3证据；无 eligible forecast run | “公开数据与执行栈的审计揭示这些可复现限制” |
| `L1-DESCRIPTIVE` | complete sealed results，P6 PASS；primary tests不拒绝 | “tested policies在该fleet/conditions下表现为mixed/null/negative” |
| `L2-LOCAL` | 某个预注册 Plan B contrast adjusted PASS | “tested direct/hybrid/roster component在指定contrast上改善” |
| `L3-PLAN-A-BASE` | base prerequisites、N0/C4 NI、operational superiority、reliability/harm全部PASS | “在`δ_NI`内非劣并取得预指定操作性收益” |
| `L4-PLAN-A-AGGRESSIVE` | L3 + ARCH1−N0和ARCH1−C4两项superiority PASS | “tested multi-Agent system package在冻结包络内改善预测” |
| `L5-GENERAL` | 多 fleet/新 generation、外域一致、P6查新 | 仍只作范围明确的跨域结论；不自动称SOTA/普遍优越 |

任何 `BLOCKED_P1`、`NO_CONFIRMATORY_POWER`、`BLOCKED_API`、formal invalid或P6 fail最多停在 L0，不得转为 Plan B性能论文。

## 7. Venue recommendations (conditional, not a submission claim)

### Plan A stretch targets

1. **NeurIPS Evaluations & Datasets Track**：2026起明确把 evaluation methodology本身作为科学对象；只有 CAP-ACT开放、跨多 dataset/asset、相对 PHMForge和 forecasting-agent benchmarks有清晰增量时才合理。当前单一blocked fleet远远不够。官方说明：[NeurIPS ED Track](https://blog.neurips.cc/2026/03/23/introducing-the-evaluations-datasets-track-at-neurips-2026/)。
2. **KDD Datasets & Benchmarks Track**：适合公开benchmark/tool与responsible data audit，但要求可访问、文档、影响与开放代码；同样需要解除数据 Gate并展示跨方法/跨域价值。官方 scope：[KDD D&B](https://kdd2026.kdd.org/datasets-and-benchmarks-track-call-for-papers/)。
3. **IEEE Transactions on Industrial Informatics**：若重点是工业 Agent orchestration、在线能力、可靠执行与多模型系统，而不只是单数据集预测。

### Plan A realistic archival target

- **IEEE Transactions on Instrumentation and Measurement (TIM)**：若核心是测量链、uncertainty、monitoring、audit trace和capacitor condition estimation；其官方scope明确覆盖测量方法、监测、信号处理与信息保存：[IEEE IMS/TIM](https://ieee-ims.org/publication/ieee-tim)。Patrizi原论文也在TIM，但需突出方法增量而非重复数据分析。

### Plan B targets

1. **IEEE Transactions on Reliability**：若 RUL/failure/censor与跨工况可靠性语义真正通过；否则不应以RUL为主。
2. **International Journal of Prognostics and Health Management / PHM Society Conference**：对严谨negative/mixed PHM结果、开放artifact、standards/metrics/verification高度契合。PHM 2026 CFP明确列出 agentic AI、foundation models、hybrid modeling与V&V：[PHM 2026 CFP](https://phm2026.phmsociety.org/north-america/call-for-papers/)。
3. **IEEE TIM**：若最终主要贡献仍是condition measurement/estimation与data audit而非Agent architecture。

不以 venue名气反推阈值或改storyline。投稿目标应在结果与P6审计后按 claim level机械选择。

## 8. Paper-generation gate

当前只能生成 protocol/methods与data-audit草稿。完整论文的 Results、Abstract数值、Conclusion性能结论和图表必须等待：Ren新 parser批准→P1 PASS→P2/P3/development/P4/P5分别批准→joint unseal→P6 audit。任何提前填入的数值均视为伪造。
