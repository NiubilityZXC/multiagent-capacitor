# Plan A Protocol Addendum

**版本**：2026-08-27 15:28:47 +08:00  
**状态**：`PRESEAL_PROPOSAL / UNAPPROVED / EXECUTION_BLOCKED`  
**依赖**：`PLAN_A_PROBLEM_ANCHOR_ADDENDUM.md`、`MASTER_JOINT_SEAL_PROTOCOL.md`

## 1. 协议边界

本 addendum 只增加 `ARCH1` 及其预注册比较。Plan B 的 11 个 arm、Data Gate、common planned keys、whole-unit split、maturity、共同 fallback、accuracy no-retry、Stop/Go 和原局部 contrasts 保持不变；联合 multiplicity 和表格位置的有限调整以 `CANONICAL_SUPERSESSION_LEDGER.md` 为唯一解释表。

当前没有已冻结 ARCH1、没有开发 API 结果、没有 outer score，也没有真实 LLM 电容预测。任何标为“提议”的值在人工批准与 hash seal 前都不具执行效力。

## 2. ARCH1 的程序化定义

`ARCH1` 是一个 fold-local selection policy，而不是固定的事后 winner：

```text
for outer_fold f in frozen_fold_order:
    training_units = all_confirmatory_units - held_out_units[f]
    candidate_records = inner_whole_unit_CV(training_units, CANDIDATES)
    qualified = apply_frozen_schema_deadline_WIS_failure_reliability_gates(candidate_records)
    if qualified is empty:
        ARCH1[f] = BLOCKED_ARCH_DEV
    else:
        ARCH1[f] = argmin(
            inner_unit_macro_MASE_on_common_keys,
            tie=(action_space_cardinality, agent_count, edge_count, candidate_id)
        )
```

- 候选集合恰为 `A01-HIER-VERIFY-4H`、`A02-PAR-DEBATE-4X`、`A03-TYPED-ROUTE-4X`；人类可读说明见 `PLAN_A_ARCHITECTURE_CANDIDATES.md`，闭合 schema、exact prompt bytes/hashes、route/assignment、aggregation与failure transition以 `PLAN_A_ARCHITECTURE_REGISTRY.json` 为机器权威。
- 三个候选均为 `k=4`；这是允许集合 `{2,3,4}` 的预先选择，并优先保证可与 Plan B 的 D4 controls 做匹配。冻结后不能新增 `k=2/3` 候选。
- 每个候选至少有两个角色不同的 model workers；角色输入、权限、输出 schema、边、聚合、仲裁、终止和 fallback 都是可执行的。
- role 间只交换 typed、canonical-serialized、hash-addressed artifacts；不交换未冻结自由文本，也不保存或评价隐藏 reasoning。
- 每个 outer fold 的 candidate、backbone/roster、prompt、router、threshold、calibration 只可使用该 fold 的 outer-training units；held-out label、suffix、terminal metadata 和 loss 全部不可见。
- 每个 fold 必须报告选中 candidate ID、合格/不合格原因、inner-CV score 和选择频率；outer 结果不得参与选择。
- 只要任一 required outer fold 为 `BLOCKED_ARCH_DEV`，`ARCH1` 在整个 Generation 1 全局 blocked；不得删除该 fold 后在剩余 folds做 confirmatory inference。全部 ARCH1 primary slots固定 `status=NA_BLOCKED_ARCH_DEV, p=1`。
- 每个 fold、process和provider session都用 seal 中不同 namespace；cache/store/session默认关闭，禁止跨 fold、跨 origin或跨 arm共享隐状态。

## 3. Candidate tournament

### 3.1 一次冻结的输入

在任何正式 inner-CV result 可见前，一次 hash-freeze：candidate registry、role prompts、packet/schema、API slot assignment rule、candidate/worker/fold 配额、seed root、common development keys、qualification gates、MASE/WIS 实现、tie rule、failure semantics 和 `N_dev`。

