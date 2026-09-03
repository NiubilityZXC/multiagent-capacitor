# Plan A ARCH1 Architecture Candidates

**版本**：2026-09-03 17:33:17 +08:00  
**状态**：`PRESEAL_UNAPPROVED_NO_API / NO_MODEL_RESULTS`  
**候选数**：恰好 3；冻结后不得增加、拆分或替换  
**机器权威注册表**：`refine-logs/PLAN_A_ARCHITECTURE_REGISTRY.json`  
**共同调用包络**：每个 origin bundle 的 `planned_physical_slots=4`；每 slot 最多发送一次，因此实际 `provider_send_attempts∈[0,4]`

本文件是人类可读说明；闭合 JSON schemas、exact prompt bytes及其 SHA-256、A03 route/assignment registry、decision/aggregation/tie-break、slot failure transitions、parent/data-hash visibility 和候选字段均只以 `PLAN_A_ARCHITECTURE_REGISTRY.json` 为机器权威。它既不是模型结果，也不授权 P3、development API、P4/P5、模型训练、RUL scoring 或真实电容预测。实际 provider model ID 只能来自未来经人工批准的 P3 authenticated capability registry；下文的 `M_H`、`M_X1..M_X4` 是冻结的角色映射规则，不是对当前可用模型的猜测。

## 1. 共同资格合同

三个候选都必须满足：

1. 至少两个角色不同的 model workers；不能用四次同 prompt 的独立采样冒充多 Agent。
2. 每个角色只有 seal 中列明的输入、工具与输出 schema；无浏览器、代码执行、外部检索、label/loss/evaluator 或 provider memory 权限。
3. 角色间只传递 canonical JSON artifact 及其 SHA-256；不传隐藏 reasoning、自由文本 scratchpad 或未哈希上下文。
4. 工作流固定为 `planned_physical_slots=4`、有限 DAG、无循环、无 continuation、无 retry；每 slot 的 provider send 为0或1次，故 bundle级 `provider_send_attempts∈[0,4]`。超时、ambiguous consumption 与 schema failure 在已经 send 时消费该 slot。terminal closure 写入后收到的响应只追加正交 `LateResponseEvent.v1/LATE_RESPONSE_DISCARDED`，不能替换 closure、output hash 或 prediction，且不增加 send 计数。
5. 任一 worker 失败先落盘 `WorkerFailure.v1`，不得重发。w4 provider 只在 deadline 内形成 reference-only `FinalDecision.v1`；冻结的本地 executor 随后生成 `FinalOutput.v1`，其 `execution_status` 只能为 `ACTIVE`、`DELIBERATE_FALLBACK` 或 `ERROR_FALLBACK`。w4 失败或 decision 非法时本地提交 exact common `ERROR_FALLBACK`。
6. 每个 direct numeric output 必须覆盖整个 frozen origin bundle 的全部 planned target×horizon×quantile keys；禁止只保留成功 key。
7. ESR、SOH、RUL 或 anomaly endpoint 只有在 P1/P2 各自语义与数值 Gate 通过时出现；未通过的 key 不得由 Agent 推断补造。
8. prompt、packet、schema、model mapping、decode、requested ceiling、deadline、local executor、fallback 与聚合器全部进入 master seal。
9. 四个 planned slots 在每个 admitted origin都必须有 closure。上游 role失败后，只有在下游自己的 subdeadline 仍开启时，下游才以 typed failure/default artifact send一次；若其 subdeadline未开启，则不得 send，并以 `NOT_STARTED_DEADLINE`、`provider_send_attempts=0`闭合。不能通过“路由跳过”减少 `planned_physical_slots=4`，完整 bundle始终进入预注册 failure处理。
10. process/cache/store/session按 `generation×fold×arm×unit×origin×replicate×role`隔离；默认 store/cache/tools全部关闭。

## 2. 共同 typed artifact schemas

