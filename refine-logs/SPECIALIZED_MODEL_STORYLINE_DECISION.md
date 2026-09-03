# 专用退化模型论文路线决策包

**时间**：2026-09-03 18:10:00 +08:00
**状态**：`USER_DIRECTION_RECORDED / PRESEAL_PROPOSAL_ONLY / NO_EXECUTION_AUTHORITY`
**适用范围**：公开电容退化数据上的统计、状态空间、粒子滤波、传统机器学习、专用序列/RUL模型与现代时间序列模型。

## 用户方向

若专用模型在冻结的真实测试上能够支撑高水平论文，则该路线可继续并可成为论文主线；不因它不是大模型 Agent 而降低优先级。

## 不变的证据规则

专用模型与 direct LLM、LLM+专用模型、固定/动态多 Agent 共用同一数据 Gate、rolling replay、whole-capacitor outer split、leave-one-capacitor-out、跨工况测试、预测前封存、共同成熟 key、失败分母、区间/WIS、单位级推断与 P6 审计。模型名称、参数量或 LLM 主观评语不能替代数值测试。

## 两种可发表的专用模型路线

1. **折内选择的数值策略论文**：把冻结的 `N0+` 候选池和 nested inner whole-unit selection 视为一个完整的 numerical selection policy。可主张的对象是该 policy 在外层单位上的表现及其跨工况限制，不是事后被挑出的单一 constituent 模型。
2. **固定专用模型方法论文**：若希望主张某一个模型（例如 state-space/particle filter、专用小样本序列模型、物理约束 RUL 模型或 TSFM）本身有效，它必须在看见任何结果前成为一个固定、独立的 confirmatory arm；需冻结代码、版本、输入、训练预算、特征、区间构造与 failure semantics，并与 N0/其他 arms 做同一 outer replay 比较。

后一条会改变当前 `canonical 11 arms ∪ {ARCH1}`。它不能被静默加入或在解封后补跑；需要独立的人类批准、更新 arm registry、重新计算预封存 generation ID/hash、重跑 adversarial review，并在任何预测前重新 seal。

## 论文升级的最小证据门

一个专用模型路线只有同时满足下列条件才可被考虑为高水平文章主线：

- P1 对所用 target/终止/删失语义与物理单位身份通过，且 P2 的 N0、度量、区间、功效和执行包络已经冻结；
- 严格时间切分与 outer whole-unit/LOCO 均显示预注册的点预测改进，或达到预注册 non-inferiority 后具有唯一、绝对的 operational improvement；
- WIS、coverage、failure、deadline 与所有 harm gates 不恶化；
- 预注册的跨工况/跨电容边界未被事后删除，或失败被如实作为 scope limit；
- 消融能排除数据泄漏、额外信息、调参预算或候选选择本身造成的表观提升；
- P6 完成代码、数据、统计、主张和文献审计。若结果为 null/negative，仍可形成严格 benchmark/audit 论文，但不得伪装成方法 superiority。

## 当前无权执行的事项

本记录不批准下载、Ren 解压/解析、P2 训练或评分、SOH/RUL 构造、GPU 实验、Ark 调用或真实电容预测。当前预封存 bundle 仍为 `UNAPPROVED_HUMAN_GATE_REQUIRED`，其 canonical plan 未被修改。

## 后续人工选择

- `APPROVE_N0_PLUS_POLICY`: 批准候选池扩展，专用模型作为 fold-local N0+ selection policy 的组成部分；不新增 confirmatory arm。
- `APPROVE_FIXED_SPECIALIZED_ARM`: 批准一个精确命名的专用模型作为独立 arm，并触发新的 preseal generation；必须先给出模型、版本、输入、训练预算和新 arm 的主张。
- `RETAIN_CURRENT_11_PLUS_ARCH1`: 不改变 arm set；专用模型只保留为现有 N0/后续 paper 的非确认性候选描述。

未收到其中之一的明确批准前，维持当前封存和停止边界。
