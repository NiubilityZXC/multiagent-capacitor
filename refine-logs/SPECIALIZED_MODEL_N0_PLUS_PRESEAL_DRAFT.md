# N0+ 专用模型预封存增补草案

**时间**：2026-09-04 13:46:14 +08:00
**状态**：`DRAFT_ONLY / NOT_APPROVED / NOT_SEALED / NO_EXECUTION_AUTHORITY`
**父协议**：`refine-logs/EXPERIMENT_PLAN.md`（保持原文件与 hash 不变）
**目标**：在不读取 outer-test loss、不调用 LLM、不运行真实模型的前提下，把专用数值模型路线定义为可批准、可实现、可证伪的下一代 `N0+` policy。

## 1. 决策摘要

本草案建议优先批准 **N0+ selection policy**，而不是现在指定某个未经真实数据检验的模型为固定 superiority arm。N0+ 将旧 `N0-v1`、经典时序、在线状态估计、小样本机器学习和两种紧凑现代序列模型纳入有限候选池；每个 outer fold 只在 outer-training units 内用 nested whole-unit CV 选择 champion。选出的 champion 同时成为所有 Agent 臂唯一、逐字节相同的 `FALLBACK`。

这一定义支持两条可发表结论，但不保证正结果：

1. 专用模型论文：检验整个预注册 `N0+ policy` 是否相对旧 `N0-v1` 提升真实 whole-device 在线预测，并给出跨工况边界。
2. Agent 论文：direct LLM、LLM+专用模型和多 Agent 必须相对更强的 N0+ 比较；若不胜，严格负结果仍有效。

## 2. Claim Map

| Claim | Why It Matters | Minimum Convincing Evidence | Linked Blocks |
|---|---|---|---|
| **S1 — numerical policy value**：预注册 N0+ policy 在 Ren whole-unit rolling replay 上优于旧 N0-v1，或在 point loss non-inferior 时取得预注册的 WIS/failure/latency operational gain。 | 决定专用模型能否独立成为论文主线，并防止用弱 numerical baseline 衬托 Agent。 | paired physical-unit effect；practical margin；WIS/failure harm gates；全部 outer units 和失败进入分母；nested selection 不接触 held-out suffix。 | SB1–SB4 |
| **S2 — transportability boundary**：N0+ 在 Patrizi compatible target 上的方向和失效边界可被复现地估计。 | 高水平论文需要跨器件/工况边界，而不是随机窗口内插。 | separate-domain LOCO；不与 Ren 池化；target/unit/identity Gate 通过；报告每单位 effect 与 uncertainty。 | SB5 |

### Anti-claims

- 不把 inner-CV winner 事后称为“固定模型 superiority”；可主张的对象是完整 selection policy。
- 不把 window 数、origin 数或 API replicate 当独立样本。
- 不把 synthetic Stress-2 结果、LLM 评语、模型规模或训练 loss 当真实预测证据。
- 不把 capacity、capacitance、ESR、SOH 或 RUL 互换；endpoint 未过 Gate 时对应 task=`NA`。
- 不因某模型安装失败而在看到其他 outer score 后替换候选；failure/NA 规则在 seal 前固定。

## 3. 有限候选池

### Tier A：CPU 优先、必须实现

| Family ID | Constituent | 冻结角色 | 预封存约束 |
|---|---|---|---|
| `LEGACY` | 原六 experts＋五 fusions 的 `N0-v1` | 必须候选、旧基线、所有失败的最终安全锚点 | 复用父协议语义；不得删除 |
| `CLASSICAL` | `AutoETS`、`AutoARIMA`、`DynamicOptimizedTheta` | 规则/平稳性/趋势强对照 | 仅 prefix；实现库、版本、自动搜索空间、季节频率与 tie-break 在代码 seal 时固定；不规则网格则按机械规则 `NA` |
| `ONLINE-SSM` | causal RLS/RELS trend；robust local-level/local-slope particle filter | 在线适应、区间与异常风险候选 | 状态方程、likelihood、粒子数、重采样、seed、train-scale noise grid 和失效语义全部在 outer score 前固定 |
| `SMALL-ML` | direct-horizon Elastic Net；HistGradientBoosting | 适合小 fleet 的特征模型 | 仅 past-prefix 特征；scaler、imputer、feature selection 和 tuning 只能在 outer-training/inner folds 中拟合 |