所有 schema 是一个 Draft 2020-12 resource（`$id=urn:plan-a:ArtifactSchemas.v1`，共享 `$defs`，无改变 scope 的嵌套 `$id`），其机器可执行闭合 JSON Schema、canonical serialization与 hash规则见唯一机器权威 `PLAN_A_ARCHITECTURE_REGISTRY.json`。当前 schema-resource canonical SHA-256 为 `a18a53a3a635d5cbc8a01b7dc3e2fbfb8a888a69e8bf126f27e614d54e3273aa`；离线 validator 为 `experiments/vfps_agent/architecture_registry.py`（SHA-256 `36e9f718f6a84bc8316e128969ae683334d2db9c439fc29e1836b4e2d17a6dd7`），对应测试为 `tests/test_vfps_architecture_registry.py`（SHA-256 `78e41ec3767d6126151421e4552d91829800d40cad9dd17e72ff4be22963568a`）。三者都须在 master seal 中 hash-pin；任何一项改变都需要重审。

| Schema | 必需内容 | 明确禁止 |
|---|---|---|
| `ForecastProposal.v1` | generation/fold/origin/request hashes；role；每 planned key 的 point 与冻结 quantiles；proposal confidence bin；status | prose forecast、缺 key、NaN/Inf、真实 suffix、self-score |
| `ActionProposal.v1` | 同一组 identity hashes；每 key 的 frozen action ID；所引用 numerical candidate hashes | 新 action、参数越界、直接执行工具 |
| `DiagnosticEvidence.v1` | past-only trend/curvature/noise/change flags；引用 packet field hashes；有限枚举值 | 未冻结特征、未来事实、自然语言论证 |
| `Critique.v1` | parent artifact hashes；逐 proposal 的 schema/physics/quantile-consistency flags；有限 reject codes；推荐 ID | 修改 parent、读取 label、自由打分 |
| `RoutePlan.v1` | frozen route ID；两个 exact specialist assignments；provider R01–R07 必须无 parent；本地 R00 必须以唯一 parent hash 绑定同一 cell 的 durable w1 `WorkerFailure.v1` | 生成新模型/特征、任意 assignment、provider 选择 R00、无 typed w1 failure 的 R00、运行未批准代码 |
| `A03SpecialistOutput.v1` | 一次 slot 唯一 envelope；一个 `DiagnosticEvidence.v1` child、一个 `ActionProposal.v1` child及两个 child hashes | 一个 slot 产生两个无共同 closure 的顶层 artifact、assigned view 外 action |
| `FinalDecision.v1` | 恰好三个 parent hashes；candidate/role/decision/aggregation/source_refs 的14个闭合映射之一；不含 payload | 任意数值 payload、closure status、新数值来源、隐藏 parent、LLM judge 分数 |
| `FinalOutput.v1` | 本地 executor hash、finalization trigger/hash、source hashes、planned-key manifest、三态 status 与 direct/fallback payload | provider 直接生成、status/trigger/payload 不一致、未注册聚合 |
| `WorkerFailure.v1` | slot、role、request hash、failure enum、deadline/attempt closure hash | raw response、凭据、reasoning |
| `SlotClosure.v1` | slot identity、0/1 send、不可变 terminal state、唯一 output schema/hash | late response 覆写 closure、同 slot 多个顶层输出 |
| `LateResponseEvent.v1` | 原 terminal closure hash、late response hash、严格单调观测时钟、三个无权限常量 | 0-send slot 的伪 late event、closure/prediction 覆写、send 增量、orphan/duplicate event |

Canonical serialization 使用项目合同 `CAP_CANONICAL_JSON_V1_SORTED_UTF8_NO_WHITESPACE`（UTF-8、sorted keys、无空白、拒绝 duplicate keys 与 non-finite numbers）。Artifact ID 为 `sha256(experiments.vfps_agent.canonical.canonical_bytes(value))`；下游同时校验 parent hash、request hash、fold/origin identity 与 schema hash。

