# Research Contract: AUDIT-Cap 最小可识别在线预测基准

> 这是 H0 批准后的聚焦工作契约。TRACE-Cap 全栈保留为长期蓝图；当前只执行数据审计、设计仿真和最小 CPU 基线。

## Selected Idea

- **Description**：从官方公开原始数据建立逐物理电容、逐事件、带可用时间和删失语义的不可变清单；先验证 C/ESR 多步在线回放是否可评，只有终止原因和事件结构通过识别门后才启用 RUL。使用设计仿真确认真实独立样本量是否足以比较模型，再运行 last-value、drift、local-linear、指数/状态空间和 ridge 等简约基线。
- **Source**：`idea-stage/IDEA_REPORT.md` 的审查后最小系统、`FROZEN_EVAL_PROTOCOL.md` v0.2。
- **Selection rationale**：两名零上下文 reviewer 均认为 Benchmark L 的 schema、器件身份、配对和终止结局是首要阻断项；全栈模型在此之前不可识别且不可归因。

## Core Claims

1. **主张 C1（审计/评测）**：公开 NASA/PHM 电容数据可以被机器重建为按物理器件隔离、严格时间可用、显式区间/右删失的 prequential 评测对象；若原始字段不支持，则报告不可识别边界而不补造标签。
2. **主张 C2（条件精度）**：在通过 Data Gate 与 Design Gate 的端点上，简约基线可给出逐器件、逐 horizon 的真实数值基准；任何复杂模型必须在相同预测账本上超过最强简约冠军后才有资格进入。
3. **反主张**：窗口数、频点数和种子不增加独立样本量；文件末尾不是 EOL；LOVO 不是现实跨工况；历史回放不是部署验证。

## Method Summary

数据层保存原始 ZIP/MAT 字节与哈希，并递归审计 HDF5 对象、MATLAB class、shape、dtype、引用、缺失、时间范围和字段语义。事件规范化只生成能从源字段确定的数据；身份、时间或模态关系未知时进入 quarantine。标签构建器按 20% C-loss、ESR×2 与 OR 规则产生 exact/interval/right/unknown 状态，不用轨迹末尾补造 RUL=0。

评测层按整只电容先分折再生成 rolling origins。每个原点只读取当时可用前缀；C/ESR/SOH 的 h-step 标签到达后才计分。RUL 校准只由内层训练器件拟合，测试器件终末结局不得回填。设计仿真按审计得到的器件数、轨迹长度、事件率、删失率和相关结构评估零效应选择错误率、最小有意义效应的检出率和置信区间宽度。

## Experiment Design

- **Datasets**：Benchmark S（NASA Stress-2，6×11）；Benchmark L（ES10/12/14，只有全量审计后才冻结）。
- **Splits**：按物理电容 LOCO；Benchmark L 条件允许时做 leave-one accelerated-stress voltage out。
- **Baselines**：last-value、global drift、local-linear、指数趋势、简约 Kalman/state-space、ridge；不使用深度模型或 LLM 预测。
- **Metrics**：每器件宏平均 MAE/RMSE/MASE，逐 horizon；区间覆盖/WIS 只在合法校准样本存在时；RUL 只在识别门通过时用区间相容 score。
- **Key hyperparameters**：初始上下文、local window、ridge penalty、状态噪声/观测噪声；全部在内层训练器件选择。
- **Compute budget**：数据下载/解压约 11 GB；审计和基线预计 4–20 CPU 小时、<20 GB 派生输出；不使用 GPU。

## Baselines

| Method | Dataset | Metric | Score | Source |
|--------|---------|--------|-------|--------|
| last-value | Benchmark S/L | macro MAE/MASE | 待运行 | 本项目确定性实现 |
| drift/local-linear | Benchmark S/L | macro MAE/MASE | 待运行 | 本项目确定性实现 |
| exponential/state-space | Benchmark S/L | macro MAE/MASE | 待运行 | NASA 经典路线的 clean-room 简化实现 |
| ridge | Benchmark S/L | macro MAE/MASE | 待运行 | 因果窗口特征 clean-room 实现 |

## Current Results

| Method | Dataset | Metric | Score | Notes |
|--------|---------|--------|-------|-------|
| — | — | — | — | H0 已批准；尚未产生模型结果 |

## Key Decisions

- 大包审计优先于模型；Data Gate 失败即停止对应端点。
- Benchmark S 只验证 parser、回放、泄漏哨兵和极小样本行为，不承担复杂模型优越性结论。
- C3 EIS—瞬态概率观测模型、TSFM 和多 Agent 拓扑均不在本轮 must-run。
- 火山方舟/Kimi 不是数值预测器，也不参与指标裁决；如后续 Agent meta-eval 需要，只从环境变量读取凭据。

## Status

- [x] Idea selected
- [ ] Raw data audit complete
- [ ] Design Gate complete
- [ ] Baseline reproduced
- [ ] Benchmark L representative results
- [ ] Full dataset results
