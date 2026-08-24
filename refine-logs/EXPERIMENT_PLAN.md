# CAP-ACT Claim-Driven Experiment Plan

**版本**：2026-08-24 15:19:15 +08:00  
**状态**：`MOCK_GO / SCIENCE_BLOCKED / PAPER_REVISE`  
**Problem Anchor source**：`RESEARCH_BRIEF.md`  
**Canonical method source**：`refine-logs/round-3-refinement.md`  
**AUTO_PROCEED**：`false`；所有下载、凭据、真实 API 与正式 release 均受人工 Gate 约束。

## 证据边界与规划前检

本计划只基于当前本地证据，不包含真实预测结果，也不把 mock tests 当科学证据。

| 本地证据 | SHA-256 | 当前含义 |
|---|---|---|
| `refine-logs/round-3-refinement.md` | `d4d40b0a7e3f5c9030bfe80e5ede3d059673c3b3c96122c9cf050097aa54f110` | CAP-ACT 19-action、common fallback、sealed outer-CV canonical proposal |
| `RESEARCH_BRIEF.md` | `609523fb547f0092c4461dda2c70e6bfdf9a36a1680b78ddce2cca9829825c6b` | immutable Problem Anchor、required arms、预算与因果约束 |
| `idea-stage/DATASET_EXPANSION.md` | `1435f6b12a6087d9194f978fc09fdfd3acf4ed40fd7cfa7ca852d7d1d1315156` | Ren/Patrizi 仅 acquisition-qualified；payload 尚未下载 |
| `refine-logs/ARK_AGENTPLAN_GATE1_PROTOCOL.md` | `7e2b32b812a872d11ad26785ff90b24a53a38ecf02346bb8e8361db3fa64abd6` | Ark `BLOCKED_PENDING_AUTHENTICATED_DISCOVERY_AND_CAPABILITY_PROBES` |
| `refine-logs/BENCHMARK_L_DATA_GATE_RESULT.md` | `081f30ec366c7e8298b915de5c5b4a68b85ae90ad11fb15567710b8cf06249e1` | Benchmark-L modeling/capacity/ESR/SOH/RUL 全部 blocked |

当前实现检验仅支持 harness readiness：

~~~text
PYTHONDONTWRITEBYTECODE=1 .venv-audit-cap/bin/python -m pytest -q \
  -p no:cacheprovider \
  tests/test_capact_actions_verifier.py \
  tests/test_capact_arms_search.py \
  tests/test_vfps_budget_ledger.py \
  tests/test_vfps_contracts.py \
  tests/test_vfps_no_network.py
~~~

本轮本地复核结果为 `40 passed`。它验证了 19/96 manifest 隔离、`b_star=FALLBACK=N0`、RC1=8、IF1=76,969/quotient-19、ENUM global backoff、arm permissions、ledger/crash/fallback 与 no-network 合同；尚未完成完整 reveal→durable commit→maturity→score 的端到端 M2 replay。

## Problem Anchor

> Can a maturity-aware agent graph whose typed proposals are tested by executable counterfactual replay improve strictly causal, held-out capacitor forecasts over both direct LLM agents and strong specialized numerical models under matched call, token, and latency budgets?

本计划采用 proposal 的诚实解释：`maturity-aware` 是 sealed policy 的 whole-unit mature qualification；`counterfactual` 仅指 deterministic metamorphic/perturbation testing，不指干预因果效应。

## 方法与规划 Gate

**Method thesis**：在 sealed whole-unit outer CV 中，用同一 common planned-key manifest、可审计 API envelope 与共同 numerical fallback，对 direct numeric LLM、同信息 direct LLM、受限 hybrid authority、19-action unified controller、deterministic action selector 和最小 homogeneous/heterogeneous four-call ensemble 做因子化比较，从而得到正、混合、空或负的可复现实证结论。

