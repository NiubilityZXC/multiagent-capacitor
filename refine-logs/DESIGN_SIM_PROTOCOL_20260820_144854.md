# AUDIT-Cap B1 Design Simulation Protocol v0.2-B1.1

**Frozen before numeric execution**：2026-08-20  
**Parent protocol**：idea-stage/FROZEN_EVAL_PROTOCOL.md v0.2  
**Scope**：轨迹比较 quick sanity；不执行或裁决 RUL Design Gate。

## Estimand and decision unit

对固定 target、horizon 与同一预测账本，先在每只物理电容内平均损失 L_mi，再形成配对差 D_i=L_incumbent,i-L_candidate,i。独立样本量始终是器件数 N，不是窗口数、频点数或随机种子数。主效应为 1-mean(L_candidate)/mean(L_incumbent)。

- H0: E[D_i] <= 0；H1: E[D_i] > 0。
- 最小有意义效应固定为 10%。Quick 只运行 0%、10% 与指定 Stress-2 场景的 -5% 伤害哨兵；5%/15% 仅属于未来 formal grid，不是 quick cells。
- 唯一候选用单侧 paired t，family alpha=0.04；K>1 用 Holm，总 alpha=0.04。
- N<12 不允许确认性冠军裁决；Stress-2 只作描述性实现验证。
- 若多个候选通过 Holm，最低损失候选还必须在预先定义的 runner-up 配对检验中通过 alpha=0.04，否则 NO_CHAMPION/TIE。

## Trajectory DGP

每个器件生成共享难度 b_i、AR(1) 时间难度 u_it，以及具有冻结 residual paired correlation rho 的模型特异噪声。误差为 lognormal；候选零的位移 delta=-log(1-r)，因此边际期望绝对误差相对 incumbent 改善 r。其他候选在 K=5 场景为 null。所有模型共享相同 unit、origin 与 availability mask；每只器件的轨迹长度可不等，但分析端仍只产生一个单位级损失。

参数含 N、每器件平均成熟原点 M、unit ICC、AR phi、residual paired correlation、measurement availability、length CV 与候选数 K。rho 不等于总 log-error 或 unit-loss correlation；输出必须另报 realized unit-loss correlation。每器件长度上限 200，避免把极长轨迹解释为新增独立样本。

## Quick trajectory cells

| Scenario | N | M | ICC | phi | rho | availability | length CV | K | Role |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| QT0_h1 | 6 | 7 | .4 | .6 | .8 | 1.0 | 0 | 1 | Stress-2 h=1 |
| QT0_h2 | 6 | 6 | .4 | .6 | .8 | 1.0 | 0 | 1 | Stress-2 h=2 |
| QT0_h3 | 6 | 5 | .4 | .6 | .8 | 1.0 | 0 | 1 | Stress-2 h=3 |
| QT1 | 12 | 25 | .4 | .6 | .8 | .9 | .5 | 1 | reference |
| QT2 | 6 | 7 | .7 | .9 | .3 | .7 | .5 | 1 | hard small-N |
| QT3 | 12 | 25 | .4 | .6 | .8 | .9 | .5 | 5 | multiple candidates |

每场景运行 effect {0,10%}；三个 QT0_h* 另运行 -5% 伤害哨兵，共 15 cells。每 cell 200 repeats，共 3,000 repeats。seed=SHA256(global_seed=20260813, canonical cell, repeat)。输出逐 repeat ledger 和逐 cell summary。

## Quick acceptance and non-claim

Quick 仅要求：程序确定性、shape/单位级聚合正确、null 交换性没有明显异常、伤害候选不被系统晋级、所有单元输出数值有限。无论观察到何种率，状态固定为 NOT_EVALUATED_QUICK_SANITY；不得由 200 repeats 宣称 Design Gate 通过。

正式 Gate 的预注册标准保留为：required anchor 上 null false promotion 的点估计 <=5% 且单侧 95% Clopper-Pearson 上界 <=5%；名义 95% 比较 CI coverage 在 [0.93,0.97]；10% effect power 的单侧 95% Clopper-Pearson 下界 >=80%；K=5 正确冠军概率下界 >=80%、null 无冠军率下界 >=95%；10% cell 绝对效应偏差 <=2 个百分点。正式运行至少 2,000 repeats/cell，并对 required anchors 扩展到 10,000。

## RUL module gate

Stress-2 原始 MAT 不含 termination_reason，末次未越界不能证明行政右删失；其物理器件身份也未嵌入。故本轮 quick 的 RUL simulation、RUL metric 与 RUL champion 均为 NA_outcome_and_termination_gate_unresolved。只有大包 outcome/censor gate 通过后，才冻结 interval/right-censored conditional NLL DGP；unknown termination 永不重标为 right censor。

## Leakage and integrity rules

- generator 可以读取 true effect，analyzer 只接收 incumbent/candidate 的 unit-loss arrays。
- 若某器件 availability mask 没有任何成熟原点，该 repeat 显式 FAIL/NA 并计入 planned denominator；不得强造 observed[0] 或静默删除。
- repeat seed 只由 frozen scenario、effect 与 repeat index 决定，不含本次 repeats 预算，因此 200→2000 保留前 200 条流。
- 所有模型共享 maturity mask；缺失或失败不得静默删除。
- 逐 repeat seed、cell hash、effect estimate、decision、coverage 写入 append-only ledger。
- Quick 外层结果不得改写 alpha、MME、K、tie rule 或正式 Gate 门槛。