执行时还必须提供一个 sealed `ArchitectureCellContext`：它逐字段绑定 generation/fold/origin/request/data/schema identity、candidate ID，以及包含 `key_id/target_id/unit/minimum/maximum` 的完整 `PlannedKeyManifest.v1`。公开 finalizer 只接受同一 cell 的四条 `(SlotClosure, durable output)` 记录，不接受 caller-supplied parent map；它从该 ledger 唯一派生 w1/w2/w3，且 w4 的三个 parent hashes 必须按 `[w1,w2,w3]` 等于这些派生 artifact。A03 仅在 durable w1 output 是冻结 failure state 的 `WorkerFailure.v1` 时派生 R00，R00 的唯一 parent hash 必须等于该 failure hash；provider route 与 R00 不得共存。每个 `FINISHED_VALID` direct proposal在 closure 前即按 manifest 原顺序验证全部且仅全部 key、finite、quantile nesting 与 target/unit 数值域。任何 registry/context/N0/closure-ledger 不一致使 formal run invalid；typed w4 failure或不可执行的已闭合选择只通过同一个本地 finalizer产生冻结的 common `ERROR_FALLBACK`。

## 3. 候选 A01 — `A01-HIER-VERIFY-4H`

### 3.1 目的与模型配置

这是同 backbone 的层级 evidence→proposal→critique→arbitration 架构，用来检验结构化角色分工是否优于 matched homogeneous four-call control，而不混入模型 roster 差异。

- 模型映射：四个 slot 均请求同一 fold-local `M_H`，returned model 必须匹配 seal 中的 model rule。
- 可见数据：与未来被判定为 matched 的 `D4-H` 完全相同的 raw causal packet bytes；若 hash 不同则该 fold 的 `C_k` 不可取 `D4-H`。
- 输出 authority：direct numeric bundle；本地只做 schema/target/quantile contract 验证，不做事后数值修正。

### 3.2 固定 DAG 与 slot

```text
raw packet ─┬─> w1 Trend Forecaster ─ ForecastProposal.v1 ─┐
            └─> w2 Robust/Risk Forecaster ─ ForecastProposal.v1 ─┤
packet + hash(w1,w2) ─> w3 Constraint Critic ─ Critique.v1 ──────┤
packet + hash(w1,w2,w3) ─> w4 Arbiter ─ FinalDecision.v1 ────────┘
```

| Slot | Role | 输入 | 输出 | Requested ceiling share |
|---|---|---|---|---|
| 1 | trend forecaster | raw packet | `ForecastProposal.v1` | `B_ARCH/4` |
| 2 | robust/risk forecaster | raw packet | `ForecastProposal.v1` | `B_ARCH/4` |
| 3 | constraint critic | raw packet + hashes/canonical artifacts 1–2 | `Critique.v1` | `B_ARCH/4` |
| 4 | arbiter | raw packet + artifacts 1–3 | `FinalDecision.v1` | `B_ARCH/4` |

Arbiter 只能：(a) 选择 w1；(b) 选择 w2；(c) 使用预冻结 componentwise median of w1/w2/N0；(d) deliberate common fallback。它不能创造第三个自由数值预测。w3 只给有限 reject codes；不输出 numerical loss 或主观质量分数。

### 3.3 终止与 fallback

固定深度 3、无反思回路。w1/w2任一失败时，其位置替换为 typed failure；w3仍使用两个 closure artifacts被调用，w4也必须被调用并可使用剩余合法 proposal与N0。w4失败、两 proposal均非法或最终 bundle非法时提交 exact common `ERROR_FALLBACK`。

## 4. 候选 A02 — `A02-PAR-DEBATE-4X`

### 4.1 目的与模型配置

这是异构 direct-LLM 并行提案加 bounded adversarial adjudication 架构，直接回答“多个大模型 Agent 能否直接预测”而不依赖专用数值候选。

- 模型映射：`M_X1`、`M_X2`、`M_X3` 为三个不同的 direct forecasters，`M_X4` 为 adjudicator；四个 returned model ID 必须互异。
- 可见数据：与 matched `D4-X` 完全相同的 raw causal packet bytes。
- 输出 authority：w1–w3 direct numeric；w4 只能在 proposal 与固定本地聚合模板中选择。

### 4.2 固定 DAG 与 slot