| Gate | 决定 |
|---|---|
| 贡献类型 | empirical Agent-architecture study；不是新的学习原理或 program-synthesis method |
| 主贡献 | direct/hybrid/numerical/multi-call 的严格因子化、matched-observable-budget whole-unit study |
| Supporting artifact | typed schemas、deterministic authority/fallback、durable replay、maturity ledger 与 fault qualification |
| 明确删除 | primary ACT-COMP96、IF-COMP96、ACT4、REFLECT4、hierarchy、debate、dynamic route、LLM judge/self-score |
| Frontier primitive | LLM 是 direct forecaster 或 bounded action controller；不再添加额外 frontier module |
| 当前放行 | M0/M1 complete-verified；M2 可继续；P1/P3 需要人工 Gate；P4/P5 禁止运行 |

## Claim Map（最多两个）

| Claim | Why It Matters | Minimum Convincing Evidence | Linked Blocks |
|---|---|---|---|
| **C1 — one-call Agent value**：在 Ren sealed outer whole-unit CV 的共同 matured keys 上，direct numeric LLM 与 19-action LLM+numerical controller 相对强 N0 的增益、空效应或伤害可被可靠估计。 | 直接回答“纯 LLM 是否有用”与“LLM+专用模型是否有用”，不预设正结果。 | `D1-RAW−N0` 与 `ACT1−N0` 两个预注册 paired-unit contrasts 全部运行；Holm-adjusted simultaneous inference；任何 positive claim 同时通过 point-loss minimum-effect 与 WIS/failure harm gates。 | B1, B2, B5 |
| **C2 — value-source factorization and scope**：任何观察到的 API value 可在声明上区分为 candidate-information、typed-authority package、LLM-versus-deterministic selection、permission-union、IF representation 或 four-model roster effect，并报告是否在 Patrizi 外域保持方向。 | 防止把更多信息、短输出、fallback、更多 calls 或强模型能力误写成“Agent graph novelty”。 | 全部预注册 one-call contrasts、D4-H/D4-X、worker-level constituent scores、planned/active/fallback states 和外域分表；只按结果矩阵给出局部 claim。 | B2, B3, B4, B5 |

### Anti-claims

- 不声称 action routing、fixed median ensemble、ordinary OOF 或 hash ledger 是新 ML 原理。
- 不把 D4-X 胜 D4-H 自动称为 diversity causality；未控制 constituent ability 时只称 sealed roster effect。
- 不用 Stress-2、mock、fault pass 或 Benchmark-L parser pass 支持预测精度。
- 不将 Patrizi 的一策略一设备结果解释为 protocol causal effect或 within-condition replication。
- endpoint 未通过 Gate 时，RUL/ESR 只能为 `NA`，不能通过更换阈值救活。

## Frozen Scientific Contract

### 1. 数据、target 与 split

- **Primary**：Ren SCs 113-unit EDLC，仅在 P1 row-level Gate 通过后进入。主 target 候选为 audited derived capacitance、capacity-SOH 与多步 trajectory；ESR 固定 `NA`；protocol EOL/RUL 需独立 Gate。
- **External stress**：Patrizi HSC 8-unit，仅在独立 P1 Gate 通过后进入。`Cap_ch/Cap_dis` 按 Ah/capacity-SOH 命名；IR 与 EIS-derived ESR 不混名；一策略一设备必须标为 confounded cross-strategy transfer。
- **Excluded from science**：Benchmark-L 当前 `FAIL/BLOCKED`；Stress-2 仅 M0/M2 sanity；Warwick 仅保留未来 energy-SOH auxiliary，不进入 core blocks。
- **Sealed outer CV**：每个 held-out physical unit 的全部 origins/windows 只在一个 outer fold；该 fold 的 model/scaler/calibration/fusion/`b_star`/ENUM table/feature bins 只来自 outer-training units，并在 outer-training 内做 nested whole-unit inner CV。
- 所有 outer folds 的 split、registry、prompt、model/version rule、commands 和 confirmatory contrasts 在打开任何 outer score 前一次 seal。查看结果后的任何改动是新 generation，旧 outer data 只能降级为 development。
- Patrizi 在 Ren architecture/prompt/claims seal 后独立运行；使用同一 architecture contract，但 numerical experts 可在 Patrizi outer-training units 内重新 fit。两域不池化。

### 2. Common planned keys 与 maturity

每个 fold/arm 在 replay 前共享逐字节相同的 `PLANNED` manifest：

