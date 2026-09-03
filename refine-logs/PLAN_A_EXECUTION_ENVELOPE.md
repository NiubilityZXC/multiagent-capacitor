# Plan A / Plan B Pre-Seal Execution Envelope

**版本**：2026-08-28 00:20:00 +08:00  
**状态**：`FORMULA_COMPLETE / COUNTS_UNRESOLVED / UNAPPROVED / NO_API`  
**原则**：只记录 physical attempts、requested/actual tokens、deadline、latency与执行闭合；不换算价格，不做 cost/Pareto，不以调用少作为论文价值。

## 1. Current hard stop

- Ren：payload bytes/MD5/SHA integrity PASS，但 RAR test 对233/233 members返回 unsupported method；没有 extraction、row identity、target、origin registry，故 `O_R=UNRESOLVED_BLOCKED_P1_REN`。
- Patrizi：payload integrity与受限静态解析完成，但 physical identity、schema/prose consistency、target与split eligibility不通过；`B5=NA/BLOCKED`，`O_P=NA_NOT_ADMITTED`。
- 当前不允许 P2 fitting/scoring、P3、development API、P4/P5或真实预测。

因此本文件不能诚实给出最终整数 attempts；任何声称当前已有可执行预算的文本均无效。

## 2. Lane separation

| Lane | Purpose | Attempt rule | Current status |
|---|---|---|---|
| `capability` | P3 authenticated identity/schema only | 最多5模型×恰3 synthetic probes=`≤15`；每 probe 96 output tokens | human-gated, prohibited |
| `development` | fold-local roster/candidate tournament与training-only dry run | `N_dev` hard manifest；每 slot no-retry | blocked P1 + human-gated |
| `confirmatory_ren` | 11 canonical arms + ARCH1 joint generation | full admitted Cartesian cells; one barrier/unseal | blocked P1/P2/P3/P4 |
| `external_patrizi` | separate-domain B5 | only if P1 PASS and joint seal | `NA/BLOCKED` |
| `fault_qualification` | synthetic failure injection | no real provider unless separately listed; never accuracy evidence | offline mock only |

Lane之间不能借用、重命名或用成功返回抵消 consumed attempts。P3不抵扣 `N_dev`。

## 3. Confirmatory arm slots per origin

| Arm group | Arms | Physical slots per origin/replicate |
|---|---|---:|
| deterministic | `N0`, `ENUM-ACTION` | 0 |
| one-call | `D1-RAW`, `D1-PACKET`, `H1`, `RF1`, `RC1`, `ACT1`, `IF1` | 7 |
| four-call controls | `D4-H`, `D4-X` | 8 |
| Plan A | `ARCH1` | 4 |
| total if all admitted | 12 arms | 19 |

Ren full-envelope upper bound：

```text
N_R_confirm = 19 × O_R × R_API
```

其中 `R_API∈{1,3}` 必须在任何 confirmatory result可见前固定；replicate先在unit内聚合，不增加样本量。资源若不能覆盖全部 MUST-RUN admitted cells，不得 seal。不能先跑 `R_API=1` 看结果再升级为3。

Patrizi若未来新 P1通过，domain admission必须在 joint seal冻结：

```text
B5_minimum canonical API = 3 × O_P × R_API
  # D1-RAW + D1-PACKET + ACT1; N0/ENUM have zero calls
B5_ARCH1               = 4 × O_P × R_API
B5_all_one_call        = 7 × O_P × R_API  (only if all seven admitted)
B5_D4                  = 8 × O_P × R_API  (only if pre-approved/admitted)
```

当前 `O_P=NA`，所以这些是未来公式，不是已授权 attempts。

## 4. Development API envelope

对3 candidates的全部有限完整 roster mappings、4 slots和training-only inner validation origins，令 `K[f,j,A01]=m[f,j]`，`K[f,j,A02]=K[f,j,A03]=P(m[f,j],4)`，其中 `m[f,j]` 是 capability-admitted model数：

```text
N_roster_tournament_slots
             = 4 × sum_f sum_j sum_c sum_{r=1}^{K[f,j,c]}
                   O_dev[f,j,c,r] × R_dev
N_prompt     = 0 for fixed PROMPT_V1
N_dryrun     = sum of pre-registered training-origin engineering slots
N_dev_slots  = N_roster_tournament_slots + N_dryrun
provider_send_attempts_dev <= N_dev_slots
```

