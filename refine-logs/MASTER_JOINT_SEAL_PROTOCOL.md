# Master Joint Seal Protocol

**版本**：2026-08-27 15:28:47 +08:00  
**状态**：`PRESEAL_SPECIFICATION / UNAPPROVED / NOT_SEALED`  
**目标**：让 Plan A 与 Plan B 只产生一个确认性 generation、一个 seal、一个 generation-wide prediction barrier、一次 joint unseal 和一次冻结统计运行。

## 1. 不可变上游

以下 canonical 文件必须在 seal、执行和 unseal 三个时点重新验证：

| 文件 | 必须等于的 SHA-256 |
|---|---|
| `refine-logs/EXPERIMENT_PLAN.md` | `df968d2e7ba33748043e547165143d9247358afca573946f3dde573c8c04b6d2` |
| `refine-logs/round-3-refinement.md` | `d4d40b0a7e3f5c9030bfe80e5ede3d059673c3b3c96122c9cf050097aa54f110` |

任一不匹配均停止；不得自动接受“最新版本”。Plan A addenda 只有在 `CANONICAL_SUPERSESSION_LEDGER.md` 列明、全部文件 hash 固定且人工批准后才可进入 seal。

当前 P1 证据也必须作为不可静默替换的只读上游重新验证：

| P1 evidence | Current path | Bound SHA-256 roots |
|---|---|---|
| decision index | `data/audit/P1_REN_PATRIZI_DECISION_INDEX.json` | file `69cb57366da92252232bc219eb95ff62084859fede921e582ad2118d0e46fad6` |
| Patrizi current bundle | `data/audit/patrizi_hsc/p1_20260828_180200` | `COMPLETE.json=140387643564c8df17f4cd683595db778b7cee9e0af7bd5e79d7e39c3083b6ec`; `ARTIFACT_MANIFEST.json=68fceef2b15ce5593c583afad3a3d64635f7861f075bbb758dc759adfaac065e`; `ARTIFACT_HASHES.sha256=694c4b7890502dc7222772ee364cf213149c9a5d59b93e44242f69fcd53b8d1a` |
| Ren current bundle | `data/audit/ren_scs/p1_20260828_180210` | `COMPLETE.json=2a5a25d9c8d92583aa6ff137010da0b0c16a13e4bbd5fc57861c0a20edec7f72`; `ARTIFACT_MANIFEST.json=eef896f082a7b24f4cd1da7d213f90306045c99c3f66fa69ed92f94f6c231510`; `ARTIFACT_HASHES.sha256=b5ba97584a2c7bff2c76b3a45d7d85282ea81f7e00e1de16ff4db492f7607877` |

这些 roots 只绑定当前 P1 决策证据，不把 `BLOCKED` 变成 `PASS`，也不授权新提取或下游执行。

## 2. Seal 前硬 Gate

按顺序全部满足后才能创建 master seal：

1. M0–M3 final implementation 的 fresh full tests、secret scan、diff review 与独立 release review通过；
2. Ren P1 identity/target/chronology/split Data Gate通过；Patrizi单独给出 PASS 或机械 `B5=NA/BLOCKED`；
3. seal 前 baseline adequacy/文献审查完成，并存在明确的 human `BASELINE_DECISION` artifact（批准、条件批准或拒绝均须显式记录）；本 protocol 不预设它已获批准，任何必要新增 baseline 在 outer/API result 可见前另行批准；
4. P2 完成 target/horizon、N0、metric、power、margins、seeds、joint multiplicity，以及 `C_k` calipers/eligibility algorithm/ties/`NA_NO_MATCH` 语义的冻结；P2 不选定 actual `C_{4,f}`；
5. P3 只证明 authenticated model/capability/schema，形成 requested/returned model registry；
6. development API 经独立人工批准后完成 fold-local tournament，并在 outer score 不可见条件下锁定每 fold 的 ARCH1 candidate/roster；若任一 required fold 无合格 candidate，锁定 generation-wide `BLOCKED_ARCH_DEV` 和 ARCH1 机械 NA slots，该状态本身不阻止 master seal 继续包含 Plan B；随后在 seal 前使用 P2 冻结算法选定 actual `C_{4,f}` 或 `NA_NO_MATCH`；
7. P4/P5 execution envelope 获独立人工批准；
8. formal evaluator 已证明在 generation-wide barrier 前无法读取 label、loss、arm score 或跨 arm summary。

任何前置 Gate 的 mock PASS 都不能替代真实 Data/API/confirmatory Gate。

## 3. Master seal 内容