`(unit_hash, origin, availability_cutoff, target, horizon, quantile_levels, unit, maturity_rule)`。

- origin 使用预冻结绝对 cycle/time schedule；不得用 final length、EOL fraction 或 suffix 决定。
- 每个 key 恰有一个 `execution_status ∈ {ACTIVE, DELIBERATE_FALLBACK, ERROR_FALLBACK}`。
- 流结束后恰有一个 `maturity_status ∈ {MATURED, NEVER_MATURED}`。
- 主准确率在所有 arms 共同 `MATURED` keys 上 intention-to-treat 比较，所有 fallback 保留。
- `NEVER_MATURED` 不能删除、补标签或按 arm 改 denominator；单独报告数量与比例。
- active-only loss 仅为 selection-biased diagnostic。
- 一个 API response 必须覆盖该 origin 的全部 planned target×horizon keys；缺一 key 则整个 origin bundle common fallback。

### 3. Frozen 19-action authority

每个 target×horizon：

~~~text
BaseAction = 6 EMIT + 5 FUSE + FALLBACK
ActionPrimary = BaseAction
              + 4 SHIFT(FALLBACK=b_star)
              + 3 INFLATE(FALLBACK=b_star)
~~~

- `b_star(target,h)` 严格等于该 outer fold 的 `FALLBACK=N0` champion bundle。
- 19 是 syntactic Action ID count；`FALLBACK` 与其所别名的 winning numerical action 可数值相同，不能声称 19 个独立 forecast functions。
- H1=6 model actions；RF1=5 fusion actions；RC1=`b_star` identity+7 transforms；三者集合并为 ACT1=19。
- `SHIFT` 对 point 与全部 quantiles 加 `s × scale_train(target,h)`；scale 必须 positive/finite/train-only；不 post-hoc clip。
- `INFLATE` 对每个 50/80/90 interval 围绕 point 外扩；point 必须位于 base interval 内，且扩展后保持 nested/monotone。
- invalid/nonfinite/unit/target/coverage violation 触发 whole-origin `ERROR_FALLBACK`。
- IF1 branch 只取 19 Actions；syntactic cardinality=76,969、realized-origin quotient=19；只支持 representation/metamorphic claim。
- ACT-COMP96、IF-COMP96、ENUM-COMP96 仅 appendix NICE-TO-HAVE，不能延迟 core。

### 4. Budget、attempt 与 failure

定义在 P3 synthetic capability probes 后、P4 前冻结：

- \(O_R\)：Ren 全部 sealed held-out origin packets；\(O_P\)：Patrizi 对应数量。
- \(R_{API}\)：正式 policy replicates，人工预算 Gate 在看任何 outer label 前固定为 1 或 3；replicates 永不计作独立 unit。
- \(B_1\)：可容纳完整 direct numeric bundle 的 common requested output-token ceiling。
- \(T_1\)：所有 one-call API arms 共同 workflow deadline。
- `accuracy_v1`：每 arm×origin×replicate 恰好一个 physical attempt、无 retry；timeout/late/unknown usage 仍占 slot并 fallback。
- P4 API attempts：7 个 one-call API arms（D1-RAW、D1-PACKET、H1、RF1、RC1、ACT1、IF1），上界公式为 \(7O_RR_{API}\)，外域另加 \(7O_PR_{API}\)。
- P5 API attempts：D4-H 与 D4-X 各四 workers，上界为 \(8O_RR_{API}\)；两臂同 total requested ceiling、worker count、aggregator 与 deadline。
- requested-token matching、actual-spend caliper、data-byte parity、full-request bytes、input/output/reasoning tokens、physical attempts、local CPU 与 end-to-end latency分开报告。
- usage 缺失的 attempt 保留预测/failure结果，但不能进入 matched-actual-token claim。
- D4 与 one-call 跨 envelope 只做 quality-cost Pareto，不称 matched-call effect。

### 5. Metrics 与统计冻结

**Primary point metric**：unit-macro MASE。

