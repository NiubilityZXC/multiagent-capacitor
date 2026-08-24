# Idea Creator 并行生成账本

**日期**：2026-07-29  
**生成约束**：三个分支互相独立；只读；不得排名；每个候选必须给出可证伪假设、最小实验、成功/失败条件、数据、算力、风险与最近邻。  
**评审独立性**：生成分支不参与最终裁决。

## 1. 数据与 Eval 分支（10）

| # | dedup_key | 候选 | 可证伪核心 |
|---:|---|---|---|
| D1 | `auditable-capacitor-data-manifest` | 可执行数据血缘与可用性审计 | 修正可复现的数据语义/对齐问题是否改变至少一个端点误差或模型次序 |
| D2 | `causal-normalization-leakage-sentinel` | 因果归一化与窗口泄漏哨兵 | 全寿命归一化/随机窗口是否造成可测的虚假改善 |
| D3 | `multi-definition-eol-censoring` | 多定义 EOL 与区间删失标签 | EOL 定义/删失处理是否导致标签和模型排序改变 |
| D4 | `causal-eis-transient-measurement-bridge` | 离线 EIS→在线瞬态因果测量桥 | 分层桥是否跨留出电容降低 C/ESR 及下游 RUL 误差 |
| D5 | `event-triggered-prequential-evaluation-ledger` | 每点触发的预序滚动账本 | 滚动回放是否推翻单截点评测的模型排序 |
| D6 | `nested-capacitor-voltage-generalization-matrix` | 嵌套 LOCO/LOVO 泛化矩阵 | 随机窗口结果与整电容/整电压外推是否存在显著差距 |
| D7 | `fold-internal-agentic-feature-tournament` | 训练折内多 Agent 特征竞赛 | 冻结特征能否在多数留出电容及零调参跨电压保留收益 |
| D8 | `prospective-anomaly-risk-head` | 未来阈值穿越/突变异常风险头 | 模型分歧/创新是否提高 AUPRC、Brier 和提前量且不增加过多虚警 |
| D9 | `frozen-eval-shadow-promotion-gate` | 冻结 Eval 影子冠军门 | 多端点门是否阻止平均误差改善但覆盖/晚报更差的挑战者 |
| D10 | `selective-prediction-under-sparse-modalities` | 稀疏模态选择性预测 | 可用性路由/弃权是否在相同覆盖率降低选择性风险 |

## 2. 模型与动力学分支（10）

| # | dedup_key | 候选 | 可证伪核心 |
|---:|---|---|---|
| M1 | `hierarchical-switching-dual-state-filter` | 层级双状态切换状态空间 | 切换状态是否在膝点/后半寿命改善误差并保持区间校准 |
| M2 | `online-bayesian-monotone-process-averaging` | 随机退化过程在线 Bayesian 平均 | 软平均是否降低最坏电容 RUL 误差和 CRPS |
| M3 | `label-audited-joint-degradation-survival` | 标签审计的退化—生存联合模型 | 联合模型是否同时改善 IBS/log score 和 RUL 误差 |
| M4 | `local-global-residual-fusion` | 长期基线 + 近期残差双通道 | 在线融合是否跨多个 horizon 同时优于长期/短窗单通道 |
| M5 | `physics-constrained-continuous-time-multitask` | 物理约束连续时间多任务 | 约束 CDE 是否降低长步误差和物理违例且不压制真实回升 |
| M6 | `target-horizon-online-conformal-calibration` | 目标×horizon 在线共形 | 多步自相关校准是否达到 coverage 且宽度不过度膨胀 |
| M7 | `changepoint-triggered-heterogeneous-expert-router` | 变化点异构专家软路由 | 是否降低 90 分位电容误差和变化后恢复时间 |
| M8 | `equivalent-circuit-multimodal-observation-model` | 等效电路 EIS/瞬态联合观测 | 携带拟合协方差是否改善 LOCO/LOVO 并区分测量异常 |
| M9 | `abstaining-time-series-foundation-expert` | 可拒绝 TSFM 专家 | TSFM 是否只在足够上下文中带来增益并在 11 点序列被拒绝 |
| M10 | `llm-code-diagnostic-agent-only` | 仅代码/诊断的 LLM Agent | Agent+验证器是否提高植入故障召回而不误修正常管线 |

## 3. Graph Engineering 分支（10）

| # | dedup_key | 候选 | 可证伪核心 |
|---:|---|---|---|
| G1 | `evidence-locked-typed-fixed-agent-dag` | 证据锁定的类型化固定 DAG | 是否降低泄漏/无效上线并保持或改善真实 Eval |
| G2 | `hierarchical-fault-domain-isolation-graph` | 层级故障域隔离 | 10% 节点故障时是否抑制误差传播并保持精度 |
| G3 | `executable-debate-with-numeric-referee` | 数值裁判的并行对抗辩论 | 可执行反例是否比 LLM 多数票更早发现泄漏/过拟合 |
| G4 | `frozen-risk-telemetry-dynamic-router` | 冻结风险遥测动态拓扑 | 在精度非劣下是否显著降低 Agent/训练成本 |
| G5 | `safety-constrained-agent-supernet-edge-ablation` | 安全 Agent 超网与边消融 | 图搜索能否在外层 Eval 找到真实有用且更稀疏的边 |
| G6 | `transactional-event-sourced-agent-graph-recovery` | 事务事件溯源与局部回滚 | 故障下是否提高完成率、减少重训且不改变数值输出 |
| G7 | `data-lineage-taint-firewall-agent-graph` | 数据污点防火墙 | 是否 100% 阻断预定义 future/Eval 攻击并低误报 |
| G8 | `loco-cross-condition-specialist-federation` | 跨工况专家联邦图 | 训练工况专家融合是否改善完全未见工况的最差误差 |
| G9 | `champion-challenger-shadow-sequential-gate` | 冠军—挑战者影子孪生 | 序贯数值门是否降低偶然改善导致的错误上线 |
| G10 | `criticality-adaptive-agent-redundancy` | 节点关键度自适应冗余 | 是否接近全冗余恢复效果而显著节省调用/训练成本 |

## 4. 机械合并后的 21 个模块

1. 数据 manifest/血缘审计。
2. 因果预处理与污点防火墙。
3. EOL 多定义、区间/右删失。
4. EIS→瞬态测量桥。
5. 等效电路多模态观测。
6. 每点 prequential 账本。
7. 嵌套 LOCO/LOVO。
8. Agent 折内特征发现。
9. 前瞻异常风险。
10. 稀疏模态选择性预测。
11. 层级切换状态空间。
12. 退化—生存联合。
13. 长期基线/近期残差。
14. 连续时间深度多任务。
15. 目标×horizon 在线校准。
16. 变化点异构路由/模型平均。
17. 可拒绝 TSFM。
18. 固定类型化/层级故障域 Agent 图。
19. 可执行辩论与确定性裁判。
20. 事务恢复/自适应冗余。
21. 影子冠军—挑战者与人类裁决。

## 5. 生成阶段未做的事

- 没有训练任何候选。
- 没有用语言模型给预测精度打分。
- 没有把未完整下载的大包字段当成已核验事实。
- 没有让候选生成 Agent 决定排名。
- 没有越过 `AUTO_PROCEED=false` 的人类检查点。