### 3.2 资格门顺序

按以下固定顺序逐候选逐 fold 执行，任何一步失败均不能靠后续 loss 排名救活：

1. schema completeness 与 unit/target/quantile contract；
2. accuracy no-retry、exact physical-attempt closure 与无 late overwrite；
3. common development planned-key coverage；
4. deadline qualification；
5. WIS harm gate；
6. `ERROR_FALLBACK` 与无重发恢复资格门；
7. inner whole-unit CV unit-macro MASE 排名。

全部候选失败时记录 `BLOCKED_ARCH_DEV`。该状态不阻止 master seal 机械保留 ARCH1 的 `NA_BLOCKED_ARCH_DEV` slots；在尚未查看 outer performance 的条件下 Plan B 可依 Stop/Go 继续执行已 admitted cells，但禁止临时加入第四候选。Plan B 叙事仍只能在全 generation 的 frozen statistics 完成且 P6 PASS 后触发；P6 failure 是 `STOP`。

### 3.3 Fold aggregation 与 tie

- inner fold 顺序：按冻结 `inner_fold_id` 升序；unit 内先聚合 common matured keys，再跨 unit 等权宏平均。
- candidate 汇总：对 inner held-out unit loss 先逐 unit 计算，再按 unit 等权均值；不能按 row/origin 数加权。
- exact tie 或数值差小于冻结的 machine-tolerance 时，依次取更小的 `[action_space_cardinality, agent_count, edge_count, candidate_id]`。
- physical calls 或 tokens 更少不能作为价值判据，也不进入 tie rule。

## 4. Confirmatory execution

- Arm set 是 Plan B 11 臂加 `ARCH1`；每个 admitted `outer_fold × arm × origin × R_API` cell 都必须在任何 outer performance、arm summary 或 comparison 可见前闭合。
- `ARCH1` 每个 origin/replicate 预留恰好四个 planned physical slots；每个 slot 的 `send_attempt_count∈{0,1}`。已发送后的失败/超时/late/ambiguous consumption 记录一次 actual send attempt 且禁止重发；因 workflow deadline 到期而根本未发送的预留 slot 以 typed `NOT_STARTED_DEADLINE` 闭合，actual send attempts 为 0。
- 四 worker 中任一无效先形成该 role 的 typed failure artifact；最终聚合器必须机械生成 valid active output 或 exact common fallback closed state。
- `ERROR_FALLBACK` 永远保留在 ITT denominator；active-only 仅诊断。
- `ARCH1` 的 Ren `4 O_R R_API` 与 Patrizi（若 Gate 通过）`4 O_P R_API` 只是最大 planned/reserved send opportunities，不是保证发生的 physical attempts。实际 send attempts 必须由 attempt ledger 计数且不得超过对应上界；这些数值不换算价格。
- `R_API ∈ {1,3}` 仅是固定重复次数，replicate 不增加独立样本量。

## 5. C_k 与比较

时序必须分开：P2 只冻结 `PLAN_A_CK_MATCHING_PROTOCOL.md` 中的 `C_k` calipers、eligibility algorithm、tie rule 与 `NA_NO_MATCH` 语义，不冻结或预判任何 actual `C_{4,f}`。P3/candidate tournament 完成后且 master seal 之前，才使用该已冻结算法和仅 outer-training/inner-CV records 从 canonical 11 臂中机械确定每 fold 唯一 `C_{4,f}`（叙事中的 `C_k` 在本研究因 `k=4` 即指这个 fold-specific control）：

- caliper 要求 physical calls、外生可见数据、backbone/roster capability、工具权限、requested token ceiling、deadline、retry、decode/provider policy 和 fallback 匹配；
- 多个 eligible controls 时，只用 outer-training/inner-CV unit-macro MASE 机械选择，平局按 arm ID；
- 任一 required fold 无合格 control 时记 `C_{4,f}=NA_NO_MATCH`，仍报告 ARCH1 package，但两个 Plan A tier均不能触发，也不作协作结构/节点/边的增益主张；
- `ARCH0-SHAM` 只作为待人工批准的可选设计，不自动加入 arm set。