- 每个 eligible origin 的 scale 仅用该 origin 可见 prefix 的 one-step naïve absolute differences；`n_scale`、measurement-resolution `epsilon` 与 zero-scale exclusion rule 在 P2 依据 schema/measurement rule机械冻结，不看任何 API output。
- 先在 physical unit 内聚合 common matured keys，再跨 unit macro-average；rolling origins 和 API replicates不是独立样本。
- 若 P1 证明 MASE denominator 在预注册任务上机械不可定义，则在任何 API 调用前将 primary 切换为 outer-training-scale normalized macro-MAE，并生成新 protocol hash；不得看 P4 结果后切换。

**Secondary numeric metrics**：unit-macro MAE/RMSE、50/80/90 weighted interval score与coverage、worst batch/protocol fold、ERROR_FALLBACK、DELIBERATE_FALLBACK、active coverage、attempts、tokens、latency和 cost Pareto。

**Inference**：

- Primary family只有两个 one-sided paired-unit contrasts：D1-RAW−N0 与 ACT1−N0。
- 对 physical-unit paired differences 做 batch/protocol-stratified studentized cluster bootstrap（10,000 resamples，seed manifest冻结），并用 Holm 控制两项 familywise \(\alpha=0.05\)。
- P2 在不看 API 结果时冻结 practical margin \(\delta_{min}\) 及 WIS/failure harm margins；positive claim 要求 adjusted upper confidence bound \(<-\delta_{min}\)，且两个 harm gates 均通过。
- C2 contrasts 作为独立 secondary family：D1-PACKET−D1-RAW；ACT1−D1-PACKET；ACT1−ENUM-ACTION；ACT1 分别对 H1/RF1/RC1。使用 simultaneous/Holm-adjusted intervals。IF1−ACT1 与 D4-X−D4-H 单独标为 representation/roster families。
- 样本量/功效以独立 physical units 计算。若 P2 的预注册 power simulation 不足，输出 `NO_CONFIRMATORY_POWER`，仍可报告 descriptive estimates，但不启动扩大 claim。
- Patrizi 只有 8 units 时以 paired unit estimates/uncertainty 和方向性 external stress 为主，不冒充强 confirmatory replication。

## Paper Storyline

### Main paper must prove

1. 一个 eligible primary fleet 上强 numerical champion、direct LLM 与 LLM+numerical authority 的完整 one-call anchor table。
2. 同信息与权限分解能解释 positive/mixed/null/negative 结果，而不是靠 token、fallback 或遗漏 keys。
3. 最小 D4-H/D4-X 在同 four-call envelope 下给出 homogeneous repeat 与 heterogeneous roster 的结果。
4. Ren 结论在 Patrizi 上的适用边界，以及 final protocol 的 failure/coverage/cost。

### Appendix can support

- IF1 representation/metamorphic diagnostics。
- ACT/IF/ENUM-COMP96 成对 add-one，仅在 core 完整后。
- 逐 model worker scores、逐 horizon/action usage、fault matrix、ledger verification、provider capability matrix。
- resilience_v1 transport retry table，与 accuracy_v1 完全分表。

### Experiments intentionally cut

- ACT4-H/X、REFLECT4、hierarchy、debate、dynamic route。
- LLM judge、自评分、自由连续权重、accuracy retry、online outer-test policy update。
- GPR/TSFM/新 trainable component，除非 P2 显示六个 frozen experts 不足且另过人工 compute Gate。
- 未通过 endpoint Gate 的 exact RUL/ESR。
- 用 Benchmark-L 或 Stress-2 替代真实 eligible primary fleet。

## Core Experiment Blocks（恰好五个）

### B1 — Eligible data and strong numerical floor