```text
                         ┌─> w1 extrapolation view ─┐
raw causal packet ───────┼─> w2 robust-change view ─┼─> w4 bounded adjudicator
                         └─> w3 uncertainty view ───┘       │
                                                           └─> FinalDecision.v1
```

| Slot | Role | 输入 | 输出 | Requested ceiling share |
|---|---|---|---|---|
| 1 | extrapolation forecaster | raw packet | `ForecastProposal.v1` | `B_ARCH/4` |
| 2 | robust-change forecaster | raw packet | `ForecastProposal.v1` | `B_ARCH/4` |
| 3 | uncertainty forecaster | raw packet | `ForecastProposal.v1` | `B_ARCH/4` |
| 4 | bounded adjudicator | packet + canonical proposals/failures 1–3 | `FinalDecision.v1` | `B_ARCH/4` |

w4 的有限选择集合恰为：任一合法 worker bundle、合法 workers 的 componentwise median、合法 workers 与 N0 的 componentwise median、deliberate fallback。没有多轮辩论；前三个 worker 不接收彼此输出。任何“debate gain”只能理解为该完整 bounded package 相对严格 matched control 的效果。

### 4.3 终止与 fallback

前三个 slot可并行；slot 4仅在三者均 durable close或其子 deadline到达后启动，即使三者全失败也使用 typed failures调用。存在至少一个合法 proposal时，w4可闭合 active output；否则 common `ERROR_FALLBACK`。无 worker重发。

## 5. 候选 A03 — `A03-TYPED-ROUTE-4X`

### 5.1 目的与模型配置

这是 LLM Agent 与专用数值模型直接组合的 typed dynamic-routing 架构。它测试的不是“LLM 自己更会外推”，而是训练侧冻结的专家库、路由证据和多角色验证能否形成更好的完整 system package。

- 模型映射：四个不同 returned model ID：`M_X1` router、`M_X2` trend specialist、`M_X3` uncertainty specialist、`M_X4` arbiter。
- 可见数据：frozen hybrid packet，包含与 canonical one-call hybrid arms 相同的 past-only features、N0、六个 numerical experts、五个 fusion candidates、calibrated intervals及各自 hashes。
- authority：router 从 seal 中的有限 route registry 选两条路径；specialists只能输出 primary 19-action proposal及 finite diagnostics；w4 从这些 actions/固定 fusion 中选择，随后本地 deterministic executor 生成完整预测。

### 5.2 固定 DAG 与 slot

```text
hybrid packet + expert hashes ─> w1 typed router ─ RoutePlan.v1
                                      ├─> w2 trend specialist ─ A03SpecialistOutput.v1
                                      └─> w3 uncertainty specialist ─ A03SpecialistOutput.v1
packet + exact envelope hashes 1–3 ───────> w4 arbiter ─ FinalDecision.v1
                                                        │
                                                        └─> local frozen executor ─ FinalOutput.v1
```

| Slot | Role | 输入 | 输出 | Requested ceiling share |
|---|---|---|---|---|
| 1 | typed router | hybrid packet + candidate hashes | `RoutePlan.v1` | `B_ARCH/4` |
| 2 | trend specialist | route + assigned past-only candidate views | one `A03SpecialistOutput.v1` envelope containing `DiagnosticEvidence.v1` + `ActionProposal.v1` and both child hashes | `B_ARCH/4` |
| 3 | uncertainty specialist | route + assigned intervals/residual views | one `A03SpecialistOutput.v1` envelope containing `DiagnosticEvidence.v1` + `ActionProposal.v1` and both child hashes | `B_ARCH/4` |
| 4 | typed arbiter | packet + artifacts/failures 1–3 | `FinalDecision.v1` | `B_ARCH/4` |

Route registry 只能由已冻结的 numerical expert/action IDs 的有限组合构成；不得在运行时生成代码、训练新模型或发明特征。w4 选择集合为 w2/w3 action、两者 frozen tie-break fusion、`b_star=FALLBACK`。所有数值由本地 executor 确定，Agent 没有写任意浮点轨迹的权限。