必须报告的 confirmatory comparisons：

1. `ARCH1−N0`；
2. `ARCH1−C_k`（无匹配时机械 NA）；
3. `ARCH1−D1-RAW`；
4. 唯一 primary operational endpoint 的 `ARCH1−C_k`；
5. Plan B canonical primary contrasts `D1-RAW−N0` 与 `ACT1−N0`。

WIS、failure、deadline、四项操作性测量以及所有 Plan B canonical secondary contrasts仍完整报告。没有严格 matched orchestration ablation 时，ARCH1 只能支持 full-system/package effect。

## 6. Joint inference

- Joint primary family恰为七个 fixed slots：`H-A-N0-SUP`、`H-A-C4-SUP`、`H-A-N0-NI`、`H-A-C4-NI`、`H-A-OP-C4`、`H-B-D1RAW-N0`、`H-B-ACT1-N0`。`ARCH1−D1-RAW` 必须报告但属于预冻结 secondary family。
- P2 提议对七个 composite intersection-union p-values使用 Holm procedure，强控制 FWER `α=0.05`；Plan A 与 Plan B 不各自获得完整 alpha。不存在的 control/capability slot用数值 `p=1` 且另记 `status=NA_*`，不回收 alpha。
- bootstrap 使用 physical-unit paired differences、batch/protocol stratification、10,000 resamples 和冻结 seed manifest。
- `δ_min`、`δ_NI`、`π_min`、harm margins、`r_max`、`r_rec`、`q_min` 必须由 P2 的工程依据/外部先验/数值 baseline 侧功效程序冻结，不能依据 API arm 易否通过而移动。
- unit-macro MASE 不可机械定义则触发 canonical `NO_CONFIRMATORY_POWER` 或预先允许的 metric fallback；禁止解封后切换 metric。

## 7. Operational endpoints

四项全部报告，唯一 primary proposal 为：

```text
ERROR_FREE_CLOSED_COMPLETION_BY_DEADLINE
= unit-macro fraction of planned origin bundles that, without retransmission,
  reached a durable, schema-valid ACTIVE or DELIBERATE_FALLBACK closed state
  by the frozen workflow deadline; ERROR_FALLBACK and unclosed states count 0.
```

其余三项和所有构成指标为 secondary，并按冻结 multiplicity/描述性规则报告。该 endpoint 目前仍为 `UNFROZEN_PROPOSAL`，必须在 development API 前批准。

故障注入只能进入独立 fault-qualification 记录；它不产生 natural accuracy/WIS observation，不得与未注入故障的 confirmatory accuracy rows 合并。

## 8. Stop/Go 与禁止事项

Canonical Stop/Go 优先。尤其是 `NO_CONFIRMATORY_POWER`、`BLOCKED_API`、Ren Data Gate failure、`KILL_PROTOCOL`、generation barrier failure、formal run invalid 或 P6 audit failure 都不是 Plan B trigger，而是对应 scope 的 STOP/BLOCKED。

Joint unseal 后禁止改 candidate、topology、prompt、roster、router、threshold、estimand、margin、primary endpoint、C_k、seed、resampling、alpha allocation 或 matured-key denominator；禁止为任一 arm 单独二次 seal。

## 9. 当前人工 Gate

`CURRENT_AUTHORITY`：只允许对已存在的 P1-Ren/P1-Patrizi bundles 做只读重新核验、执行已有 static audit，以及不执行预测的文档/代码审查和 offline release checks。当前明确禁止新下载、新数据提取、新解码工具或 parser操作、P2 fitting/training/scoring、SOH/RUL构造或评分、P3、development API、P4/P5、formal outer evaluation和任何真实 LLM电容预测。本文件本身不产生任何执行授权。