- **Claim tested**：C1 的前置；排除弱 baseline、target误名与 split leakage。
- **Why**：没有可信 N0，就无法解释任何 Agent gain。
- **Dataset / split / task**：Ren sealed outer whole-unit CV；另做 batch/protocol holdout。Patrizi 仅在 B5。
- **Compared systems**：六个 frozen experts：last value、held-prefix drift、local linear、log-linear exponential、causal local-trend KF、ridge causal increment；五个 fold-local fusion algorithms：uniform、inverse-inner-risk、simplex point-loss stacking、simplex interval-score stacking、worst-unit/minimax simplex；nested inner rule选 `N0=b_star=FALLBACK`。
- **Metrics**：primary MASE、MAE/RMSE、WIS/coverage、per-unit/worst-fold loss、fit/forecast CPU与failure。
- **Setup**：所有 feature/scaler/calibration/fusion weight只用 outer-training；输出每 key point+50/80/90 intervals或 target-level NA。
- **Success criterion**：Data Gate、deterministic replay、nonzero/common metric denominators与预注册 unit-power Gate通过；不是要求某 numerical model“显著胜出”。
- **Failure interpretation**：target/identity/power失败则 formal Agent experiment `BLOCKED`；不得换 Benchmark-L/Stress-2。
- **Table / figure**：Table 1 data/estimand；Table 2 numerical floor。
- **Priority**：MUST-RUN。

### B2 — One-call direct versus hybrid anchor

- **Claim tested**：C1。
- **Why**：直接回答纯 LLM 与 LLM+专用模型是否有数值价值。
- **Dataset / split / task**：Ren 同一 sealed folds、planned keys、origins和maturity。
- **Compared systems**：N0、D1-RAW、D1-PACKET、H1、RF1、RC1、ACT1、ENUM-ACTION。
- **Metrics**：primary/secondary全部指标；planned/matured/active/deliberate/error fallback；requested/actual budgets。
- **Setup**：共同 anchor backbone；one physical attempt；hybrid data bytes相同；D1 direct 输出 compact fixed-order full numeric bundle；typed arms只能输出 allowlisted IDs。
- **Success criterion**：不预设 positive。D1-RAW或ACT1 positive 只在其 adjusted primary CI 与 harm gates通过时成立；否则记录 mixed/null/negative。
- **Failure interpretation**：direct差而ACT好支持 numerical authority package；全部不胜N0则支持严格负结果，仍进入最小B4。
- **Table / figure**：Main Table 3 one-call anchor；Figure 2 quality-cost-failure Pareto。
- **Priority**：MUST-RUN；D1-RAW、D1-PACKET 与至少一个 LLM+numerical arm绝不可删除，实际计划要求四个 hybrid子臂全部运行。

### B3 — Information, permission and representation isolation

- **Claim tested**：C2。
- **Why**：防止把信息、权限集合、短输出或IF语法混成一个“Agent effect”。
- **Dataset / split / task**：复用 B2 predictions，不额外挑选 origins。
- **Compared systems**：D1-RAW vs D1-PACKET；D1-PACKET vs ACT1；ACT1 vs H1/RF1/RC1/ENUM-ACTION；ACT1 vs IF1。
- **Metrics**：paired unit loss、WIS、schema/ERROR_FALLBACK、tokens、action distribution、deliberate fallback。
- **Setup**：IF1 strict matched at model/packet/decode/ceiling/deadline/fallback；IF perturbation只测试 fixed artifact contract。
- **Success criterion**：每个局部结果只支持 claim matrix中的对应来源；ACT1不胜子臂时删除 union-value claim；IF positive也只称 representation effect。
- **Failure interpretation**：factorization本身仍有价值；不得用其他对比补写机制。
- **Table / figure**：Main Table 4 contrast matrix；appendix action/fallback Sankey仅在确有可读价值时生成。
- **Priority**：MUST-RUN；COMP96为NICE-TO-HAVE。

### B4 — Minimal homogeneous and heterogeneous four-call controls

- **Claim tested**：C2 的 call/roster边界。
- **Why**：单 Agent负结果不能代表多调用 ensemble；同时避免 topology sprawl。
- **Dataset / split / task**：Ren 同一 keys/folds；只用 direct numeric outputs。
- **Compared systems**：D4-H（同一 anchor backbone四次独立 physical attempts）与 D4-X（四个 authenticated distinct backbones各一次）。
- **Metrics**：aggregate及每个worker的primary/secondary loss、invalid/fallback、total tokens、wall latency、deadline、cost。
- **Setup**：共同 componentwise median aggregator；每个 invalid worker先变成common fallback numeric bundle；aggregate后再做quantile/nesting验证。H/X同四workers、总requested ceiling、deadline和aggregation。无LLM synthesizer。
- **Success criterion**：D4-X−D4-H只支持 sealed roster effect；只有同时报告 constituent ability 后才讨论多样性迹象。
- **Failure interpretation**：两者不胜one-call/N0则停止全部多Agent扩展；仍报告required negative control。
- **Table / figure**：Main Table 5 four-call envelope；Figure 3 worker/aggregate paired effects。
- **Priority**：MUST-RUN if capability Gate admits four distinct models；D4-H至少需要一个可用model。若少于四个不同合格模型，D4-X机械 `BLOCKED_CAPABILITY`，不得用 provisional ID凑数。