### Tier B：紧凑现代序列模型、通过 compute Gate 后必须实现

| Family ID | Constituent | 冻结角色 | 预封存约束 |
|---|---|---|---|
| `DLINEAR` | direct multi-horizon DLinear | 简洁现代负/强对照 | 固定 context/horizon、optimizer、epoch cap、early stopping source、3 seeds；单架构总计不超过批准的 2 GPU-hours |
| `NHITS` | direct multi-horizon N-HiTS | 非线性多尺度强基线 | 同一输入信息、训练预算和 3-seed aggregation；不得比 DLinear 多看数据或调参 |

### Tier C：单独报告的 frontier stress，不参与 N0+ champion 选择

`Chronos`、`TimesFM`、`Moirai` 只做冻结版本 zero-shot/allowed-shot stress。其 checkpoint、revision、license、quantile mapping、context truncation、device 和预训练污染披露必须固定。它们不进入 N0+ global selection，防止版本/下载可得性改变 fallback；也不能在看到 N0+ outer result 后挑一个最佳 TSFM 报告。

### Conditional RUL family

`S4+RevIN` 与可复现的 physics-constrained RUL model 仅在 EOL、right censoring、RUL unit 和模型输入全部通过独立 endpoint Gate 后进入一份新的 task-specific addendum。它们不得借 capacity/SOH trajectory 的批准自动获得 RUL 执行权。

## 4. Candidate Selection Policy

对每个 outer fold、target、horizon，执行以下不可变顺序：

1. outer-test unit、suffix、label、loss 对 feature、fit、calibration、hyperparameter 与 selection 进程均不可见。
2. 每个 family 仅用 outer-training units 做 deterministic nested LOCO；inner risk 先 unit 内聚合，再跨单位 macro-average。
3. family 内按 primary metric 选 winner；差值落入预冻结 tie tolerance 时按固定顺序选择复杂度更低者：`LEGACY → CLASSICAL → ONLINE-SSM → SMALL-ML → DLINEAR → NHITS`。
4. global champion 只在六个 family winners 中选择；Tier C 不参与。`N0+=b_star=FALLBACK` 的 point/quantile bundle 写入同一 immutable registry。
5. 任一 train/forecast/nonfinite/schema/deadline failure 计入该 constituent 的 inner risk；不得 retry 后隐藏。family 全部失败则 family=`NA`；全部新增 family 为 `NA` 时机械回退到 `N0-v1`。
6. 外层只评估一次已关闭的 policy。所有 constituent outer predictions 可作为透明诊断保存，但不能用于改 policy、重排模型或选论文主角。

## 5. 输入与特征防泄漏

所有模型共享相同的 `(unit_hash, origin, availability_cutoff, target, horizon)`。允许的特征只能由 origin 及以前的观测机械计算，包括：当前水平、有限差分/稳健斜率、局部曲率、prefix 长度、缺失间隔、train-only 标准化残差，以及经 P1 验证的工况字段。禁止使用：未来终止长度、future missingness、EOL distance、完整序列归一化、outer-unit statistics、从文件名推断的 outcome proxy、跨 origin 的最新真实误差。

所有 imputation、scaling、feature screening、calibration 和 fusion weights 都以 outer-training 为边界。特征代码、列顺序、dtype、缺失规则和 train-state bytes 必须 hash-pin。

## 6. 不确定性、异常风险与失败

