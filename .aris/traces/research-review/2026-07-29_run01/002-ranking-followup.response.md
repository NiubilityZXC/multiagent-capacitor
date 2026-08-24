{
  "headline_rejection_memo": "该计划把尚未完成 schema、器件身份和终止原因审计、独立器件极少的加速过压数据，扩张为测量桥、切换状态、动态专家、共形校准与多 Agent 全栈。主 RUL 可能因区间/右删失而不可识别，三电压也只支持应力电压迁移；在线 RUL 校准的标签时钟尚未闭合，核心机制又都有强近邻。若不先审计数据、缩成单一机制并锁定可识别估计量，本研究最多支持严谨基准或负结果，不能支持通用在线 PHM 系统。",
  "findings": [
    {
      "id": "F01",
      "severity": "CRITICAL",
      "claim": "Benchmark L 尚不是已定义的数值基准：独立器件数、模态配对、事件映射和终止结局均未核验。",
      "evidence_file_section": "EVIDENCE_LEDGER.md §1、§1.1、§6；FROZEN_EVAL_PROTOCOL.md §1.2、§11",
      "why_it_matters": "所有复杂模型、LOVO、删失分析和功效判断都依赖这些未知量。远程文件大小和中央目录不能证明数据支持拟议实验。",
      "minimum_fix": "正式建模前发布可机器复建的逐器件审计清单，包含哈希、身份、批次/板卡、电压、时间轴、模态事件、缺失、配对规则、阈值穿越区间、终止原因和重复关系，并设置明确的模型启用门。",
      "decisive_experiment": "由独立脚本从原始 MAT 重建上述清单；若无法得到稳定器件映射、已知终止状态和足够的配对事件，则停止 C1/C3/RUL 主分析，仅保留可核验子集的描述性基准。"
    },
    {
      "id": "F02",
      "severity": "CRITICAL",
      "claim": "有效样本量按物理电容计，而当前唯一完全核验的 Benchmark S 只有 6 个独立单位；Benchmark L 的单位数仍未知，无法支撑多层随机效应、切换状态、动态路由、共形分层和五种 Agent 架构。",
      "evidence_file_section": "EVIDENCE_LEDGER.md §1、§6；FROZEN_EVAL_PROTOCOL.md §1.1、§1.2、§7；IDEA_CANDIDATES.md §2 C1、§3",
      "why_it_matters": "窗口、频点、预测原点和随机种子都不能增加独立样本量。六簇 bootstrap、多个候选的 Holm 校正和三折 LOVO 对合理效应的区分力极弱，复杂模型的方差分量也可能不可识别。",
      "minimum_fix": "在数据审计后，以实际单位数、事件率、删失率和相关结构做设计仿真；预先定义可接受的效应置信区间宽度。只保留功效足以区分的一个主要模型对比，其余均标为探索性。",
      "decisive_experiment": "按真实采样结构模拟零效应和最小有意义效应，运行完整嵌套评测并估计选择错误率、覆盖率和置信区间宽度；若无法稳定区分该效应，则不得提出模型优越性或架构排序。"
    },
    {
      "id": "F03",
      "severity": "CRITICAL",
      "claim": "物理 EOL、点 RUL 和生存分布目前不一定可识别，且以首次观测越界计算点误差与“真实 EOL 为区间删失”的定义存在张力。",
      "evidence_file_section": "EVIDENCE_LEDGER.md §1.1(5)、§2.2、§5.2、§6；FROZEN_EVAL_PROTOCOL.md §2、§6.1",
      "why_it_matters": "未知终止原因可能是信息性删失；离散越界只给出区间，局部电容量回升又会使首次越界依赖测量噪声。IPCW、点 RUL MAE 和远期生存曲线不能在缺少事件及删失假设时自动成立。",
      "minimum_fix": "冻结可审计的结局判定表、C0/R0 来源、越界持续规则和时间尺度；主要使用区间删失似然及相容评分。除非明确把目标改称“首次观测越界时间”，否则不得把区间端点或中点当物理 EOL。",
      "decisive_experiment": "报告每种 EOL 定义下的事件数、右删失数、未知终止数和区间宽度，并用区间左右端点及删失机制敏感性分析重排模型；若结论随合理边界改变，则把 RUL 降为探索性，仅保留 C/ESR 预测。"
    },
    {
      "id": "F04",
      "severity": "CRITICAL",
      "claim": "回放协议正确处理了固定 h 的 C/ESR 标签延迟，但没有闭合 RUL/生存校准的标签时钟。",
      "evidence_file_section": "FROZEN_EVAL_PROTOCOL.md §2.2、§3、§4、§8；IDEA_CANDIDATES.md §2 C1",
      "why_it_matters": "某预测原点的真实 RUL 通常到 EOL 或删失时才揭示，而非在 t+h 揭示；届时同一器件已无可用寿命供在线校准。若使用该器件的最终 EOL 回填早期残差，或使用同折其他 Eval 器件更新校准器，就会产生回顾性或跨单位泄漏。",
      "minimum_fix": "为 C/ESR、穿越风险和 RUL 分别定义 append-only 时间线。RUL 校准器原则上只由内层训练单位拟合；若研究跨器件序贯部署，必须预注册器件顺序并把它定义为不同于 LOCO 的估计量。",
      "decisive_experiment": "执行时间戳不变量测试：延迟、删除或置换所有尚未揭示的未来/EOL 标签，标签揭示前的预测哈希必须完全相同；另比较固定校准与测试期更新，任何无法由合法已到达标签解释的差异均判泄漏。"
    },
    {
      "id": "F05",
      "severity": "MAJOR",
      "claim": "10/12/14 V 的 LOVO 只检验同一加速电气应力实验内的留一电压迁移，不等于跨真实工况或跨应用泛化。",
      "evidence_file_section": "EVIDENCE_LEDGER.md §2.2、§6(3-4)；FROZEN_EVAL_PROTOCOL.md §1.2",
      "why_it_matters": "电压可能与板卡、批次、时间、仪器和温度共同变化，而且只有三个应力水平。LOVO 无法分离电压效应与这些群组因素，也没有覆盖真实负载、环境或服役时间。",
      "minimum_fix": "所有表述改为“leave-one accelerated-stress voltage transfer”。只有在独立批次、板卡或真实环境留出上复现后，才使用“跨工况”。",
      "decisive_experiment": "在审计可用时执行电压与独立批次/板卡的交叉留出，并加入环境和仪器协变量；若没有独立批次或外部运行数据，则该更强主张直接不成立。"
    },
    {
      "id": "F06",
      "severity": "MAJOR",
      "claim": "所谓“因果 EIS→瞬态桥”目前更像观测映射：EIS 需移除器件、瞬态约 1100 h 后才开始，且两者量级和校准条件不同。",
      "evidence_file_section": "EVIDENCE_LEDGER.md §2.2；IDEA_CANDIDATES.md §2 C1、C3",
      "why_it_matters": "缺少早期重叠、同步测量和温度/仪器状态时，真实损伤、时间趋势与测量偏差不可分；预测相关性不能支撑因果措辞。",
      "minimum_fix": "先冻结配对容差、可用时刻和测量协变量，把方法称为带测量误差的概率观测桥；没有干预或可识别假设时删除“因果”。",
      "decisive_experiment": "在完全留出的器件和电压上，仅用当时可获得的瞬态预测同时间窗 EIS 参数，并比较直接映射、时间趋势负控和完整测量模型；若优势在时间置换或板卡负控下仍存在，则说明模型主要利用混杂。"
    },
    {
      "id": "F07",
      "severity": "MAJOR",
      "claim": "C1 将测量桥、层级状态、阶段切换、残差专家、动态路由、共形校准和 Agent 治理合成一个全栈故事，在当前样本量下无法归因。",
      "evidence_file_section": "IDEA_CANDIDATES.md §1、§2 C1；FROZEN_EVAL_PROTOCOL.md §5、§6、§7、§9",
      "why_it_matters": "“全系统胜过弱基线”不能说明哪个机制有效；逐组件搜索又引入大量选择自由度和多重比较。失败时也无法区分数据不足、组件错误或交互失效。",
      "minimum_fix": "主论文只保留一个科学机制和一个固定骨干；其余组件作为预注册的逐项挑战者或工程附录。每个组件必须有独立估计量、删除条件和成本报告。",
      "decisive_experiment": "在相同折、原点和骨干上做锁定顺序的 add-one/remove-one 对比，并与最佳单组件而非弱基线比较；若任何全栈收益不能由跨单位一致的单组件增量解释，则不得作系统机制主张。"
    },
    {
      "id": "F08",
      "severity": "MAJOR",
      "claim": "当前六个候选的核心机制均有强近邻，尚未形成可防守的方法学新颖性。",
      "evidence_file_section": "EVIDENCE_LEDGER.md §3；IDEA_CANDIDATES.md §2 C1-C6",
      "why_it_matters": "两阶段与在线模型选择、长短期残差、联合退化—生存、EIS/瞬态关联、RUL 共形、TSFM 应用和多 Agent 比较均已有先例；重新集成并不自动构成顶会方法贡献。",
      "minimum_fix": "建立逐机制 novelty table，明确公式、可识别假设或评测对象相对最近邻的唯一增量。若没有清晰增量，就把贡献限定为数据审计、统一协议、严格复现或负结果。",
      "decisive_experiment": "在同一标签、切分和预算下复现最强最近邻，并只加入拟议唯一机制；若增量对大多数留出单位不稳定，删除方法新颖性主张。"
    },
    {
      "id": "F09",
      "severity": "MAJOR",
      "claim": "Agent 图按设计不直接预测 C/ESR/RUL，因此其拓扑与最终预测精度之间没有直接可识别的因果链。",
      "evidence_file_section": "FROZEN_EVAL_PROTOCOL.md §9；IDEA_CANDIDATES.md §2 C1(H5)、C5、§4",
      "why_it_matters": "不同拓扑会改变候选数量、代码、人工干预和计算量；最终精度差异可能来自被选择的模型而非拓扑本身。单个电容基准也不能支持一般 Agent 架构结论。",
      "minimum_fix": "把 Agent 研究拆成独立 meta-eval，以缺陷阻断、有效补丁、误拒绝、恢复率和成本为主要结局；预测精度仅作为下游次要结局，并报告候选生成的中介路径。",
      "decisive_experiment": "在隐藏故障和自然任务上随机分配拓扑，使用相同基础模型、权限及多档资源上限，重复种子并由盲态确定性测试裁决；若多 Agent 在同成本下不优于 single，则采用 single。"
    },
    {
      "id": "F10",
      "severity": "MAJOR",
      "claim": "“Pareto + 词典序”仍留下过多分析者自由度：多个 EOL、目标、horizon、指标、覆盖率和未冻结的最坏工况界限共同决定晋级。",
      "evidence_file_section": "FROZEN_EVAL_PROTOCOL.md §2、§6.1、§7",
      "why_it_matters": "在小样本下，候选会在不同指标上互有胜负；若没有唯一主要对比、明确门限和平局规则，最终冠军容易被事后选择。",
      "minimum_fix": "冻结一个主要估计量、一个主要模型对比、候选资格规则、所有非劣界限、缺失/无事件处理和平局规则；其他指标只解释安全性或机制。",
      "decisive_experiment": "在解封真实结果前，用覆盖全部边界情形的模拟结果运行锁定分析程序；程序必须无人工判断地产生唯一结论或预定义的“无冠军”。"
    },
    {
      "id": "F11",
      "severity": "MAJOR",
      "claim": "协议承认查看外层结果会产生新版本，但没有提供可供新版本再次无偏检验的独立最终测试集。",
      "evidence_file_section": "FROZEN_EVAL_PROTOCOL.md §4(3-4)、§8(10)、§10",
      "why_it_matters": "在同一批极少器件上反复调试解析器、特征和模型，即使保留旧数字，也会让整体研究过程适应外层数据；“影子验证”若仍用同一历史流不能恢复独立性。",
      "minimum_fix": "在首次解封前冻结容器、分析脚本和主对比，由隔离评测者一次性运行；解封后的任何修改只能标为探索性，除非获得新的时间、批次或外部数据。",
      "decisive_experiment": "由未参与开发的评测执行者在隐藏清单上重跑最终容器，并核对提交前后的哈希；任何解封后变更都不得覆盖原预注册结论。"
    },
    {
      "id": "F12",
      "severity": "MAJOR",
      "claim": "公开复现与复用权尚未闭合：大包无 README 且未完整下载，第三方仓库虽声称 MIT 却无许可证文件。",
      "evidence_file_section": "EVIDENCE_LEDGER.md §1、§4.1、§4.2、§6；FROZEN_EVAL_PROTOCOL.md §11",
      "why_it_matters": "读者可能无法确认字段语义、稳定取得相同字节或合法复用解析代码；未经许可复制第三方实现会削弱可复现性和发布合规性。",
      "minimum_fix": "记录来源条款和获取日期；不复制无明确许可证代码，改用 clean-room 实现；发布下载器、哈希、对象树、标签构建器、环境锁、模型版本和最小 CPU 基线。若不可再分发数据，只发布可验证派生清单。",
      "decisive_experiment": "在全新环境中由独立复现者从公开来源下载、校验、解析、重建标签并运行最小 LOCO；任一步需要私有文件、人工字段猜测或无许可代码即视为公开复现未通过。"
    }
  ],
  "claims_matrix": [
    {
      "outcome": "Benchmark S",
      "allowed_claim": "六只 10 V 电容上的小样本回放、解析正确性、泄漏哨兵和描述性单位级比较。",
      "forbidden_claim": "大样本学习、深度模型泛化、跨工况或普遍电容寿命结论。"
    },
    {
      "outcome": "Benchmark L",
      "allowed_claim": "完成全量审计后，对公开加速过压 EIS/瞬态数据进行可复核基准评测。",
      "forbidden_claim": "审计前声称固定样本量、可靠模态配对、明确 EOL 或代表真实运行分布。"
    },
    {
      "outcome": "RUL与生存",
      "allowed_claim": "在终止原因和删失类型可核验、事件数满足预设精度门时，对观测支持范围内的区间删失/右删失结局建模。",
      "forbidden_claim": "把首次离散越界当精确物理 EOL、把文件末尾当 RUL=0，或外推真实服役寿命。"
    },
    {
      "outcome": "LOVO",
      "allowed_claim": "留一加速应力电压迁移。",
      "forbidden_claim": "跨真实工况、跨应用、跨环境或无混杂的电压因果泛化。"
    },
    {
      "outcome": "EIS—瞬态桥",
      "allowed_claim": "在可审计配对事件上的概率观测映射及其留出预测价值。",
      "forbidden_claim": "没有干预、同步设计或可识别假设时称为因果桥或真实损伤分解。"
    },
    {
      "outcome": "C1全栈与动态路由",
      "allowed_claim": "预注册组件在相同骨干上的单位级增量及完整成本。",
      "forbidden_claim": "仅凭全系统对弱基线获胜，把增益归因于变化点、路由、共形或 Agent 中任一模块。"
    },
    {
      "outcome": "TSFM",
      "allowed_claim": "指定模型版本在该公开加速数据、上下文和预算下的正结果、拒绝行为或负结果。",
      "forbidden_claim": "基础模型一般优于专用模型，或其预训练知识不存在污染。"
    },
    {
      "outcome": "Agent拓扑",
      "allowed_claim": "在隐藏任务和公平预算下的缺陷阻断、有效补丁、恢复率及质量—成本前沿。",
      "forbidden_claim": "未做随机化 meta-eval 时声称多 Agent 提高物理预测精度，或从一个 PHM 数据集推广到一般 Agent 系统。"
    },
    {
      "outcome": "方法新颖性",
      "allowed_claim": "严格标签语义、数据审计、统一回放协议、领域特定测量模型或可信负结果中的经核实增量。",
      "forbidden_claim": "把联合生存、状态空间、动态选择、长短期残差、共形区间、TSFM 应用或多 Agent 本身称为新机制。"
    },
    {
      "outcome": "在线与部署",
      "allowed_claim": "严格时间戳下的离线 prequential replay，以及标签真实到达后的合法短期 C/ESR 更新。",
      "forbidden_claim": "未经历真实影子期就称在线部署验证，或使用终末结局回填后称在线 RUL 校准。"
    },
    {
      "outcome": "公开复现",
      "allowed_claim": "在来源条款允许且独立 clean-room 重建通过后，声称公开可复现。",
      "forbidden_claim": "复用无明确许可证代码，或把仅有论文 PDF、未审计大包称为即用型公开基准。"
    }
  ],
  "minimum_publishable_package": {
    "stage_zero_gate": [
      "完成 Benchmark L 字节、HDF5、器件、批次、模态、时间和终止原因审计。",
      "发布逐器件事件/删失清单、重复身份裁决和可复建标签脚本。",
      "用实际结构做功效与可识别性仿真，结果不通过时自动降级研究目标。"
    ],
    "primary_question": "只检验一个问题：在已审计的加速过压数据上，一个简约且领域特定的观测机制能否改善留出器件的 C/ESR 概率预测；RUL 仅在结局审计通过时作为次要结果。",
    "model_set": [
      "last-value或drift",
      "一个经典统计退化或KF基线",
      "GPR或一个传统ML强基线",
      "最强直接近邻",
      "一个唯一的新机制挑战者"
    ],
    "recommended_new_mechanism": "若 EIS—瞬态存在充分、可核验的配对与协变量，选择简化版 C3；C2 作为正确处理删失的强基线而非新颖性中心。若配对不通过，则不做新模型论文，只发布协议、审计、复现与负结果。",
    "evaluation": "一次性冻结 LOCO，并把 LOVO明确限定为应力电压迁移；固定一个主要 endpoint、一个主要对比和一个分析脚本。所有结果按物理电容宏平均并逐只展示。",
    "statistics": "以单位级效应和置信区间为主；只有设计仿真证明精度足够时才作比较性推断。随机种子不能当独立样本。",
    "ablation": "只对唯一新机制做必要性消融；全专家池、动态路由、Physics-CDE和Agent拓扑不进入主要因果故事。",
    "reproducibility": "提供哈希、下载/解析脚本、字段字典、标签构建器、时间回放测试、环境锁、许可证清单和独立 clean-room 最小复现。",
    "go_no_go": "若终止原因、事件数、配对模态或目标精度任一不通过，停止 RUL/测量桥主张并转为小样本基准或数据限制报告。"
  },
  "recommended_scope": {
    "primary_paper": "公开加速过压电容数据的可审计基准、区间/右删失标签协议和泄漏安全 prequential 评测，并附简约统计基线。",
    "conditional_extension": "仅在审计证明配对充分时加入一个 EIS—瞬态概率观测模型；措辞限定为预测映射，不预设因果。",
    "separate_paper": "Agent-FE及五种拓扑应成为独立的 Agent/ML 工程 meta-eval，使用跨任务隐藏故障集，而不是作为 PHM 精度论文的一层。",
    "exclude_from_first_submission": [
      "C1全栈集成主张",
      "动态数值路由与动态Agent拓扑同时出现",
      "TSFM轻量微调作为主要贡献",
      "Physics-CDE",
      "跨真实工况或真实服役寿命表述"
    ],
    "publication_ceiling_before_external_data": "严谨的 PHM 基准、复现、测量研究或可信负结果；当前证据不足以支撑通用在线预测系统或一般多 Agent 方法贡献。"
  },
  "verdict": "PROCEED_WITH_MAJOR_REDESIGN",
  "review_independence": "same-family",
  "acceptance_status": "provisional",
  "candidate_ranking": {
    "same_reviewer_notice": "该排序由同一位对抗 reviewer 给出，只是基于三份文件的证据先验，不是额外独立投票，也不是性能预测。",
    "evidence_prior_order": [
      "C2",
      "C3",
      "C5",
      "C4",
      "C1",
      "C6"
    ],
    "ranking": [
      {
        "rank": 1,
        "candidate": "C2 Censored-Joint",
        "support": "与已确认的区间/右删失语义一致，可解释且比深度模型更适配小样本；也是所有后续 RUL 研究必须具备的基线。",
        "objection": "Gao et al. 2025 已覆盖联合退化—生存与 Bayesian 更新；shared frailty 和风险模型在极少事件下仍可能不可识别。",
        "falsification": "在完全相同切分上与纯轨迹、纯生存及最近邻联合模型比较 IBS/log score、区间相容性和单位级事件误差；优势必须跨器件而非由单个事件驱动。",
        "blocker": "审计后必须存在足够的已知阈值事件、可解释右删失和合理区间宽度；否则只能作为方法说明或基线，不能验证主假设。"
      },
      {
        "rank": 2,
        "candidate": "C3 EC-Bridge",
        "support": "最贴近数据中特有的 EIS/瞬态双模态结构，也最可能形成领域特定、可区别于通用预测器的技术贡献。",
        "objection": "EIS需离线移除器件、瞬态晚启动、尺度不同且配对 schema 未核验；“因果”措辞无当前证据。",
        "falsification": "在留出器件/电压上比较直接瞬态、简单测量误差模型和 EC-Bridge，并加入时间置换、板卡及仪器负控；要求 C、ESR 同时获益。",
        "blocker": "必须有足够同步或近同步配对、设备/温度/仪器元数据和跨器件重叠；否则模型不可识别。"
      },
      {
        "rank": 3,
        "candidate": "C5 Agent-FE",
        "support": "植入故障可提供比物理器件更多的独立任务，泄漏和语义错误也确实是当前数据管线的主要风险。",
        "objection": "作者自选的30个故障可能与自建验证器循环一致；Agent不直接预测，且通用Agent工程与多拓扑比较已有近邻。",
        "falsification": "使用未向Agent和验证器公开的故障家族及自然缺陷，随机比较 single 与 fixed，报告阻断率、误拒率、有效补丁、恢复率和总成本。",
        "blocker": "需要独立构造、隐藏且覆盖分布外故障的任务集；没有它，结果只是对预编写规则的回归测试。"
      },
      {
        "rank": 4,
        "candidate": "C4 Reject-TSFM",
        "support": "冻结零样本和拒绝机制实施成本相对低，正结果或严格负结果都可检验热门假设。",
        "objection": "Stress-2 仅11点上下文，领域和预训练污染未知；把TSFM用于小领域本身无新颖性。",
        "falsification": "比较完全相同专家池的有/无TSFM版本，预注册非平凡选择比例、宏平均增益和拒绝正确性；在S上应能稳定拒绝。",
        "blocker": "Benchmark L 必须有足够长度、独立器件和可转换输入；还需固定模型版本、许可证及污染风险说明。"
      },
      {
        "rank": 5,
        "candidate": "C1 TRACE-Cap",
        "support": "安全约束和假设写得较完整，长期可作为模块集成路线。",
        "objection": "组件数远超数据的信息量，多个核心思想有直接近邻，且全栈收益无法归因；Agent平面与预测精度因果脱节。",
        "falsification": "从固定简约骨干开始逐一加入组件，每一步都必须跨单位通过预冻结增益、校准和成本门，并最终超过最佳单组件。",
        "blocker": "只有数据审计、功效门及至少两个核心模块分别通过后才应实现全栈；当前不应作为首个实验。"
      },
      {
        "rank": 6,
        "candidate": "C6 Physics-CDE",
        "support": "结构上适合不规则采样和缺失，也允许通过软约束表达局部电容量回升。",
        "objection": "模型自由度最大、独立轨迹最少；所谓物理约束可能只是错误的单调先验，CDE增量也非领域特有。",
        "falsification": "与GPR、滤波器、TCN和无约束CDE做留出单位比较，同时要求长horizon误差、物理违例和种子方差改善。",
        "blocker": "只有 Benchmark L 审计证明存在足够多独立长轨迹、可靠时间和协变量后才可启动。"
      }
    ]
  },
  "agent_architecture_ranking": {
    "same_reviewer_notice": "该排序与上述对抗审查来自同一 reviewer，不构成第二票或独立 jury 结论。",
    "first_implementation_recommendation": "先实现 single Agent 加确定性验证器作为因果和成本基线；首个多 Agent 挑战者仅实现 fixed 类型化 DAG。不要直接从层级、辩论或动态路由开始。",
    "evidence_prior_order": [
      "single",
      "fixed",
      "hierarchical",
      "debate",
      "dynamic"
    ],
    "ranking": [
      {
        "rank": 1,
        "architecture": "single",
        "support": "上下文强耦合、预算低、行为最容易复现，是判断多Agent是否真有增量的必要基线。",
        "objection": "存在上下文污染和单点失败，但这些必须通过实测而不是预设。",
        "first_use": "完成数据审计、候选补丁和故障诊断，并把所有关键裁决交给确定性测试。",
        "promotion_gate": "若其他拓扑在同资源前沿上不能提高有效修复或缺陷阻断，生产方案保持 single。"
      },
      {
        "rank": 2,
        "architecture": "fixed",
        "support": "角色、权限和handoff固定，最适合隔离数据访问并复现实验。",
        "objection": "错误可能沿固定边传播，且额外通信成本可能没有收益。",
        "first_use": "作为唯一首轮多Agent实现，限定为解析、特征、泄漏挑战和治理节点。",
        "promotion_gate": "在隐藏任务上以相同成本显著降低错误晋级，且不增加误拒率或任务失败。"
      },
      {
        "rank": 3,
        "architecture": "hierarchical",
        "support": "当确有多个独立故障域时，可集中治理和局部恢复。",
        "objection": "监督节点成为瓶颈；与fixed DAG的实现差别可能只在命名而非可操作机制。",
        "first_use": "只在fixed暴露可复现的跨故障域协调失败后加入独立治理层。",
        "promotion_gate": "必须对预先定义的跨域故障提升恢复率，并报告监督延迟和错误放大率。"
      },
      {
        "rank": 4,
        "architecture": "debate",
        "support": "适合并行生成可执行反例和泄漏挑战。",
        "objection": "多数票没有数值意义，成本高且易产生相关错误。",
        "first_use": "仅用于训练侧探索；裁决只能依据可执行反例和隐藏测试。",
        "promotion_gate": "在相同预算下提高新缺陷发现率，而非仅增加提案数量或文本一致性。"
      },
      {
        "rank": 5,
        "architecture": "dynamic",
        "support": "理论上能按任务风险选择拓扑和控制成本。",
        "objection": "需要额外meta数据训练路由器，最容易对故障类型和工况过拟合；当前任务数远不足。",
        "first_use": "仅作为所有静态架构稳定后、在内层meta-train任务上训练的后置挑战者。",
        "promotion_gate": "在按数据集和故障家族完全留出的meta-test上超过最佳静态架构的质量—成本前沿，并有可靠OOD回退。"
      }
    ],
    "fair_meta_eval": {
      "experimental_unit": "独立的数据审计、代码修复或植入故障任务；Agent调用、提案数和预测窗口不是独立样本。",
      "task_split": "按数据集、故障家族和代码模块做meta-train/meta-validation/隐藏meta-test分割；动态路由只能读取meta-train/validation。",
      "assignment": "对每个隐藏任务随机、配对地分配五种架构并运行多个预注册随机种子；冻结提示词、工具和停止规则。",
      "resource_fairness": "共享相同基础LLM版本、候选库、数据视图和工具权限，在多个预冻结token/GPU/wall-clock成本档比较质量—成本前沿，同时记录人工分钟。",
      "two_tracks": [
        "诊断轨：给定相同候选和隐藏故障，测缺陷阻断、误报、漏报和恢复。",
        "发现轨：允许生成新候选，测有效候选率、错误晋级、最终模型变化及完整中介链。"
      ],
      "primary_outcomes": [
        "泄漏、伪指标和不可复现补丁阻断率",
        "错误晋级率与误拒率",
        "有效候选发现率",
        "任务完成率与恢复率",
        "总token、GPU、wall-clock和人工成本"
      ],
      "secondary_outcome": "最终冻结模型的数值误差；只有随机架构分配、候选路径记录和相同外层评测同时成立时，才可讨论拓扑导致的下游精度变化。",
      "evaluator": "隐藏真值与确定性测试优先，评测者不得依据Agent自评、投票或文字说服力裁决。",
      "statistics": "按任务做配对差异，按底层数据集或故障家族聚类；报告置信区间、种子方差和多重比较校正，不把Agent轮次当样本。",
      "decision_rule": "若fixed在相同成本下不优于single，停止更复杂拓扑；hierarchical、debate和dynamic分别只有在前一级出现预定义失败模式时才晋级。"
    }
  }
}