### B5 — External-domain and operational boundary

- **Claim tested**：C1/C2 的scope与anti-claims。
- **Why**：单一Ren fleet不足以支持广泛PHM结论；fault pass必须与accuracy分开。
- **Dataset / split / task**：Patrizi separate-domain sealed whole-unit LOCO；capacity-SOH为优先兼容target；IR/EIS仅在其独立Gate通过。复跑final-hash fault fixtures。
- **Compared systems**：至少 N0、D1-RAW、D1-PACKET、ACT1、ENUM-ACTION；资源允许时同一完整B2表。D4仅在能力/预算预先批准时复制，不是外域最低门。
- **Metrics**：与Ren同构但不池化；逐unit paired estimates；strategy/device confounding标签；fault detection、ledger seal、secret canary、late/crash behavior。
- **Setup**：Ren后不改prompt/Action/claim；Patrizi numerical experts只在其outer-training units fit；final protocol hash fault suite全部通过。
- **Success criterion**：报告方向保持、反转或不可辨；只有兼容target与完整Gate才能称external stress。
- **Failure interpretation**：外域不稳定则把scope收窄到Ren；fault-only positive不能称accuracy gain。
- **Table / figure**：Main/Appendix Table 6 external boundary；Appendix fault qualification。
- **Priority**：MUST for journal-level scope；若Patrizi Data Gate失败则 `NA/BLOCKED`，不以Warwick或Stress-2替代。

## Run Order and Milestones

| Stage | Goal | Must-run work | Decision Gate | Current status | Cost envelope |
|---|---|---|---|---|---|
| **M0 — mock contracts** | schema/action/fault correctness | strict packets/arms、19/96隔离、SHIFT/INFLATE、fallback states、no-network/fault tests | 相关tests全部PASS且无secret/network side effect | `COMPLETE_VERIFIED`（纳入本轮40 tests） | CPU-only，0 API |
| **M1 — registry** | frozen numerical/action/ENUM registry | 6 models/5 templates/FALLBACK alias、19 Actions、RC1=8、IF1 count、ENUM global backoff | hashes/cardinality/permissions/toy argmin全部PASS | `COMPLETE_VERIFIED` | CPU-only，0 API |
| **M2 — blind replay** | reveal→commit→maturity闭环 | planned/maturity manifest、STARTED fsync、crash/late recovery、prediction-before-reveal、scorer seal | end-to-end hidden-suffix test与tamper test全部PASS | `PARTIAL_VERIFIED`；ledger tests有证据，E2E尚缺 | CPU-only，0 API |
| **P1 — new-data download/audit** | Ren/Patrizi row-level eligibility | 人工批准后按published bytes/digest下载；identity/schema/chronology/duplicate/target/censor/split audit | Ren primary target Gate PASS；Patrizi独立裁决 | `BLOCKED_HUMAN_GATE` | 约2.341 GB published payload bytes；不估解压量 |
| **P2 — numerical baselines** | strong N0与正式Eval冻结 | six experts、five fusions、nested CV、interval calibration、planned keys、power/margins | N0/replay/power/protocol seal PASS | `BLOCKED_P1` | CPU preferred；任何add-one GPU ≤2 h且另审批 |
| **P3 — authenticated Ark capability** | callable model与正式budget | 轮换credential、authenticated discovery、3–5 synthetic probes/model、capability matrix、第二人工release Gate | ≥1 anchor model通过；D4-X另需4 distinct models | `BLOCKED_HUMAN_AUTH` | discovery + 3–5 calls/candidate；不猜价格 |
| **P4 — one-call arms** | C1/C2 main result | B2+B3全臂、Ren；外域在主claim seal后 | complete common-key ledger；无adaptive reuse；统计Gate | `BLOCKED_P1_P2_P3` | \(7O_RR_{API}\)；外域另加 \(7O_PR_{API}\) |
| **P5 — minimal D4-H/D4-X** | required multi-call boundary | componentwise median、worker scores、same four-call envelope | capability/budget/seal PASS | `BLOCKED_P3_P4` | \(8O_RR_{API}\) |
| **P6 — audit/results-to-claim** | evidence→claim | independent ledger/code/result audit、statistics、claim matrix、artifact hashes | audit PASS才允许paper claim | `BLOCKED_RESULTS` | CPU-only；无LLM judge替代数值loss |