- 所有 admitted model 输出 point 与 0.05/0.10/0.25/0.50/0.75/0.90/0.95 quantiles，或通过 outer-training-only residual conformal wrapper 产生等价区间。
- 区间必须 finite、ordered、nested 并满足 target domain；任何违规触发 whole-origin fallback，不做结果后 clipping。
- 异常风险由 prefix-only standardized innovation、filter degeneracy、out-of-training-support distance 与 interval width 的冻结组合给出；没有未来 label 时不能自称 fault probability。
- primary replay 沿用 `accuracy_v1`：一个 physical fit/forecast attempt、无 retry；late/timeout/crash/nonfinite 均保留并进入 failure denominator。
- 对不可计算 RUL 的 unit/origin 输出 typed `RUL_NA`，不得用 run end 伪造 EOL。

## 7. Experiment Blocks

### SB1 — Data/target and causal replay qualification

- **Claim tested**：S1/S2 的必要前提。
- **Dataset / split / task**：Ren primary；Patrizi separate external；Benchmark-L excluded。
- **Success criterion**：identity、units、chronology、target derivation、split、origin、maturity 和 censor rules 全部机械可判定。
- **Failure interpretation**：Ren fail 则停止 numerical/Agent accuracy；Patrizi fail 只令 SB5=`NA/BLOCKED`。
- **Priority**：MUST-RUN，当前仍由 P1/P2 gate 阻断。

### SB2 — Tier-A numerical floor

- **Compared systems**：N0-v1、CLASSICAL、ONLINE-SSM、SMALL-ML。
- **Metrics**：unit-macro MASE primary；MAE/RMSE、WIS、50/80/90 coverage、failure、CPU time、peak memory secondary。
- **Success criterion**：所有 eligible constituents 产生完整 common-key records；nested selection 与 final fallback bytes 可重建。
- **Failure interpretation**：新增模型不胜不构成项目失败；保留 N0-v1 并报告强负结果。
- **Table target**：专用模型 Table 2；Agent 论文 numerical floor。
- **Priority**：MUST-RUN after approval and P1/P2 release。

### SB3 — Compact modern necessity

- **Compared systems**：Tier-A champion、DLinear、N-HiTS。
- **Success criterion**：在相同信息和冻结预算下给出 outer whole-unit estimate；现代模型只有通过 effect 与 harm gates 才可称有增量。
- **Failure interpretation**：两者不胜支持“小样本退化任务无需更大 learned forecaster”，但仅限冻结数据/预算。
- **Table target**：Main ablation or appendix，取决于 S1。
- **Priority**：MUST-RUN only after separate compute Gate。

### SB4 — Selection-policy isolation

- **Compared systems**：N0-v1、best fixed family chosen before outer reveal、full N0+ nested policy、equal-weight family ensemble。
- **目的**：区分模型能力、nested selection 和简单 ensemble，不把候选池扩大本身包装成方法创新。
- **Success criterion**：N0+ 对 N0-v1 的 paired-unit effect 达到 P2 冻结的 practical margin，且 WIS/failure harm gates 通过；或明确报告 null/negative。
- **Table target**：Main Table 3；family-selection heatmap 为 appendix。
- **Priority**：MUST-RUN。

### SB5 — External condition boundary

- **Compared systems**：完全冻结的 N0-v1 与 N0+；可选 fixed family 只按 Ren training rule选择，不用 Patrizi loss。
- **Setup**：Patrizi separate LOCO；compatible capacity-SOH only；一策略一设备混杂显式报告。
- **Success criterion**：全部 eligible units 与 failures 报告；不要求显著性，不池化 Ren。
- **Failure interpretation**：反向或高方差即 scope boundary，不更换模型救结论。
- **Priority**：MUST-JOURNAL if P1 eligible。

## 8. 统计与论文裁决

