# TRACE-Cap 零上下文查新报告

**日期**：2026-07-29  
**review independence**：same-family  
**acceptance status**：provisional  
**总裁决**：`PROCEED_WITH_MAJOR_REPOSITIONING`

## 结论

TRACE-Cap 不应被表述为五项均新的统一算法。只有 EIS—瞬态概率观测桥保留 `MEDIUM` 的窄幅方法潜力；层级双状态/切换、动态专家路由、联合删失/共形和类型化 Agent DAG 均为 `LOW`，应作为既有组件、强基线或领域评测协议。

最稳妥的定位是：

> 测量科学贡献 + 严格电容 PHM 基准：在离线 EIS 稀疏、在线瞬态可用且存在系统测量偏差时，检验一个概率校准观测层能否改善未见电容/应力电压下的 C、ESR 与条件可识别 RUL。

若该桥在 LOCO/LOVO 下无可重复增量，则转为数据审计、统一标签、严格回放、公开代码和可信负结果。

## 逐主张裁决

### A. EIS—瞬态概率观测桥：MEDIUM

**最近邻**

- [Renwick et al. 2015](https://doi.org/10.36001/phmconf.2015.v7i1.2713)：同一 NASA 实验已比较离线 EIS 与在线充放电瞬态时间常数，并报告趋势对应、量级偏差、晚启动及硬件/校准影响。
- [Ou et al. 2024](https://arxiv.org/abs/2404.13399)：从在线电压、电流和开关波形同时估计 C 与 ESR。
- [Online Condition Monitoring for DC-Link Capacitors, 2024](https://doi.org/10.1016/j.compeleceng.2024.109577)：用注入瞬态在线同时估计 C、ESR。
- [Celaya et al. 2012](https://doaj.org/article/1bf4b32c80d844429674df78650a95b4)：把 EIS 健康状态、Kalman 更新、阈值穿越与 RUL 连接。

**可允许主张**

提出并检验一个严格按可用时刻构造的概率校准层，量化离线 EIS 与在线瞬态之间的系统偏差和观测不确定性，并传播到 C/ESR 阈值穿越与 RUL。不得宣称首次发现 EIS—瞬态关系、首次在线估计 C/ESR 或一般因果识别。

**致命反对**

如果不能在配对观测上辨识偏差，并证明该桥相对直接瞬态估计在未见电容和未见电压上改善 proper loss，它只是标准误差变量模型的领域拼接。

### B. 层级双状态、切换退化与在线 RUL：LOW

**最近邻**

- [Wen et al. 2018](https://doi.org/10.1016/j.ress.2018.04.005)：multiple change points、unit heterogeneity、Bayesian online RUL。
- [Sun et al. 2024](https://doi.org/10.2298/TSCI2403295S)：双变量、两阶段 Wiener、random effects 和首次穿越。
- [Chen et al. 2024](https://doi.org/10.1016/j.microrel.2024.115509)：电解电容两阶段 Wiener、顺序 Bayesian 更新和历史 RUL 相似度在线选模。

**可允许主张**

作为电容领域联合状态建模实例，比较单状态与切换状态在 C/ESR 非单调和留一应力电压回放中的适用边界。不得宣称层级随机效应、双变量退化或切换 RUL 建模本身新颖。

### C. 目标×horizon、变化点路由与拒绝：LOW

**最近邻**

- [V’yugin & Trunov 2022](https://doi.org/10.1016/j.patcog.2021.108193)：以 CRPS 在线聚合概率专家和 sleeping/specialist experts。
- [Kairosis 2025](https://doi.org/10.1016/j.ijforecast.2025.03.001)：Bayesian 变化点感知的概率预测动态聚合。
- [TimeRouter 2026](https://arxiv.org/abs/2606.11625) 与[代码](https://github.com/UConn-DSIS/TimeRouter)：TSFM 路由、选择性门控、拒绝和 ensemble fallback。

**可允许主张**

严格评估一个面向电容、带延迟标签的目标×horizon 在线专家路由器，报告何时拒绝复杂专家及其失败边界。不得宣称动态路由、变化点聚合、CRPS 加权或拒绝机制本身新颖。

### D. 联合删失、多输出与共形：LOW

**最近邻**

- [Gao et al. 2025](https://doi.org/10.1109/TPEL.2025.3621772)：电容混合效应退化、proportional hazards、工况协变量和 Bayesian 在线更新。
- [Capacitor anomaly/model update, 2022](https://doi.org/10.1016/j.microrel.2022.114646)：联合 C-loss/ESR 异常检测与 Bayesian 参数更新。
- [Doubly Robust Conformalized Survival Analysis, 2025](https://arxiv.org/abs/2412.09729) 与[代码](https://github.com/msesia/conformal_survival)：右删失生存共形。
- [Conformalized Survival Distributions, 2024](https://arxiv.org/abs/2405.07374)：生存分布共形后处理。

**可允许主张**

给出标签语义一致、显式处理区间/右删失的联合输出与评测接口，并验证校准方法在极小电容样本下的适用边界。不得宣称联合退化—生存、在线 Bayesian 更新、异常检测或共形生存本身新颖。

### E. 类型化 Agent DAG、血缘与影子门：LOW

**最近邻**

- [AgentEval 2026](https://arxiv.org/abs/2604.23581)：DAG step-level evaluation、类型指标、错误传播和根因。
- [Curie 2025](https://arxiv.org/abs/2502.16069)：严谨自动实验 Agent。
- [MLE-bench](https://arxiv.org/abs/2410.07095) 与 [MLAgentBench](https://github.com/snap-stanford/MLAgentBench)：冻结/隐藏 Eval、统一预算和污染风险。
- [From Agent Traces to Trust, 2026](https://arxiv.org/abs/2606.04990)：执行 provenance、污点、访问控制、恢复和治理。

**可允许主张**

发布一个电容预测 Agent 治理与泄漏审计基准，量化类型化证据边是否减少无效候选和错误晋级。不得宣称类型化 DAG、隐藏 Eval、数据血缘、影子部署或人类上线门本身新颖。

## 限制

- 检索截至 2026-07-29；部分 2026 预印本尚未同行评审。
- 部分付费论文只核验题录、摘要、开放预印本或可抓取片段。
- 不是系统专利/FTO 检索，不能证明绝对不存在未索引或非英语工作。
- A/B 的直接电容近邻未检索到官方公开实现；“未找到”不等于“没有”。
- ES10/ES12/ES14 尚未完成 schema 与配对审计。
- 额外 reviewer 因线程上限未启动；当前 reviewer 为 fresh 但 same-family，因此裁决保持 provisional。