## P1 与 P3 人工 Gate

### P1 data acquisition Gate

未经新批准，不下载：

- Ren `raw.rar`：expected 2,114,703,017 bytes，published MD5 `26a7a663217c59377c83fb2a8274466b`。
- Patrizi `Dataset_HSC.mat`：225,986,697 bytes，MD5 `57e71c60cbae63142db44559edfa8ae0`；information PDF：397,625 bytes，MD5 `0189a89a72c73080cece2104ba834bce`。

下载后必须先 project SHA-256、ignored raw manifest、exact device identity、columns/units、chronology、duplicates、terminal records、target derivation、censor rules与outer split，再允许P2。任何paper/author-script与rows冲突都block，不做推断修复。

### P3 credential/API Gate

- 所有曾出现在聊天中的 key 一律视为不可用，必须轮换。
- credential仅由operator在运行环境外注入 secret environment；不得进入 prompt、shell command text、argv、repo、manifest、日志或paper。
- 先冻结 `arkcli` version/binary hash；取 `agent-plan model-list` 与实际 text resources 的 authenticated snapshots并取交集。
- 报告中的 `doubao-seed-2.0-mini`、`glm-5.3`、`deepseek-v4-flash`、`kimi-k3`、`kimi-k2.7-code`、`minimax-m3`、`deepseek-v4-pro` 均为 provisional；`glm-5.2` 不作为preferred dependency。只有requested/returned model与authenticated交集一致才可进入formal registry。
- 每个candidate先做3–5次strict-schema synthetic probes，验证model、usage、store/cache/tools、latency、deadline与failure。probe不能使用真实held-out labels。
- P3通过后，人工再批准 P4 formal envelope；能力probe PASS不代表模型有预测价值。

## Stop / Go Rules

| Trigger | Required action |
|---|---|
| M0/M1任何 deterministic contract fail | 停在本stage；不得用fallback掩盖test failure |
| M2 prediction可在durable commit前被reveal，或suffix/ID改变packet/prediction | `KILL_PROTOCOL`；禁止P1后续科学执行 |
| Ren P1 identity/target/split Gate失败 | formal paper `BLOCKED`；不得换Benchmark-L/Stress-2 |
| Patrizi P1失败 | external B5=`NA/BLOCKED`；Ren计划可独立继续，但venue scope降低 |
| P2 primary metric/power不可定义 | `NO_CONFIRMATORY_POWER`；禁止P3/P4 accuracy支出，除非新人工review重定义estimand |
| P3无合格model | `BLOCKED_API`；只保留artifact |
| P3少于4个distinct合格models | D4-X=`BLOCKED_CAPABILITY`；不得用未验证ID替代 |
| P4 direct/hybrid全部不胜N0 | 保留严格负结果；仍运行capability允许的minimum D4-H/D4-X；停止ACT4/debate等扩展 |
| ACT1不胜H1/RF1/RC1或ENUM | 删除union/controller superiority claim；不新增module救结果 |
| IF1胜ACT1 | 只允许representation effect；不得复活program-synthesis claim |
| actual token usage缺失 | 保留quality/failure；删除matched-actual-spend claim |
| 任一arm遗漏planned key或修改maturity denominator | formal run invalid；从未揭示labels的fresh generation重跑 |
| P6 independent audit fail | 不写paper performance claim；输出audit failure/blocked |