w1无效时，本地生成唯一 `ROUTE_DEFAULT_V1`（两个 specialists都接收 seal中固定的 N0+global-best-numerical views）；slots 2与3只在各自 subdeadline开启时发送，否则以 `NOT_STARTED_DEADLINE`闭合。任一 specialist失败时，w4接收对应 `WorkerFailure.v1`，也只在自身 subdeadline开启时发送；否则同样闭合但不发送。因此 dynamic route不会减少 planned四槽包络，但 realized provider sends可以小于4。

### 5.3 匹配限制

若 canonical 11 arms 中没有一个同时具有相同 hybrid packet、四次调用、同 roster、同工具与同总 ceiling，则本候选在该 fold 的 `C_k=NA_NO_MATCH`。即使它胜 N0，也只能支持 tested hybrid system-package effect，不能支持 routing/edges 的独立因果增益。

## 6. Fold-local model/roster mapping

P3 synthetic probes只决定模型是否满足 authenticated identity、schema、usage、deadline与工具关闭能力，绝不按预测表现排序。预测能力选择不定义不可观测的“role loss”，而是在 outer-fold 内对有限完整 roster配置做二级 whole-unit nesting：

1. 对 outer fold `f`，只取 `T_f=outer-training units`。
2. 在任何 development result可见前，对每个 inner split `j` 发布完整 roster manifest：A01枚举每个 capability-admitted model作为 homogeneous四槽 mapping `(m,m,m,m)`；A02/A03枚举 admitted model IDs 的全部 ordered injective 4-tuples。最多5个模型时，每个 heterogeneous candidate最多 `P(5,4)=120` 个 mappings；不按 role、prompt或单次返回表现剪枝。
3. 每个 `candidate × roster mapping` 都在 `T_{f,j}` 的 inner-training信息上形成其 numerical/calibration对象，并在 inner-held-out physical units上执行**完整四槽 workflow**。schema、deadline、WIS、failure与reliability gates以及 common-key unit-macro MASE均针对完整 candidate输出计算；router、critic、specialist或arbiter没有单独的伪“role loss”。
4. 对每个 candidate，先排除任一资格门失败的 roster mapping，再取跨 inner-held-out physical units平均 MASE最小者；`abs(diff)<1e-12` 时按完整 ordered model-registry-ID tuple词典序取小。若无合格 mapping，该 candidate在该 outer fold不合格。
5. 三个 candidate各自锁定 roster后，再按§7的完整 candidate规则选择 `ARCH1[f]`。选中 candidate/roster后，只用全部 `T_f` 按同一预冻结 numerical/calibration算法形成 outer-held-out执行对象；prompt bytes保持固定，不能重新选择。
6. 上述所有 `fold × inner split × candidate × roster mapping × unit/origin × planned worker slot` 的 evaluation sends必须在首次 development调用前逐项进入 `N_dev` hard manifest；资源不能覆盖全枚举时该配置不得开始，也不能看部分结果后剪枝或补调。

不得用所有 outer OOF 结果选一个全局 model、roster、prompt或 candidate。每 fold 的映射、被拒模型、选择频率与训练侧分数都进入审计表。

Generation 1每个 role的唯一 exact prompt bytes及其 SHA-256见 `PLAN_A_ARCHITECTURE_REGISTRY.json`；这些 bytes与 schema slot落入 master hash seal前不得真实调用。若未来允许 fold-local prompt选择，必须新建 generation并先提交每 role有限 prompt registry及配置数；不能在看到 inner结果后手工改字，也不能把新增 prompt伪装成同一候选。

## 7. Mechanical candidate selection

逐 outer fold：

1. 按 schema → attempt closure → common-key coverage → deadline → WIS harm → failure/recovery gate 排除不合格候选；
2. 对合格候选计算 inner-held-out physical-unit macro MASE；
3. 取均值最小者；差值小于 `1e-12` 视为 machine tie；
4. tie 依 `[action_space_cardinality, agent_count, edge_count, candidate_id]` 词典序取小；
5. 任一 required outer fold全部不合格，则整个 Generation 1 的 `ARCH1=BLOCKED_ARCH_DEV`，全部 ARCH1 primary hypotheses固定 `status=NA_BLOCKED_ARCH_DEV,p=1`；不得删除失败 fold后做 subset confirmatory inference，也不得加入第四候选。

