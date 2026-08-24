{
  "review_independence": "same-family",
  "acceptance_status": "provisional",
  "claims": [
    {
      "id": "A",
      "novelty": "MEDIUM",
      "closest_works": [
        {
          "title": "Analysis of Electrolytic Capacitor Degradation under Electrical Overstress for Prognostic Studies",
          "year": 2015,
          "url": "https://doi.org/10.36001/phmconf.2015.v7i1.2713",
          "overlap": "同一类 NASA 电气过应力实验已比较离线 EIS 与在线充放电瞬态时间常数，报告趋势对应、量级偏差、晚启动及硬件和校准影响。"
        },
        {
          "title": "A Data-Driven Condition Monitoring Method for Capacitor in Modular Multilevel Converter",
          "year": 2024,
          "url": "https://arxiv.org/abs/2404.13399",
          "overlap": "从在线电压、电流和开关波形同时估计 C 与 ESR，并以电容电压方程闭环校正；已覆盖在线瞬态到双健康参数估计。"
        },
        {
          "title": "Online Condition Monitoring for DC-Link Capacitors of Three-Level NPC Converters Using Noninvasive Signal Injection",
          "year": 2024,
          "url": "https://doi.org/10.1016/j.compeleceng.2024.109577",
          "overlap": "利用注入瞬态和小波分解在线同时估计 C、ESR，并用于退化跟踪和故障检测。"
        },
        {
          "title": "Towards A Model-based Prognostics Methodology for Electrolytic Capacitors: A Case Study Based on Electrical Overstress Accelerated Aging",
          "year": 2012,
          "url": "https://doaj.org/article/1bf4b32c80d844429674df78650a95b4",
          "overlap": "把 EIS 获得的电容退化状态、Kalman 更新、阈值穿越与 RUL 预测连接起来，覆盖桥的下游半段。"
        }
      ],
      "delta": "检索中未发现一项工作同时完成：严格按可用时刻配对 EIS 与在线瞬态、显式分离器件状态和仪器/电路/温度偏差、输出完整概率测量分布，并把该测量后验传播到删失感知的 RUL。真正增量只能是这一可识别、可校准且端到端传播的不确定性层，而不是瞬态与 EIS 有关、在线估计 C/ESR 或从健康状态算 RUL。",
      "reviewer_killer_objection": "所谓“因果桥”可能只是 Renwick 2015 的经验对应关系后接 Celaya 的 KF/RUL；仅使用过去数据是时间因果性，不是因果推断。若不能在配对观测上辨识偏差，并证明桥相对直接瞬态估计在未见电容和未见电压上改善下游 proper loss，该模块就是标准误差变量模型的领域拼接。",
      "allowed_claim": "提出并检验一个时间因果的概率校准层，用于量化离线 EIS 与在线瞬态之间的系统偏差和观测不确定性，并将其传播至 C/ESR 阈值穿越与 RUL；不得宣称首次发现 EIS—瞬态关系、首次在线估计 C/ESR 或一般意义上的因果识别。"
    },
    {
      "id": "B",
      "novelty": "LOW",
      "closest_works": [
        {
          "title": "Degradation Modeling and RUL Prediction Using Wiener Process Subject to Multiple Change Points and Unit Heterogeneity",
          "year": 2018,
          "url": "https://doi.org/10.1016/j.ress.2018.04.005",
          "overlap": "已同时覆盖多变化点、器件异质性、完全 Bayesian 建模、在线递归个体更新和 RUL 分布。"
        },
        {
          "title": "Bivariate and Two-Phase Degradation Modeling and Reliability Analysis with Random Effects",
          "year": 2024,
          "url": "https://doi.org/10.2298/TSCI2403295S",
          "overlap": "建立双变量、两阶段 Wiener 随机效应模型，用变化点识别、Copula 相关性和首次穿越计算寿命/RUL。"
        },
        {
          "title": "A Remaining Useful Life Prediction Method of Aluminum Electrolytic Capacitor with Adaptive Degradation Model Selection",
          "year": 2024,
          "url": "https://doi.org/10.1016/j.microrel.2024.115509",
          "overlap": "电解电容专用的两阶段 Wiener、多退化模型、顺序 Bayesian 更新及基于历史 RUL 相似度的在线模型选择。"
        },
        {
          "title": "A Data-Driven Condition Monitoring Method for Capacitor in Modular Multilevel Converter",
          "year": 2024,
          "url": "https://arxiv.org/abs/2404.13399",
          "overlap": "说明 C 与 ESR 应作为不同速度、不同 EOL 的联合健康量监测，压低“双状态”本身的新颖性。"
        }
      ],
      "delta": "可保留的窄增量是把 C 与 ESR 作为相关潜在状态，在电压和器件层级随机效应下进行在线联合滤波，并允许慢/快阶段切换及局部电容量回升；但多变量、随机效应、阶段切换、在线 Bayesian 更新和首次穿越均已有直接先例，组合本身缺乏方法级新意。",
      "reviewer_killer_objection": "Wen 2018、Sun 2024 和 Chen 2024 的并集已经覆盖层级异质、多阶段/变化点、双变量退化、在线更新和 RUL。把两个质量特征改名为 C/ESR 并换成 switching state-space，不足以构成新模型。",
      "allowed_claim": "作为电容领域的联合状态建模实例，比较单状态与切换状态在 C/ESR 非单调、跨电压回放中的适用边界；不得宣称层级随机效应、双变量退化或切换 RUL 建模本身新颖。"
    },
    {
      "id": "C",
      "novelty": "LOW",
      "closest_works": [
        {
          "title": "Online Aggregation of Probability Forecasts with Confidence",
          "year": 2022,
          "url": "https://doi.org/10.1016/j.patcog.2021.108193",
          "overlap": "以 CRPS 这一 proper score 在线聚合概率专家，支持平滑置信度和 specialized/sleeping experts；本质上已覆盖仅依赖过去损失的软专家聚合。"
        },
        {
          "title": "Kairosis: A Method for Dynamical Probability Forecast Aggregation Informed by Bayesian Change-Point Detection",
          "year": 2025,
          "url": "https://doi.org/10.1016/j.ijforecast.2025.03.001",
          "overlap": "使用 Bayesian 变化点概率动态重加权近期概率预测，直接覆盖变化点感知的概率聚合。"
        },
        {
          "title": "TimeRouter: Efficient and Adaptive Routing of Time-Series Foundation Models",
          "year": 2026,
          "url": "https://arxiv.org/abs/2606.11625",
          "overlap": "针对异构 TSFM 池提供轻量路由头、selective gate、拒绝和 ensemble fallback，且公开实现。"
        },
        {
          "title": "TimeRouter Official Code",
          "year": 2026,
          "url": "https://github.com/UConn-DSIS/TimeRouter",
          "overlap": "公开代码直接实现 TSFM 专家池的自适应选择、选择性门控和融合回退。"
        }
      ],
      "delta": "可能保留的工程差异是为每个目标×horizon 单独维护延迟反馈账本，只有相应未来标签到达后才更新 proper loss，并把变化概率、上下文长度和模态可用性同时用于门控。但这些是已知在线专家聚合、变化点重加权、选择性路由和多步预测记账的组合。",
      "reviewer_killer_objection": "TimeRouter 已覆盖异构 TSFM 路由、拒绝与回退；Kairosis 覆盖变化点权重；V’yugin 与 Trunov 覆盖 proper-loss 概率专家在线聚合。“只用过去”和按 horizon 分账是正确实现要求，不是算法创新。",
      "allowed_claim": "实现并严格评估一个面向电容退化、带延迟标签的目标×horizon 在线专家路由器，重点报告何时拒绝复杂专家及其失败边界；不得宣称动态专家路由、变化点聚合、CRPS 加权或拒绝机制本身新颖。"
    },
    {
      "id": "D",
      "novelty": "LOW",
      "closest_works": [
        {
          "title": "Adaptive Remaining Useful Life Prediction for Film Capacitors in DC-Link Applications Using Degradation and Failure Data",
          "year": 2025,
          "url": "https://doi.org/10.1109/TPEL.2025.3621772",
          "overlap": "电容领域已用混合效应退化模型、比例风险、工况协变量和 Bayesian 在线更新联合退化与失效数据，输出概率 RUL。"
        },
        {
          "title": "A Data-Driven Method for Anomaly Detection and Aging Model Parameter Estimation of Capacitors Based on Condition Monitoring",
          "year": 2022,
          "url": "https://doi.org/10.1016/j.microrel.2022.114646",
          "overlap": "已联合利用 C 损失与 ESR，通过 Mahalanobis 距离检测突变异常，并以 Bayesian 线性回归在线更新老化模型。"
        },
        {
          "title": "Doubly Robust Conformalized Survival Analysis with Right-Censored Data",
          "year": 2025,
          "url": "https://arxiv.org/abs/2412.09729",
          "overlap": "ICML 2025 工作提供右删失生存时间的加权共形预测和双重稳健性质，直接覆盖删失感知校准。"
        },
        {
          "title": "Doubly Robust Conformalized Survival Analysis Official Code",
          "year": 2025,
          "url": "https://github.com/msesia/conformal_survival",
          "overlap": "公开实现右删失条件下的生存共形校准。"
        },
        {
          "title": "Conformalized Survival Distributions: A Generic Post-Process to Increase Calibration",
          "year": 2024,
          "url": "https://arxiv.org/abs/2405.07374",
          "overlap": "为个体生存分布提供通用共形后处理，压低“给 RUL/生存曲线做校准”的独立新颖性。"
        }
      ],
      "delta": "可保留的差异是用同一个 C/ESR 路径后验一致地产生 SOH 分量、区间/右删失 RUL、生存曲线、阈值风险和创新异常风险，并按真实标签延迟在线校准。该一致性接口和电容标签语义有实用价值，但不构成新的联合退化—生存或共形理论。",
      "reviewer_killer_objection": "Gao 2025 已完成电容退化—生存—Bayesian 在线更新，已有电容 C/ESR 异常检测和成熟的删失共形方法。增加 SOH、异常和多个输出头只是系统集成；在六只电容上，共形交换性和有效独立校准样本还可能根本不成立。",
      "allowed_claim": "给出一个标签语义一致、显式处理区间删失和右删失的联合输出与评测接口，并验证不同校准方法在极小电容样本下的适用边界；不得宣称联合退化—生存、在线 Bayesian 更新、异常检测或共形生存本身新颖。"
    },
    {
      "id": "E",
      "novelty": "LOW",
      "closest_works": [
        {
          "title": "AgentEval: DAG-Structured Step-Level Evaluation for Agentic Workflows with Error Propagation Tracking",
          "year": 2026,
          "url": "https://arxiv.org/abs/2604.23581",
          "overlap": "已把 Agent 执行形式化为带类型质量指标、依赖边、错误传播和根因定位的评测 DAG，直接覆盖类型化图和传播审计核心。"
        },
        {
          "title": "Curie: Toward Rigorous and Automated Scientific Experimentation with AI Agents",
          "year": 2025,
          "url": "https://arxiv.org/abs/2502.16069",
          "overlap": "以域内和跨 Agent 严谨性模块、实验知识模块及可执行实验评测约束自动科研流程；公开实现。"
        },
        {
          "title": "MLE-bench: Evaluating Machine Learning Agents on Machine Learning Engineering",
          "year": 2024,
          "url": "https://arxiv.org/abs/2410.07095",
          "overlap": "以冻结任务、确定性评分、统一资源预算、重复种子和污染风险评估 ML 工程 Agent，并公开基准代码。"
        },
        {
          "title": "MLAgentBench",
          "year": 2024,
          "url": "https://github.com/snap-stanford/MLAgentBench",
          "overlap": "公开代码把 Agent 可见环境与隐藏 prepare/eval 脚本隔离，覆盖冻结 Eval 和隐藏裁判模式。"
        },
        {
          "title": "From Agent Traces to Trust: Evidence Tracing and Execution Provenance in LLM Agents",
          "year": 2026,
          "url": "https://arxiv.org/abs/2606.04990",
          "overlap": "系统整理执行图、证据和 claim provenance、信息流/污点、访问控制、运行时防护、恢复与治理要求。"
        }
      ],
      "delta": "真正可发表的差异只能是面向电容 PHM 的可执行治理基准：把字段级血缘和权限与 LOCO、LOVO、rolling-origin、隐藏 Eval、植入泄漏故障及冠军—挑战者影子门统一起来，并以错误晋级率、阻断率、最终冻结数值误差和成本衡量。其价值属于领域协议和证据工件，不是一般 Agent 图或 MLOps 模式创新。",
      "reviewer_killer_objection": "AgentEval 已有类型化评测 DAG，Curie 已有严谨实验 Agent，MLE-bench/MLAgentBench 已有隐藏 Eval，provenance、taint、champion–challenger 和 shadow deployment 都是既有治理模式；LOCO/LOVO/rolling 也是标准评测。没有公开故障注入、确定性裁判和跨拓扑对照时，这只是架构图。",
      "allowed_claim": "发布一个可执行的电容预测 Agent 治理与泄漏审计基准，量化类型化证据边是否减少无效候选和错误晋级；不得宣称类型化 DAG、隐藏 Eval、数据血缘、影子部署或人类上线门本身新颖。"
    }
  ],
  "overall_recommendation": "PROCEED_WITH_MAJOR_REPOSITIONING：不应把 TRACE-Cap 作为五项均新的统一算法投稿。仅 A 保留中等方法潜力，但必须以配对测量、偏差可识别性和端到端不确定性传播为核心；B、C、D 应降为已知方法的严格组合与强基线；E 应定位为可执行领域评测、治理协议和可能的负结果贡献。",
  "positioning": "最稳妥的定位是“测量科学贡献 + 严格电容 PHM 基准”。主论文只主张：在离线 EIS 稀疏、在线瞬态可用且存在系统测量偏差时，建立概率校准桥并检查其对未见电容/电压下 C、ESR 与删失 RUL 的增量。路由、切换状态、联合生存、共形和 Agent 图均明确引用为现有组件。若 A 无法在 LOCO/LOVO 中提供可重复增量，则转为数据审计、统一标签、严格回放、公开代码和负结果论文。",
  "search_queries": {
    "A": [
      "site:arxiv.org capacitor EIS transient online estimation capacitance ESR prognostics 2024 2025 2026",
      "electrolytic capacitor EIS charging transient probabilistic measurement model RUL prognostics",
      "online capacitance ESR estimation converter waveform capacitor health monitoring 2024 2025",
      "GitHub capacitor EIS transient capacitance ESR RUL online monitoring"
    ],
    "B": [
      "site:arxiv.org multivariate degradation switching state-space remaining useful life hierarchical random effects 2024 2025 2026",
      "capacitor capacitance ESR joint state space switching regime online RUL 2024 2025",
      "two-stage degradation model capacitor RUL adaptive model selection 2024 Wiener",
      "GitHub switching state space multivariate degradation RUL capacitor ESR capacitance"
    ],
    "C": [
      "site:arxiv.org online time series forecast expert routing target horizon prequential proper loss changepoint 2024 2025 2026",
      "heterogeneous forecasting experts dynamic ensemble selection horizon-specific online aggregation changepoint abstention",
      "time series foundation model router abstain expert selection per horizon 2025 GitHub",
      "prequential scoring rule online ensemble forecasting change point Hedge experts code"
    ],
    "D": [
      "capacitor joint degradation survival Bayesian online update RUL capacitance ESR 2024 2025 2026",
      "site:arxiv.org censored RUL survival conformal online calibration anomaly joint degradation 2024 2025",
      "multivariate degradation C ESR SOH RUL joint model right censoring capacitor",
      "GitHub conformal survival RUL online calibration censored prognostics"
    ],
    "E": [
      "site:arxiv.org AI agent machine learning engineering evidence graph frozen evaluation benchmark leakage lineage shadow deployment 2024 2025 2026",
      "multi-agent automated machine learning typed DAG evidence provenance evaluation leakage benchmark 2025",
      "agentic ML engineering frozen eval holdout rolling evaluation champion challenger shadow deployment GitHub",
      "LLM research agent evidence graph provenance typed DAG reproducibility 2025 2026 arxiv"
    ]
  },
  "limitations": [
    "方案边界只从指定的 EVIDENCE_LEDGER.md、FROZEN_EVAL_PROTOCOL.md 和 IDEA_CANDIDATES.md 提取；未使用作者的其他解释。",
    "检索截至 2026-07-29，覆盖 arXiv、正式论文页面和公开 GitHub 代码；2026 年预印本可能尚未同行评审，最新条目也可能尚未被索引。",
    "部分正式论文只能核验题录、摘要、开放预印本或可抓取正文片段，未对所有付费全文逐页复核。",
    "这不是系统专利/FTO 检索，也无法证明绝对不存在未公开代码、学位论文、非英语论文或未索引工作。",
    "对 A 和 B 的直接电容近邻未检索到官方公开实现；“未检索到”不能等同于“没有代码”。C、D、E 则核验到 TimeRouter、conformal_survival、MLE-bench、MLAgentBench 和 Curie 等公开实现。",
    "额外的同模型族二次 reviewer 因团队线程上限未能启动；当前核验员本身是零上下文 fresh 子线程，因此独立性仍标记为 same-family，结论保持 provisional。",
    "ES10/ES12/ES14 大包尚未完成字段和事件配对审计，A、B 的可识别性与可执行性仍可能因元数据不足而失败。",
    "未给出任何预测性能主观评分；所有性能主张必须由冻结 LOCO、LOVO、rolling-origin 和 shadow 协议产生。"
  ]
}