## Results-to-Claims Matrix

| Result pattern | Allowed claim | Claim ceiling |
|---|---|---|
| D1-RAW adjusted win over N0 | tested direct LLM在指定fleet/targets/budget有效 | 不推出hybrid或通用LLM优势 |
| ACT1 adjusted win overN0、D1-PACKET与ENUM，且harm gates通过 | tested typed-authority architecture package有增量 | 不声称纯authority causality或新学习原理 |
| D1-PACKET胜D1-RAW | numerical-candidate packet信息有帮助 | 不证明local executor必要 |
| ACT1不胜restricted arms | 统一19-action权限无必要性 | 保留简单子臂 |
| IF1胜ACT1 | explicit branch schema有representation effect | quotient仍为19；无expressivity claim |
| D4-H胜one-call | repeated sampling+median在额外四调用成本下有效 | 非matched-call one-call superiority |
| D4-X胜D4-H | sealed four-model roster有效 | 未控制ability时不称diversity causality |
| 所有API arms≤N0 | frozen条件下的robust negative（scope依赖外域/模型数） | 不写“LLM永远无用” |
| only failure/fallback改善 | operational reliability改善 | 无accuracy claim |
| Ren+Patrizi方向一致 | named-domain external robustness evidence | 不池化、不称跨chemistry universality |
| Gate blocked/mock-only | CAP-ACT artifact/harness | 无预测/venue claim |

## Compute, API and Human Budget

- **CPU**：M0–M2、P2 core numerical、P6；优先cached deterministic preprocessing。
- **GPU**：core默认不需要训练；任何GPR/TSFM/add-one需独立 sample/compute Gate，单architecture ≤2 GPU-hours，且不能替换已冻结core table。
- **Data**：P1 published payload total 2,341,087,339 bytes；实际存储/解压成本只能在manifest后报告。
- **API**：不猜价格；P3后以 \(O_R,O_P,R_{API},B_1,T_1\) 机械生成完整预算并由人工批准。所有 retries/continuations/worker calls均计physical attempts。
- **Human evaluation**：无主观打分；只需要 P1 download approval、P3 credential/capability approval、P4 formal-spend approval。
- **最大瓶颈**：独立物理unit/target资格，而不是GPU。

## Risks and Mitigations

- **Target derivation不可辩护**：P1 fail closed；绝不把Ah/energy/Re(Z)改名为F/ESR。
- **API model drift**：requested/returned model与capability snapshot不符即ERROR_FALLBACK或新generation。
- **Direct arm输出负担更高**：compact fixed-order numeric schema；同requested ceiling；实际tokens/Pareto分报。
- **Fallback掩盖Agent无效**：DELIBERATE/ERROR分离，planned-denominator为主，active-only只diagnostic。
- **Outer CV adaptive reuse**：single batch seal；先完成全部fold再开score；任何修改后旧outer降级development。
- **D4异构能力混杂**：逐worker score；claim限定roster effect。
- **外域低功效/混杂**：Patrizi不池化、不声称策略因果；失败则收窄scope。
- **Empirical novelty crowded**：独立literature review在paper claim前完成；不使用“first/novel”直到验证。

## Final Checklist

- [x] Claims ≤2
- [x] Core blocks =5
- [x] Direct LLM与LLM+numerical均为MUST-RUN
- [x] Frozen 19-action、common fallback与fallback状态分离
- [x] Common planned keys、sealed whole-unit outer CV、unit-level inference
- [x] Ren primary与Patrizi外域分表
- [x] Matched requested budget、physical attempts、retry/deadline/failure规则
- [x] M0/M1/M2与P1–P6顺序、人工Gate和stop rules
- [x] Numeric held-out loss是唯一accuracy裁决；无LLM judge
- [ ] M2 end-to-end blind replay PASS
- [ ] P1 human approval与raw Data Gates
- [ ] P2 N0/metric/power seal
- [ ] P3 rotated env credential、authenticated model/capability snapshots
- [ ] P4/P5 complete ledgers
- [ ] P6 independent audit与results-to-claim
