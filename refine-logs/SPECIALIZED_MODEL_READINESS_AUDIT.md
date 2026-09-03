# 专用模型路线：实现就绪度与未来优先级审计

**时间**：2026-09-03 18:20:00 +08:00
**状态**：`STATIC_AUDIT_ONLY / P2_BLOCKED / NO_MODEL_RUN`

## 结论

当前仓库已有一个可审计的六模型因果数值骨架，但它明确服务于 synthetic Stress-2 harness，不能被表述为已在 Ren/Patrizi 上实现或验证的专用电容模型。若未来目标是专用模型主导的高水平论文，最合理的下一候选不是直接堆叠大模型，而是先建立同一冻结协议下的 `N0+` 小样本、状态空间和现代序列模型候选池；其后再决定是报告 fold-local numerical selection policy，还是把一个固定模型提升为 confirmatory arm。

## 已有实现（仅代码事实）

| 家族 | 当前实现 | 代码边界 | 可直接声称 |
|---|---|---|---|
| persistence / drift / local linear / log-linear | `last_value`、`global_drift`、`local_linear`、`exponential` | `experiments/audit_cap/models.py`，输入为已揭示的一维 prefix | 仅“synthetic harness 内因果 baseline 已实现” |
| causal local-trend KF | `local_trend_kf`，训练侧 robust scale 与有限噪声网格 | 同上；点预测，无 Ren/Patrizi adapter、无区间/校准 | 仅“候选 state-space baseline 原型存在” |
| ridge causal increment | `ridge`，outer-training state 与 prefix-only features | 同上；是 Stress-2 data class 的实现 | 仅“候选小样本 ML baseline 原型存在” |
| LLM action registry | 六个模型 ID 与五个 convex templates | `experiments/vfps_agent/actions.py`；mock-only policy authority | 不能声称这些模型已被真实数据训练或比较 |

现有 `replay.py`、`run_stress2_baselines.py` 与 `models.py` 都显式依赖 `Stress2Data`/synthetic harness。因此将它们直接用于 Ren 或 Patrizi 会违反当前 Data Gate、模型代码 hash、target 语义和 preseal 约束。

## 尚未实现、但已在 N0+ 提案中列出的家族

| 优先级 | 家族 | 未来价值 | 进入条件 |
|---|---|---|---|
| 1 | AutoETS / AutoARIMA / Theta | 强 classical 对照，低算力且能防止“只比弱 baseline” | P1 PASS；频率/缺失语义可机械定义 |
| 1 | RLS/RELS 与可观测的 particle filter | 与退化动态及 online 场景自然匹配；是专用模型论文的优先候选 | P2 确定 state、likelihood、initialization、interval 与失败语义 |
| 1 | gradient boosting / elastic net | 小样本、特征化专用预测的必要对照 | 特征只从 outer-training/past prefix 产生且被 hash-pin |
| 2 | DLinear / N-HiTS | 简洁现代序列模型，对“复杂模型必要性”形成高价值反证 | 单位数、序列长度、训练预算与多 horizon 输出可行 |
| 2 | S4/RevIN | 与现有 supercapacitor RUL 文献直接相关 | RUL endpoint、EOL/censor 和训练样本充分性均通过 Gate |
| 3 | PatchTST / iTransformer | 多变量高容量候选 | 样本/变量数支持，且严格防止 outer-fold leakage |
| 3 | Chronos / TimesFM / Moirai | zero-shot TSFM 压力测试 | 版本、输出量化、预训练污染披露、离线权重可复现且另行批准 |
| conditional | PINN-LSTM | 可形成物理模型故事，但风险最高 | 方程、参数、观测变量与 RUL semantics 可重复；否则机械 NA |

## 高水平文章的优先实验次序（仅未来计划）

1. 先以 CPU 优先的 classical + state-space + small-data ML 构造 `N0+`；确认数据、目标、区间、功效和跨工况评测本身成立。
2. 若 `N0+` 显示稳健而有意义的改善，论文可以以“审计级 whole-device numerical selection policy”作为主线，不需要 LLM 正结果。
3. 若某一固定专用模型在未见 outer result 前被单列为 arm，并在外层、跨电容/工况、WIS/failure/deadline 与消融上通过，则它才具备“专用模型方法论文”资格。
4. 现代高容量模型/TSFM只作为更强 stress baseline；它们失败同样是有效结果，不能用事后模型替换救叙事。

## 阻断与不允许的捷径

- 当前 Ren row-level scientific eligibility 与 P2 freeze 尚未完成；不得运行上述任一模型。
- `N0+` 选择策略与“固定模型 superiority”是不同 estimand。后者需要新增 confirmatory arm/new generation，不能由 inner selection 的赢家事后取得。
- 不以 synthetic Stress-2、Benchmark-L 或 LLM 判断替代真实 eligible whole-unit replay。

## 需要的下一条明确人类决定

在不改变当前 `11∪{ARCH1}` 的前提下，最小可执行选择是 `APPROVE_N0_PLUS_POLICY`。若目标是把某个模型作为方法论文核心，则应选择 `APPROVE_FIXED_SPECIALIZED_ARM` 并指定模型族；两者都仍要先经过 P1/P2 gate。
