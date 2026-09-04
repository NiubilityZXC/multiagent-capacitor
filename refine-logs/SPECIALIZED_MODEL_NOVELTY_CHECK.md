# 固定专用模型查新报告

**检索截止**：2026-09-04
**状态**：`NOVELTY_CHECK_COMPLETE / METHOD_CLAIM_REJECTED / RETAIN_AS_N0_PLUS`
**执行边界**：只检索、审稿和离线 schema 测试；未运行真实数据模型、RUL、GPU 或 API。

## Proposed Method

候选方法原拟采用跨器件 hierarchical prior、regime-adaptive monotone degradation state-space model、目标器件在线 Bayesian/particle-filter 更新、多 horizon capacitance/SOH trajectory、endpoint-gated RUL、joint calibrated regions 与 anomaly risk，并在 sealed whole-device rolling replay、LOCO、cross-condition、failure-inclusive no-retry 协议下测试。

## Core Claims

| 技术主张 | 新颖性 | 最接近工作/原因 |
|---|---|---|
| 跨器件层级先验＋目标器件在线 Bayesian/PF 更新 | **LOW** | Jia et al. 2026 已给出 similar-system hierarchical prognostics；更早 population-to-individual PF 也存在 |
| 分阶段/单调 capacitor degradation SSM | **LOW** | Han et al. 2024 已从其他电容学习 two-phase/change-time prior，并对 held-out capacitor 在线 Bayesian/filter 更新 |
| 多步 capacitance/SOH trajectory | **LOW** | 已是超级电容 trajectory/SOH 文献中的标准输出 |
| EOL/censoring Gate 后才做 RUL | **LOW** | 是必要评测卫生，不是新算法；已有 censor-aware RUL/interval 工作 |
| 联合多 horizon calibrated prediction regions | **LOW** | FLIPR 2026 已直接处理 joint multi-horizon conformal regions |
| anomaly risk＋在线 aging update | **LOW** | capacitor anomaly detection＋Bayesian online parameter updating 已有直接先例 |
| sealed whole-device replay＋LOCO＋failure-inclusive no-retry | **MEDIUM**（协议组合）；**LOW**（算法） | 组合更严格，但组成原则已知；贡献只能来自可复现的实证发现 |

## Closest Prior Work

| Paper | Year | Overlap | 对当前路线的约束 |
|---|---:|---|---|
| Han et al., *A New Remaining Useful Life Prediction Method for Capacitors Based on Bayesian Updating and Kalman Filtering*, Sensors, DOI `10.3390/s24010165` | 2024 | cross-unit two-phase/change-time distribution、held-out capacitor online update、Bayesian＋KF | 直接击穿“hierarchical regime-adaptive capacitor filter”主张 |
| Jia, Papaioannou, Straub, *A Hierarchical Bayesian Framework for Model-based Prognostics*, arXiv:`2601.15942` | 2026 | similar-system run-to-failure hyperpriors＋target operational updates＋predictive uncertainty | population-to-unit hierarchy不是新机制 |
| Hu et al., *Remaining useful life prediction of supercapacitors based on a state-space model*, JPS 662, DOI `10.1016/j.jpowsour.2025.238778` | 2026 | S4＋RevIN、dual embedding、cross-protocol SC RUL | SSM/RevIN 专用 RUL 路线高度拥挤 |
| Hu et al., *PGA-SSM*, SSRN `6584748` | 2026 | metaheuristic-optimized SC state-space RUL | 仅“优化 SSM”不足以构成强新颖性 |
| E et al., physics-informed LSTM for SC trajectory/RUL, DOI `10.1016/j.geits.2025.100291` | 2025 | physical loss＋LSTM＋Bayesian loss balance＋limited-data trajectory/RUL | physics-guided trajectory/RUL 已有直接实例 |
| Rigamonti et al., capacitor PF prognostics under variable conditions | 2016 | temperature-independent ESR indicator＋PF RUL | capacitor PF 与工况修正早已有之 |
| English & Lippert, FLIPR, PMLR 328 | 2026 | interpretable joint multi-horizon conformal regions | joint calibration不能作为核心创新 |
| Min et al., Energy & Fuels, DOI `10.1021/acs.energyfuels.5c06154` | 2026 | GPD-loss DNN；SI 明确覆盖 full 113 SC 与 batches 1–4 | 同数据域已有新强模型，必须直接比较 |
| SC field-data SOH framework, DOI `10.1016/j.jpowsour.2025.238384` | 2025 | capacitance identification、GPR smoothing、Prophet online SOH forecast | 小数据工程化在线 SOH 也非空白 |