- `O_dev[f,j,c,r]`、`K`和每个 ordered roster tuple必须由 P1/P2/P3 hash-pinned whole-unit split、capability roster与development-key manifest机械计算；
- `R_dev` 是固定整数，不能按返回质量追加；
- C4 control选择复用相同 policy-hash records；缺失补调必须预先列入 `N_dev`；
- 每个 `fold×inner-fold×candidate×roster mapping×role` 的整数 allocation、reserved slots与硬 stop counter在首次 development调用前出具；完整 roster records同时用于 roster和candidate tournament，不允许看部分结果后剪枝或补调；
- 若任一 required fold全部 candidates不合格，ARCH1全局 `BLOCKED_ARCH_DEV`，不能靠新增调用、第四候选或删 fold救活。

当前 `N_dev_slots=UNRESOLVED_BLOCKED_P1_REN`。未来完整整数 manifest必须单独交用户批准。

## 5. Token safety ceilings

变量定义：

- `B1`：能容纳一个 full direct numeric bundle 的 per-call requested output ceiling；
- `B_ROLE`：typed nonnumeric/limited-action role的 per-call ceiling；
- `B_ARCH=sum_{w=1}^4 B_w`：ARCH1总 requested ceiling；
- `B_D4`：matched D4 control总 requested ceiling。

匹配要求 `B_ARCH=B_D4` 且 per-slot ceiling multiset相同。最终整数只能在 P2 planned-key grid与 P3 schema probe确定 serialized lower bound后冻结：

```text
ceiling >= exact_min_schema_tokens + frozen_safety_headroom
ceiling <= provider/model authenticated maximum
```

不足以容纳 full-key schema的模型为 capability fail，不通过删 keys或缩 quantiles修复。requested ceiling、actual input/output/reasoning tokens分别记账；usage缺失不删除预测，但不进入 actual-token matched claim。当前所有 ceiling整数 `UNRESOLVED_NO_P2_P3`。

## 6. Deadline and no-retry

- 共同 ARCH/control workflow deadline使用 `T_ARCH≡T1`，按用户最新指令不另造 `T4`；
- 每 slot sub-deadline与最终 durable-write reserve在 seal前给出秒数；
- timeout、connection ambiguity、provider error、schema invalid与late response均消费相应 physical slot；禁止重发；
- late response不能覆盖已提交 fallback；
- reserved但因整体 deadline耗尽而未发送的 slot记录 `physical_attempts=0`、`NOT_STARTED_DEADLINE`与 closure，不得伪装为成功；
- actual latency只作执行事实，不能用更慢/更快触发论文价值结论。

`T1`秒数需 P3 capability latency（非预测loss）与明确工程上限共同确定，当前 `UNRESOLVED_NO_P3`。在用户批准整数前无真实调用。

## 7. Randomization and time-drift control

公开 root seed：

```text
ARM_ORDER_SEED_ROOT = ce975b7f5f55937163d04bed6bf4e8f7dc8cc429047e9db0eaa48db13d466507
```

1. scope/resource priority只在 seal前决定哪些可合法 admitted；不决定运行时“先跑 Plan A”。
2. seal后按 `unit×origin×replicate`形成 blocks，对12 arms用 seed派生的 balanced permutation/Latin rotation交错执行。
3. D4/ARCH workers在对应 arm turn内按其固定 DAG执行；独立 workers是否并发及全局 concurrency必须在 P3后、结果前冻结，并对 matched controls相同。
4. 记录 request start/end、provider returned model、rate-limit/outage、deadline与 time block；不因服务状态重试。
5. process/cache/store/session按 generation/fold/arm/unit/origin/replicate/role隔离。

## 8. Pre-seal machine-readable manifest requirements

未来 `EXECUTION_ENVELOPE.json` 至少包含：

- exact `O_R/O_P/O_dev`及来源 manifest hashes；
- `R_API/R_dev`、12-arm admission table、每 arm/worker slot counts；
- per-lane/per-fold/per-candidate/per-worker integer caps；
- per-role model rule、requested ceiling、deadline、decode、tool/cache/store；
- arm/block randomization seed与concurrency；
- no-retry/late/fallback policy hashes；
- hard-stop counters和超限行为；
- human approval artifact hash。

任一字段 unresolved 时为 `NOT_EXECUTABLE`。Manifest绝不包含 credential、raw response、hidden reasoning或价格。

## 9. Current verdict

`NOT_EXECUTABLE / BLOCKED_P1_REN / B5_NA / NO_API`。解除数据阻断所需的下一执行步骤只能是先提交新的 Ren archive tool/parser proposal并获得人工批准；在此之前仍可进行当前已授权的只读重验、文档/代码和 offline release review，但本 envelope不能替代任何批准。