`MASTER_SEAL.json`（未来实现）必须 canonical serialize 并至少绑定：

- generation ID、UTC/local timestamp、operator approval artifact hash；
- canonical 两文件 hash、本文件绑定的 P1 decision-index/bundle roots、全部 Plan A addenda hash、source code tree hash、environment lock hash；
- 明确 baseline decision、architecture registry、hypothesis registry、preseal manifest 与 fault manifest 的 file hash 及独立 approval/status artifact；
- raw/processed data manifests、unit registry、fold registry、planned-key manifest 与 maturity rule hash；
- arm registry：11 canonical arms 加唯一 `ARCH1`，以及 capability 导致的机械 admitted/NA 状态；
- 每个 outer fold 的 ARCH1 candidate ID、role/edge/schema/prompt hashes、backbone/roster mapping，或 generation-wide `BLOCKED_ARCH_DEV` 及其机械 NA mapping；
- P2 冻结的 `C_k` algorithm/calipers/ties/NA hash，以及 P3/tournament 后、seal 前产生的每 fold eligibility ledger 和 actual 唯一选择/`NA_NO_MATCH`；
- numerical experts、fusion、calibration、Action registry、fallback bundle 与 target/unit schemas；
- `O_R`、`O_P`、`R_API`、每 arm/worker **planned/reserved** physical-slot manifest与最大 send opportunities、requested ceiling、deadline、decode、tools/cache/store、provider version policy；actual send attempts 只能在执行后由 attempt ledger 绑定，且对每 slot 为 0 或 1；
- arm-order block randomization、concurrency、time-drift controls 与 seed manifest；
- complete confirmatory contrast family、harm gates、margins、bootstrap/statistics executable hash；
- generation barrier、prediction ledger、attempt ledger、worker artifact ledger 和 unseal authorization schema。

不记录凭据、raw provider response、隐藏 reasoning 或任何价格。Tokens/attempts/latency只以执行事实字段存在。

上述 baseline decision、architecture/hypothesis registries、preseal manifest 和 fault manifest 是未来 seal 的必需输入。当前 baseline decision 为 `PENDING_HUMAN_DECISION`，两个 registries 为未批准草案，preseal manifest 只可记录 `UNAPPROVED/NO_EXECUTION_AUTHORITY`，fault manifest 尚未冻结；任何一个文件的存在或 hash 都不构成批准。

## 4. Admitted cell universe

在 seal 时先生成完整 typed plan。`R_API` 是重复次数，不是 Cartesian value；API arms 使用显式 `replicate_id∈{1,…,R_API}`，deterministic arms 使用唯一 `replicate_id=0`，不能被重复伪装成额外观测：

```text
CELL_API = domain × outer_fold × unit × origin × api_arm × replicate_id
CELL_DET = domain × outer_fold × unit × origin × deterministic_arm × {0}
WORKER_SLOT(D4-H/D4-X/ARCH1) = CELL_API × {w1,w2,w3,w4}
```

`domain` 至少含通过 Gate 的 Ren；Patrizi只有在其 P1 Gate通过且联合 prompt/architecture/contrast 已 seal 时 admitted。每个 planned origin bundle内覆盖全部 frozen target×horizon×quantile keys。

arm registry 必须包含全部 canonical 11 arms 加 `ARCH1`；每个 arm/domain 都有 `ADMITTED/NA/BLOCKED`、预注册 reason code、arm-specific planned physical-slot count与授权 artifact hash。`BLOCKED_ARCH_DEV` 是 ARCH1 的允许 generation-wide 机械状态，其 confirmatory slots 固定为 `NA_BLOCKED_ARCH_DEV, p=1`，但不删除 Plan B cells或阻止它们进入同一 master seal。只有预注册 capability Gate、Data Gate、development qualification 或 canonical Stop/Go 可在 seal 前把 cell机械标为 `NA/BLOCKED`。资源优先级不得事后删 cell。

Canonical execution status保持字节语义不变，并与闭合/验证状态正交：

```text
execution_status      ∈ {ACTIVE, DELIBERATE_FALLBACK, ERROR_FALLBACK}
closure_status        ∈ {CLOSED, UNCLOSED}
cell_validation       ∈ {VALID, INVALID}
run_validation        ∈ {VALID, FORMAL_RUN_INVALID}
```

`FORMAL_RUN_INVALID` 不是第四种 execution status；它会阻止 unseal，而不是从 denominator 删除。

## 5. Generation-wide prediction barrier

在 barrier PASS 前，任何执行者、candidate selector、人工 reviewer 或统计进程都不得得到：