## Overall Novelty Assessment

- **Score**：`2/10`
- **Recommendation**：`ABANDON AS METHOD-NOVELTY CLAIM / RETAIN AS STRONG N0+ BASELINE`
- **审稿独立性**：fresh `gpt-5.6-sol` xhigh reviewer，same-family，故结论记为 provisional；其否定裁决与主执行器检索一致。
- **最强 kill argument**：该组合可由已知 hierarchical prognostics、capacitor PF/phased degradation、joint conformal calibration 与 anomaly scoring 模块拼出；没有新的 transition law、hierarchy、inference operator、calibration theorem 或 decision rule。模块首次组合不等于机制创新。

## 可保留的可证伪假设

固定模型本身没有足够技术 delta。唯一值得以 secondary mechanism hypothesis 预注册的是：

> 在 achieved simultaneous coverage 相同的条件下，condition-conditioned hierarchical shrinkage 能改善 unseen-device cold-start proper predictive score；随着目标器件已观测历史增加，该优势应系统性衰减，并可能在 unseen condition 下转为 negative transfer。

这不是已确认的新颖性。若实验没有 hierarchy×condition×prefix interaction，只能报告 integration/evaluation value。

## 高水平论文的更强定位

主故事应转为 **evaluation finding**：公开 SC 文献中的模型排名、提升幅度或 coverage，在 random/window split 与 sealed whole-device replay 之间是否出现预注册的 collapse/reversal；跨器件 pooling 是否只帮助 5–20% lifecycle cold start，却在跨工况上造成负迁移。结果为正、null 或 negative 都必须保留。

这种定位要求把 candidate hierarchical PF 当作受控测量工具，与 standard PF/UKF、N0-v1、N0+、S4+RevIN/PGA-SSM、113-SC DNN 做同一信息和预算下的比较，而不是把它称为 novel unified framework。

## Decisive Experiments

1. matched 2×2：nonhierarchical/hierarchical × single-regime/switching；固定 state equation、PF particles、update cadence、tuning budget、calibration wrapper。
2. lifecycle prefixes：5%、10%、20%、40%、60%；shrinkage benefit 必须 cold-start 最大并随 history 增加而衰减。
3. condition-label 与 device-identity permutation negatives；single-regime synthetic negative 与 known-interaction semi-synthetic recovery。
4. proper distribution scores：log score、CRPS/energy score；只有在 achieved simultaneous coverage 相同时比较 joint-region volume。
5. conventional random/window split vs sealed whole-device replay；在 reveal 前冻结 ranking-collapse/reversal 定义。
6. unit-level paired/hierarchical bootstrap；所有 timeout、nonfinite、fit failure 和 no-retry fallback 保留。
7. RUL 只在同一 EOL/censoring contract 下评分；异常任务另用 Brier、AUPRC、lead time，不能与 trajectory loss 混成一个分数。

## Route Decision

- `online_ssm_robust_local_trend_pf` 保留为 N0+ selectable baseline。
- 不创建以 hierarchical/regime/PF/conformal 模块拼装为理由的 fixed confirmatory method arm。
- 若真实 sealed replay 产生排名反转、coverage collapse 或 cross-condition negative transfer，再由 `result-to-claim` 决定论文主张；结果揭示前不预写 superiority。
- 查新 trace：`.aris/traces/novelty-check/2026-09-04_run01/`（不提交 Git）。