- S1 单独形成 numerical primary family；paired physical-unit cluster bootstrap 与 practical margin 在 P2、outer reveal 前冻结。若同时检验 superiority 与 operational non-inferiority，使用预注册层级检验而非挑选较有利结论。
- 原 Agent primary family `D1-RAW−N0`、`ACT1−N0` 中的 `N0` 若采用本增补，必须统一替换为 N0+，重新生成 generation/hash，并重新审查；不得同时对旧弱 N0 申报 positive。
- S2 只作 separate-domain effect/uncertainty 与方向性边界，除非独立单位功效足够且另行封存。
- 若 N0+ 正而 Agent 负，可形成专用 numerical paper；若 N0+ 与 Agent 均无正结果，可形成 protocol/benchmark negative paper；任何 storyline 都由数值证据决定，不由 LLM 评分决定。

## 9. Run Order、停止条件与预算

| Milestone | Goal | Runs | Decision Gate | Cost envelope | Stop condition |
|---|---|---|---|---|---|
| `SN0` | 生成新 policy generation | schema、candidate registry、dependency lock、hash、unit tests | 人工批准本 draft 后开始 | CPU only，0 model score | 任一候选/feature/metric未固定 |
| `SN1` | Tier-A implementation qualification | toy causal fixtures、prefix invariance、failure injection | fresh code review PASS | CPU only | suffix/outer statistic可影响预测则 kill |
| `SN2` | P1/P2 data and Eval freeze | eligible rows、splits、keys、metric、power、margin | independent preseal review PASS | CPU preferred | target/power不可定义则 no confirmatory claim |
| `SN3` | Tier-A real replay | SB2＋SB4 | complete common keys, one joint unseal | CPU budget由 P2 manifest机械生成 | 任何 partial reveal/adaptive edit使 generation invalid |
| `SN4` | Tier-B modern replay | DLinear＋N-HiTS | separate GPU approval；same sealed keys | ≤2 GPU-hours/architecture，3 seeds | 预算或 reproducibility 不满足则 typed NA |
| `SN5` | external and audit | SB5＋P6 | ledger/code/statistics/claim audit PASS | CPU/GPU沿用冻结 envelope | audit fail 则不作 performance claim |

Tier C TSFM、RUL-specific models 和 fixed novel specialized arm 不在本执行预算内，均需单独 addendum。依赖安装也属于 `SN0`，必须在批准后记录 lockfile、package source 与 artifact hash。

## 10. 必需消融

1. `N0-v1` vs Tier-A champion vs full N0+：识别新增候选是否真正提供 value。
2. full features vs level/slope-only：排除 feature count 造成的表观改进。
3. nested selection vs equal-weight family ensemble：识别路由/选择价值。
4. point model + conformal vs native probabilistic model：识别 interval 改进来源。
5. prefix-only invariant test：修改 hidden suffix 后 prediction bytes 必须不变。
6. success-only vs intention-to-treat 仅作为预注册 shadow analysis；主结果永远保留 failures。

## 11. 仍需在代码 seal 前填充的字段

以下字段当前必须保持 `TBD_BEFORE_SEAL`，不能伪造为已冻结：P1 eligible unit/row counts、target units、grid regularity、outer folds、origins/horizons、MASE epsilon、practical/harm margins、dependency versions、model hyperparameter grids、seed manifest、CPU/GPU wall budget、candidate/code hashes、最终 generation ID。任一字段只能根据数据审计或预结果工程约束填写，不能读取 outer score 后填写。

## 12. 人工批准语义

只有用户逐字批准 `APPROVE_N0_PLUS_POLICY`，才授权进入 `SN0`：实现/依赖锁定/离线 toy tests，以及在 P1/P2 前继续完成新的 preseal generation。该批准本身仍**不**授权真实模型拟合、outer scoring、RUL、Ark/API 或 GPU。

若用户希望一个新专用模型作为独立 confirmatory arm，需另用 `APPROVE_FIXED_SPECIALIZED_ARM:<exact_model_id>`；它不由本草案自动授权，也不能用 N0+ 的事后 winner 补办。