- held-out label、maturity outcome 或 terminal suffix；
- outer loss、arm summary、relative rank、comparison sign 或 preliminary plot；
- 按成功返回重新计算的 matured-key交集。

Barrier 仅在以下全部为真时签发：

1. 每个 admitted cell 的每个 planned physical slot 均有不可变 typed closure：已进入 transport send 的 slot 恰有一次 actual send attempt，因全局/worker deadline 在 send 前闭合的 slot 为 `NOT_STARTED_DEADLINE` 且 actual send attempts 恰为 0；
2. 每个 cell 有 durable prediction/fallback artifact，且 hash、schema、parent linkage通过；
3. 每个 ARCH1 worker output 与 final arbitration均存在或有 typed failure closure；
4. prediction count 精确等于计划 count，无 orphan、duplicate、late overwrite、retry 或跨 cell artifact；
5. common planned keys 与 fixed outcome-availability rule 的 hashes和 seal一致；
6. 所有 arm 已完成，而不是仅 Plan A 或当前看似有希望的 arms完成。

Barrier失败即 `FORMAL_RUN_INVALID`；不得部分 unseal。

## 6. Joint unseal

Joint unseal 是一次性状态迁移：

```text
SEALED_EXECUTION
  --[barrier PASS + separately approved unseal authorization artifact]-->
JOINT_UNSEALED_READ_ONLY
  --[exact frozen statistics executable once]-->
ANALYSIS_COMPLETE
```

- 一次打开全部 eligible labels并只运行 seal 中 hash-pinned 的统计程序。
- 统计输出必须同时包含 Plan A 与 Plan B、全部 arms、全部预注册 contrasts、fallback/operational tables 和机械 NA/BLOCKED。
- 不允许 Plan A、Plan B、ARCH1、B5 或任一 arm 各自单独解封。
- joint unseal 后只能做不改变 estimand/arm/denominator 的验证性重算；任何程序修复必须由 P6 独立审计判定是否仍可作确认性证据，不能静默覆盖首个输出。

## 7. 执行顺序与 time-drift

执行优先级为：Plan A主对比及合格 `C_k`、Plan B canonical MUST-RUN、B5、`R_API=3`升级、appendix NICE-TO-HAVE。该顺序只用于 **seal 前 scope/resource planning**，不能成为正式运行的时间分组。一旦 admitted，全部 arms必须在 unit/origin blocks内平衡交错；资源若不足以覆盖所有 MUST-RUN admitted cells，则不得 seal。`R_API=3` 也必须在任何 `R_API=1` outer结果可见前决定，不能作为结果驱动升级。

- 在每个 unit/origin block 内，用冻结 seed 对 arm 次序随机排列或平衡轮转。
- 并发上限、worker启动方式、model requested/returned policy、temperature/decode、tools/cache/store 与 deadline在 seal 中固定。
- 各 arm 在时间块中平衡交错，避免某 arm系统性落在特定服务时段。
- provider outage、rate limit、timeout、late response和model drift均按预冻结状态记账，不触发 accuracy retry。

## 8. Stop/Go 优先级

`KILL_PROTOCOL`、Ren Data Gate failure、`NO_CONFIRMATORY_POWER`、`BLOCKED_API`、generation barrier failure、formal invalid 或 P6 audit failure 按 canonical Stop/Go 执行，不属于 Plan B narrative trigger。

Plan B trigger 只能在：全部 admitted cells完成 → barrier PASS → joint unseal → frozen statistics完成 → P6 independent audit PASS之后，依据 Plan A 基础档的机械结果发生。P6 failure 是 STOP，不是 Plan B trigger；触发器不产生任何新增执行。

## 9. Generation 2

Generation 1 解封后若 Plan A 未达标，结果永久保留。只有用户另行批准并取得新 fleet/批次，才可创建修改架构的 Generation 2。Generation 1可作为后续 development 信息，但不能取消其确认性身份；新确认性结论只能来自新 sealed evaluation data。

## 10. 当前裁决

`NOT_SEALED`。

`CURRENT_AUTHORITY`：只允许对上述已存在 P1 index/bundles 做只读重新核验、执行已有 static audit，以及不执行预测的文档/代码审查和 offline release checks。当前明确禁止新下载、新数据提取、新解码工具或 parser操作、P2 fitting/training/scoring、SOH/RUL构造或评分、P3、development API、P4/P5、formal outer evaluation和任何真实 LLM电容预测。本 proposal、其 hash或任何 mock/test 结果都不产生执行授权。
