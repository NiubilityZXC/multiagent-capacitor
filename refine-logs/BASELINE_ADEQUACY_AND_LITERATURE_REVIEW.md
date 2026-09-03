# Seal-Before Baseline Adequacy, Literature Review, and Novelty Check

**检索截止**：2026-08-28  
**状态**：`PRESEAL_REVIEW_COMPLETE / BASELINE_ADEQUACY_BLOCKED_FOR_DECISION / NO_MODEL_RUN`  
**范围**：公开电容退化/RUL、online estimation、时间序列预测、LLM/Agent forecasting、PHM Agent benchmark、uncertainty与评测泄漏

## 1. Retrieval statement

`research-lit` source order已执行。项目 `papers/`、`literature/`及 AGENTS.md均没有可用本地 PDF library：

> WARN: local contributed nothing — no PDFs found in papers/, literature/, or a configured paper library. To include yours, add a "## Paper Library" heading to AGENTS.md followed by the directory path.

本轮因此使用 arXiv元数据、出版社/会议官方页面、论文官方代码仓库与数据发布页。优先采用 primary/official sources；搜索结果不能替代全文复现实验。没有下载新论文 PDF，也没有运行作者代码或任何预测模型。

## 2. Data and capacitor-PHM literature

| Work | Verified contribution | Relevance / caution |
|---|---|---|
| Ren et al., *Engineering early prediction of supercapacitors' cycle life using neural networks*, MTE 2020, [DOI](https://doi.org/10.1016/j.mtener.2020.100537), [code/data](https://github.com/GlimmerR/SCs) | 报告88个 commercial SC、first 657 cycles≈16%、ANN early-life prediction；作者仓库提供raw.rar处理脚本 | 本项目已验证payload hash，但7z对233 members全部`Unsupported Method`；不能运行author script或借paper补row semantics |
| Patrizi et al., *Study of Accelerated Ageing Effects on Hybrid Supercapacitors...*, IEEE TIM 2025, [DOI](https://doi.org/10.1109/TIM.2025.3577838), [Figshare](https://figshare.com/articles/dataset/Study_of_Accelerated_Ageing_Effects_on_Hybrid_Supercapacitors_Under_Different_Fast-Charging_Strategies/29153561) | 8 HSC channels、fast-charging策略、EIS与degradation observations | 本项目raw/PDF字段、dtype、duration prose存在冲突；ch1…ch8不足以证明physical identity；B5保持blocked |
| Yi et al., *Prediction of the RUL of Supercapacitors*, 2022, [DOI](https://doi.org/10.1155/2022/7620382) | 综述model-based、filtering与data-driven SC RUL | 支持PF/state-space/LSTM baseline families；不提供本项目的failure threshold |
| Sawant et al., SC capacitance/RUL ML review, J. Energy Chemistry 2023, [DOI](https://doi.org/10.1016/j.jechem.2022.11.012) | 综述SC capacitance与RUL ML | 说明仅用六个简单trend模型不足以声称baseline adequacy |
| Naseri et al., online SC-bank condition monitoring, 2017, [DOI](https://doi.org/10.1049/iet-est.2017.0013) | RELS在线估计ESR和capacitance、residual fault detection | 必须考虑online RLS/RELS baseline；但测量protocol需和dataset一致 |
| Chiang et al., recursive least-squares SC parameters, 2016, [DOI](https://doi.org/10.1109/TEC.2016.2521324) | real-time equivalent capacitance/resistance identification | 进一步支持state-estimation baseline，不允许把generic IR静默称ESR |
| Xu et al., feature-enhanced early-cycle ML, Electrochimica Acta 2025, [DOI](https://doi.org/10.1016/j.electacta.2025.147039) | static/instantaneous/trend features、RFE与gradient boosting；论文报告first-500-cycle结果 | `GBR-EARLY`是明显必要的domain baseline；其论文数字不能当本项目结果 |
| E et al., PINN-LSTM SC degradation/RUL, 2025, [DOI](https://doi.org/10.1016/j.geits.2025.100291) | physical loss + LSTM、Bayesian loss balancing、trajectory与RUL | 物理约束/专用RUL模型是必要比较方向；只在相同可观测变量和failure semantics可复现时admit |
| Hu et al., S4 state-space SC RUL, J. Power Sources 2026, [DOI](https://doi.org/10.1016/j.jpowsour.2025.238778) | S4+RevIN用于nonlinear degradation与cross-protocol RUL | 直接削弱“modern sequence model不必要”的立场；应提议 `S4-RUL` baseline |
| pre-classifying deep SC RUL, J. Energy Storage 2024, [DOI](https://doi.org/10.1016/j.est.2024.113458) | clustering/pre-classification后end-to-end RUL | 说明专用RUL路线已拥挤；若RUL Gate通过应纳入related work/可能baseline |

### Endpoint definitions constrained by evidence

- **Capacitance**：farads及冻结measurement/estimator；Ah capacity/throughput不是capacitance。
- **ESR**：ohms及冻结frequency/time-domain estimator；generic IR不是自动ESR。
- **SOH**：必须声明 reference（如 `C_t/C_ref`）和conditioning；无reference则blocked。
- **RUL**：到预注册observable failure event的剩余cycle/time，并处理right censoring；run结束不自动是failure。
- IEC 62391-2 endurance表常见 `ΔC/C` 与 internal-resistance limits，但它是特定test/part标准，不能替代原数据的unit/protocol/terminal semantics。标准预览：[IEC 62391-2:2025](https://cdn.standards.iteh.ai/samples/115392/3d942fa1acbd461380754811d5254ed5/IEC-62391-2-2025.pdf)。

## 3. Strong forecasting baselines

| Family | Primary source | Adequacy consequence |
|---|---|---|
| simple linear/decomposition | DLinear, AAAI 2023, [paper](https://ojs.aaai.org/index.php/AAAI/article/download/26317/26089), [code](https://github.com/honeywell21/DLinear) | simple model can beat complex Transformers；must-run negative control candidate |
| patch Transformer | PatchTST, ICLR 2023, [paper](https://openreview.net/pdf?id=Jbdc0vTOcol) | long context/self-supervised transfer；candidate if sample/grid support |
| inverted Transformer | iTransformer, ICLR 2024, [paper](https://proceedings.iclr.cc/paper_files/paper/2024/file/2ea18fdc667e0ef2ad82b2b4d65147ad-Paper-Conference.pdf), [code](https://github.com/thuml/iTransformer) | multivariate correlation baseline；not assumed superior on small fleet |
| hierarchical interpolation | N-HiTS, AAAI 2023, [paper](https://ojs.aaai.org/index.php/AAAI/article/view/25854), [code](https://github.com/Nixtla/neuralforecast) | strong multi-horizon neural baseline |
| TSFM | Chronos, TMLR 2024, [paper](https://www.amazon.science/publications/chronos-learning-the-language-of-time-series), [code](https://github.com/amazon-science/chronos-forecasting) | zero-shot probabilistic baseline；must disclose possible pretraining contamination |
| TSFM | TimesFM, ICML 2024, [official](https://research.google/blog/a-decoder-only-foundation-model-for-time-series-forecasting/), [code](https://github.com/google-research/timesfm) | modern general forecaster；version/quantile support hash-pin |
| TSFM | Moirai/Moirai 2.0, [ICML 2024 paper](https://arxiv.org/abs/2402.02592), [2.0](https://arxiv.org/abs/2511.11698), [code](https://github.com/SalesforceAIResearch/uni2ts) | quantile/universal forecasting baseline；small-data zero-shot candidate |
| benchmark hygiene | GIFT-Eval, [OpenReview](https://openreview.net/forum?id=9EBSEkFSje), [code](https://github.com/SalesforceAIResearch/gift-eval) | demonstrates non-leaking pretrain/train/test separation and diverse baseline reporting; does not contain capacitor validation |
| uncertainty | Conformalized Quantile Regression, [NeurIPS 2019](https://papers.neurips.cc/paper_files/paper/2019/hash/5103c3584b063c431bd1268e9b5e76fb-Abstract.html); Adaptive Conformal Inference, [NeurIPS 2021](https://proceedings.neurips.cc/paper/2021/hash/0d441de75945e5acbc865406fc9a2559-Abstract.html) | fold-local/calibration-only interval wrappers and coverage diagnostics are necessary |

## 4. LLM/Agent forecasting literature

| Closest work | Direct overlap | Remaining difference relevant to this proposal |
|---|---|---|
| Time-LLM, ICLR 2024, [arXiv](https://arxiv.org/abs/2310.01728) | reprograms an LLM for forecasting | LLM-based numerical forecast不是新方向 |
| Tan et al., *Are Language Models Actually Useful for TS Forecasting?*, NeurIPS 2024, [paper](https://proceedings.neurips.cc/paper_files/paper/2024/hash/6ed5bf446f59e2c6646d23058c86424b-Abstract-Conference.html) | ablations found removing/replacing LLM often preserved or improved performance | 强制 `LLM-free`、matched compute和simple baselines |
| Park et al., *Small Noise Can Break Large Models*, ACL 2025, [paper](https://aclanthology.org/2025.acl-short.71/) | zero-shot LLM sensitivity与simple-model underperformance | direct Agent必须有noise/failure tests；不能假设大模型直接外推强 |
| MAFS, NeurIPS 2025, [OpenReview](https://openreview.net/forum?id=Uon41HfqR3) | subtask-specialized agents、communication topologies、voting、11 benchmarks | “specialized multi-Agent forecasting/topology”新颖性低 |
| FLAIRR-TS, EMNLP Findings 2025, [paper](https://aclanthology.org/2025.findings-emnlp.834/) | forecaster/refiner/retrieval agents、iterative prompt optimization | 本项目差异应是held-out label barrier；不能使用recent true errors作confirmatory refinement |
| MoiraiAgent, Salesforce 2026, [official](https://www.salesforce.com/blog/moiraiagent/), [code](https://github.com/SalesforceAIResearch/uni2ts/tree/main/project/moirai-agent) | Agent选择Chronos/TimesFM/TiRex等experts，使用history/features/CV errors | dynamic expert selection/LLM+TSFM已直接存在 |
| CastFlow, 2026, [arXiv](https://arxiv.org/abs/2604.27840) | planning/action/forecast/reflection、memory、tools、ensemble anchor、general+numerical LLM | role-specialized hybrid Agent不是新机制；本项目只能强调all-arm whole-device seal |
| KairosAgent, 2026, [arXiv](https://arxiv.org/abs/2605.30002) | LLM reasoner + TSFM forecaster、dynamic tools、fusion与RL | generic LLM+specialized-model hybrid新颖性低 |
| Last Mile, 2026, [arXiv](https://arxiv.org/abs/2606.02497) | backbone之上的LLM workspace/tool/revision/reflection，强调auditable constraints | auditable forecast revision也已有；其case-study setting与whole-device replay不同 |
| CastFSR, 2026-08, [arXiv](https://arxiv.org/abs/2608.03031) | fast forecaster selection、slow contextual reasoning、reflection | fast/slow/reflection candidate不新 |
| REATS, 2026-08, [arXiv](https://arxiv.org/abs/2608.10149) | LLM adaptive ensemble router over text+numeric features | typed routing/ensemble作为独立claim不新 |
| single-vs-multi matched budget, 2026, [arXiv](https://arxiv.org/abs/2604.02460) | matched-token multi-hop reasoning中single Agent常持平或胜multi-Agent | 不是forecasting直接结果，但强化同调用/同信息control必要性 |

## 5. Agentic PHM and provenance near priors

| Work | Overlap | Novelty risk |
|---|---|---|
| PHMForge v3, 2026-08, [arXiv](https://arxiv.org/abs/2604.01532), [code](https://github.com/DeveloperMindset123/PHMForge-A-Scenario-Driven-Agentic-Benchmark-for-Industrial-Asset-Lifecycle-Maintenance) | v3包含99个PHM scenarios、真实电池aging、17 tools、6 numerical/TSFM RUL predictors、leave-one-battery-out observation-window评测、统一schema、failure metadata、pass-all-3、execution-trace分解、leakage controls与checkpoint SHA-256 fingerprint | **最强近邻，重叠高于初步判断**；本项目必须证明其差异是common-planned-key whole-device longitudinal policy comparison、no-retry ITT、joint forecast calibration与all-arm label barrier，而非重复PHM tool-use benchmark |
| PROV-AGENT, 2025, [arXiv](https://arxiv.org/abs/2508.02866) | W3C PROV/MCP agent interaction provenance | typed provenance/hash chain本身不能称独立创新 |

## 6. Baseline adequacy verdict

Canonical N0当前的六 experts/五 fusions覆盖last/drift/local/log-linear/KF/ridge，但不足以支撑 2026 年“strong numerical/specialized/modern forecasting champion”这一宽泛描述。seal前至少必须把以下 **proposal** 交用户决定：

### `N0+` finite candidate-pool proposal

1. **Classical**：AutoETS/AutoARIMA/Theta（或数据频率不支持时机械NA）；
2. **Online state estimation**：RLS/RELS与现有causal KF；若endpoint/likelihood可定义，加 particle filter；
3. **Small-data ML**：gradient boosting + elastic net，使用outer-training-only early/trend features；
4. **Dedicated SC sequence/RUL**：S4/RevIN；PINN-LSTM只在方程/输入可复现时；
5. **Modern learned forecasters**：DLinear、N-HiTS，PatchTST或iTransformer至少一个；
6. **TSFM**：Chronos、TimesFM、Moirai 2.0至少各做冻结版本的zero-shot eligibility/probe，最终训练侧选择或全部报告；
7. **Intervals**：quantile model或fold-local conformal wrapper，统一WIS/coverage。

精度第一意味着不能仅因模型较大或工程麻烦而删除；但113-unit小样本也意味着所有训练、feature、hyperparameter与calibration都必须在outer fold内，且zero-shot TSFM需要pretraining contamination disclosure。

### Arm-set protection

本审查 **不自动新增 confirmatory arm**，也不运行模型。默认提案是扩充 training-side `N0` candidate pool，并在每 fold只用nested inner whole-unit CV选择 `N0+ champion=FALLBACK`，同时报告所有 constituent training/held-out scores。因为这改变 canonical N0 pool，必须在任何 result可见前获得新的明确人工批准与hash-pinned addendum。若用户要求某模型成为独立confirmatory arm，则还需另行批准 arm-set变更；当前 `11∪{ARCH1}` 不变。

如果不批准 modern additions，论文必须收窄为“relative to the preregistered six-expert pool”，不能写“strongest modern numerical/TSFM baseline”。

## 7. Architecture comparison adequacy

| Architecture class | Frozen representative | Necessary control | Claim ceiling |
|---|---|---|---|
| single Agent | canonical one-call arms | N0/ENUM/same-info anchors | direct or hybrid local effect |
| fixed multi-call | D4-H/D4-X | constituent scores + same aggregator | repeat/roster effect |
| hierarchical | A01 candidate | exact D4-H match or approved sham | full-package only without match |
| parallel debate | A02 candidate | exact D4-X match or approved sham | bounded adjudication package |
| dynamic routing hybrid | A03 candidate | exact four-call hybrid control/sham | routing causality prohibited if no match |
| fold-local selector | ARCH1 policy | all candidates training-only; outer no selection | selection-policy effect, not three topology effects |

## 8. Novelty Check Report

### Core claims

1. 新的 LLM Agent、hierarchy/debate/routing或LLM+TSFM forecasting机制 — **LOW**；CastFlow、KairosAgent、MAFS、MoiraiAgent、CastFSR、REATS已直接覆盖。
2. 电容PHM中的广泛architecture-control matched study — **MEDIUM-LOW currently**；PHMForge很近，且本方案confirmatory只评fold-selected ARCH1。
3. whole-capacitor causal replay + all-arm generation barrier + one joint unseal — **MEDIUM as a combined evaluation contract**；检索未找到精确同构，但whole-unit/LOO、rolling-origin、preregistration、hidden-label与joint multiplicity均有已知先例，“未找到”不证明priority。
4. hash artifacts + physical no-retry + late non-overwrite + common ITT failure denominator — **MEDIUM-LOW**；provenance、deterministic schema/evaluator、failure decomposition、pass-all-k与fault stress已有，精确组合较严格但不是独立机制创新。
5. unit-paired calibration/failure/deadline/multiplicity joint protocol — **MEDIUM**；组成方法已知，组合可能有方法学价值。

### Overall assessment

- **Score**：`5.0/10`
- **Recommendation**：`PROCEED WITH CAUTION`
- **Defensible differentiator**：把 numerical forecasting policy 本身放进 all-arm、whole-device、prediction-before-reveal、no-retry、failure-inclusive的审计级确认性协议；不是发明新Agent topology。
- **Strongest objection**：PHMForge v3已经在真实储能退化数据上提供whole-cell LOO、numerical/foundation predictors、统一schema、deterministic evaluator、execution traces、failure/leakage/hash审计；CastFlow/Kairos/MAFS等覆盖架构机制。剩余贡献可能只是复杂seal应用到小fleet，且若无exact `C_k`、N0+、独立单位功效与有效外域，无法支持architecture claim。回顾性公开数据也只能证明程序性non-use；若没有独立控制的service/access separation，不能声称研究者字面blind。

建议定位：

> We evaluate numerical forecasting policies—not tool-use question answering—under a preregistered, all-arm, whole-device causal rolling replay. Held-out suffixes, labels, and losses remain inaccessible until every admitted attempt closes; failures stay in a common intention-to-treat denominator; physical retries and late overwrites are forbidden; and topology claims require information-, backbone-, call-, ceiling-, deadline-, and fallback-matched controls.

## 9. Falsifiable research hypotheses after gates

- **H-direct**：D1-RAW是否在matched planned keys上胜N0；negative合法。
- **H-hybrid**：ACT1/A03是否胜N0、same-info direct与ENUM；否则LLM controller/routing无增量。
- **H-multi**：ARCH1是否同时胜N0与exact C4，并通过WIS/failure/deadline；否则不作协作优势claim。
- **H-TSFM**：zero-shot TSFM是否在whole-capacitor cross-condition replay胜small-data statistical/ML；不预设大模型更好。
- **H-audit**：常见success-only/retry/window split是否相对sealed ITT改变结论方向；只能在预注册shadow分析中测试，不能污染主结果。

## 10. P6 update plan

在最终论文前重复：

1. 搜索 submission前最近6个月的Agent forecasting、PHM benchmark与SC RUL；
2. 对全部 bibliography做 DOI/title/author/venue verification；
3. 对每个“first/novel/SOTA/strongest”逐条查新，否则删除；
4. 核验所比较模型的release/version/pretraining数据与官方代码；
5. 用fresh reviewer做 zero-context claim audit；
6. 任何新近邻只收窄claim，不能解封后新增arm救结果。

## 11. Current decision

文献/adequacy审查已完成为 **提案阶段**，结论不是“baseline PASS”，而是 `BASELINE_ADDITION_DECISION_REQUIRED_BEFORE_SEAL`。Ren仍blocked，故不能实施 `N0+`、做power或调用API。