候选静态复杂度用于 tie 的值：

| Candidate | Action-space cardinality | Agent count | Directed artifact edges |
|---|---:|---:|---:|
| A01 | 4 | 4 | 5 |
| A02 | 6 | 4 | 3 |
| A03 | 19 | 4 | 5 |

这里的 cardinality 是最终 arbiter 的冻结选择数上界，不是 prompt token 数，也不是论文价值指标。

## 8. Seeds and deterministic scheduling

公开 root seed：

```text
ARCH1_SEED_ROOT = 9baeadb1cfac91d59867dd7e772412d36d95419f0af40b0cef17a232a8b74e3b
```

每个用途的 seed 为 `SHA256(root || generation || domain || outer_fold || inner_fold || candidate_id || role_id || unit_id_hash || origin_id || replicate || purpose)`。作用包括 inner fold、roster tie、arm/block order与任何允许的 sampling；不得依赖 wall-clock。API decode 若 provider 支持 seed，也记录 requested 与 returned 支持状态；不声称 provider 完全确定。

## 9. Development-call allocation formula

每个完整 `candidate × roster mapping`、每 inner validation origin、每 replicate均计划4 slots；实际 provider send由逐 slot subdeadline决定，为0到4次。令 `m[f,j]` 为该 inner split中 capability-admitted model数，`K[f,j,A01]=m[f,j]`，`K[f,j,A02]=K[f,j,A03]=P(m[f,j],4)`（`m<4` 时后二者机械不合格）：

```text
N_roster_tournament_slots
             = 4 × sum_f sum_j sum_c sum_{r=1}^{K[f,j,c]}
                   O_dev[f,j,c,r] × R_dev
N_dryrun      = sum of pre-registered engineering-only mock/training-origin slots
N_dev_slots   = N_roster_tournament_slots + N_dryrun
provider_send_attempts_dev <= N_dev_slots
```

`O_dev[f,j,c,r]`、`K`与 ordered roster tuples必须来自 P1/P2/P3 后 hash-pinned 的 training-only development manifest，`R_dev` 必须在调用前取固定整数。完整 roster records同时用于 roster与candidate tournament，不另建可结果驱动补调的 `N_roster`。因为 Ren archive test当前 `BLOCKED`，这些数量目前不可从 row-level identity/origin registry计算，故 `N_dev_slots=UNRESOLVED_BLOCKED_P1_REN`。在具体整数、逐 fold/inner-fold/candidate/roster/worker分配、`B_ARCH`与deadline扩展成完整 manifest并获人工批准前，development API保持禁止。

P3 capability lane（最多5模型×每模型恰3 synthetic probes=15 attempts，每次96 output tokens）与 `N_dev` 分账，不得互相挪用。

## 10. Candidate claims and falsifiers

| Candidate | 可证伪假设 | 直接反证 |
|---|---|---|
| A01 | 同模型、同 raw 信息、同四调用下，角色化 verifier/arbitration package优于或不劣于 D4-H | 不胜 matched D4-H/N0，或 harm/reliability gate失败 |
| A02 | 异构 direct Agent 的 bounded adjudication优于或不劣于同 roster固定聚合 D4-X | 不胜 D4-X/N0，或 adjudicator增加 failure/deadline harm |
| A03 | typed routing+numerical authority package优于 N0/one-call hybrid，并保持可靠闭合 | 不胜 N0/ACT1/ENUM，或无 matched control而声称 routing causality |

三个候选的负结果均合法。任何候选获胜都不自动证明“多 Agent 普遍优越”，更不证明语言模型具有固有数值外推能力。

## 11. 当前 Gate

`BLOCKED_P1_REN / UNAPPROVED_CANDIDATES / NO_API`。本文件等待协议审查与人工批准；不得据此调用用户提供的 Ark credential。
