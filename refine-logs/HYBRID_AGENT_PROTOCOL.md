# 电容在线预测：LLM 多 Agent × 专用小模型协议 v0.3-draft

**日期**：2026-08-24  
**状态**：`PROPOSED_HUMAN_CHECKPOINT`  
**AUTO_PROCEED**：`false`  
**真实 API 调用**：尚未授权执行本协议的数值 pilot  
**当前允许**：架构设计、无网络实现、mock/fault tests、方舟 client dry-run  

## 1. 目标与非目标

唯一优先目标是未见电容上的真实滚动预测精度。LLM 解释、自然语言质量或 Agent 自评分不能进入冠军裁决。

主假设 H1：在相同因果输入、候选小模型和预算下，LLM 路由的安全凸融合能否优于最强单一小模型与无 LLM 数值融合。

支撑假设 H2：在 H1 成立后，多 Agent 拓扑是否在相同基础模型与总预算下优于单 Agent。

以下不作为当前主张：

- “LLM 选模型”本身具有新颖性；CastFSR、REATS、LLM Forecasting Planner、KairosAgent 已构成强近邻。
- Stress-2 六列证明跨物理器件泛化。
- LLM 生成的 confidence、理由或区间具有统计含义。
- Benchmark-L 在 capacity/ESR/identity gate 未通过时可用于精度评测。
- G09 未通过时存在可数值评分的 RUL。

## 2. 数据与执行资格

| Scope | 当前资格 | 允许动作 |
|---|---|---|
| 合成 fixture | PASS | schema、路由、故障、成本与 causal-taint tests |
| Stress-2 | SANITY_ONLY | 影子 API/拓扑工程验证；不得形成模型冠军主张 |
| Benchmark-L EIS 结构 | P1 parser ready, real run pending | parser/Data Gate only |
| Benchmark-L capacity | BLOCKED G05/G06/G07/G10 | 不调用预测 API |
| Benchmark-L ESR/SOH | BLOCKED G08 | 不调用预测 API |
| RUL | BLOCKED G09 + Design Gate + Freeze B | 恒为 NA |

真实 API 实验前必须新增协议批准记录，并冻结 model capability snapshot、endpoint、prompt、schema、预算、timeout、retry、fallback 和 API replicate 数。

## 3. 因果 OriginPacket

Agent 只能看到：

- `origin_key`：无器件/文件身份含义的哈希或安全序号；
- 已揭示的 C/ESR ratio prefix；
- 预注册 horizons；
- 每个冻结小模型的候选点预测；
- 仅由 outer-train inner-LOCO 得到的逐 model×target×horizon 误差摘要；
- 当前候选分歧与仅由训练分布定义的 OOD score。

硬禁止字段及代理：actual、label、future、suffix、EOL、RUL、termination、failure、final length/cycle、row count、unit ID、物理器件 ID、文件/路径、源对象名、外层汇总结果。

请求使用 canonical JSON；没有自由文本字段。修改、删除或置换 held-out suffix 后，所有既往请求哈希、响应解析结果与预测必须逐字不变。

## 4. 数值专家库

第一阶段只使用已实现并通过 causal replay 的候选：

1. last value；
2. held-prefix global drift；
3. local linear；
4. log-linear exponential；
5. causal local-trend Kalman filter；
6. ridge causal increment。

GPR 作为 add-one 候选：必须先实现训练侧 scaler/kernel/噪声选择、CPU/sample gate 与 inner-LOCO 测试。Chronos/TimesFM 等 TSFM 只在 Benchmark-L target 和 sample gate 通过后进入，不因“现代”而自动加入。

无 LLM 控制 C2 为训练侧非负凸融合或训练侧最优专家；不得用 held-out error 拟合权重。

## 5. Agent 角色与动作空间

- `regime_analyst`：依据 causal prefix、候选分歧和训练侧误差提出白名单权重或 abstain。
- `forecast_critic`：寻找候选失配、漂移与 OOD 风险，只输出权重、枚举 reason code 或 abstain。
- `fusion_judge`：在合法候选之间给出最终凸权重；禁止输出生产点预测。

Hybrid strict JSON 只有：schema version、role、origin echo、abstain、候选权重、0–1 risk code、枚举 reason codes。所有字段 `additionalProperties=false`；权重必须有限、非负、逐候选完整且和为 1。risk 不用于预测区间或晋级。

主 Hybrid 点预测由本地确定性 `convex_fuse` 计算，并逐 target×horizon 保证位于候选凸包内。

纯 LLM direct point 仅为 A1 对照，必须使用独立 `agent-direct.v1` schema；不得生成区间。当前代码尚未实现 A1，正式协议批准后再 add-one。

## 6. 拓扑

| Arm | 拓扑 | 调用形态 | 进入条件 |
|---|---|---|---|
| C0 | last-value | 0 API | 锚点 |
| C1 | inner-LOCO 最优小模型 | 0 API | 必跑 |
| C2 | 无 LLM 数值凸融合 | 0 API | 必跑 |
| A1 | single-agent direct | 1 API/origin | 新协议明确允许后 |
| A2 | single-agent hybrid | 1 API/origin | 必跑 |
| A3 | fixed hierarchy | analyst→critic→judge，3 calls | A2 同时优于 A1/C2 后 |
| A4 | parallel debate | analyst ∥ critic→judge，3 calls | A3 优于 A2 后 |
| A5 | dynamic route | consensus 0 call；hard origin 1 call | 至少一个静态多 Agent 优于 A2 后 |

动态触发器仅使用 outer-train 冻结的候选分歧阈值、OOD 阈值、已成熟 prequential telemetry；不能依据当前或未来误差决定是否调用。

任一级不优于前级即接受更简单系统，后续复杂拓扑停止。

## 7. 方舟 AgentPlan 接入

- Base URL 由 `ARK_BASE_URL` 环境变量提供；预期 lane 为 `/api/plan/v3`。
- API key 只从 `ARK_API_KEY` 环境变量读取；不得进入 argv、仓库、prompt、schema、manifest 或日志。
- 初始逻辑模型候选：`kimi-k3`。服务返回的实际 `model/version` 必须记录；其他模型在 capability snapshot 前均为 `BLOCKED_UNAVAILABLE`。
- 预测调用：stateless、`store=false`、cache disabled、tools none、strict JSON Schema。
- 冻结 temperature/top_p/max tokens；服务若不确认 seed 或版本则记录 NA，不推断确定性。
- 只对 timeout、429、5xx 进行预注册有限重试；schema/semantic 错误不修复、不追问。
- 迟到响应不得改写已提交 fallback。

由于 API key 已在对话文本出现，真实 pilot 前建议轮换，并由用户在 shell 中安全 `export ARK_API_KEY=...`；本系统不会把对话中的密钥拼入命令。

## 8. 回退与提交

统一 fallback 是 outer-train inner-LOCO 平均误差最小的小模型，数值并列按冻结复杂度顺序。所有 Agent 臂共享同一 fallback。

顺序固定：

1. label service 仅揭示 prefix；
2. 生成并哈希 OriginPacket；
3. 小模型生成候选；
4. Agent 调用或动态跳过；
5. schema/semantic/budget 验证；
6. 凸融合或 fallback；
7. append + fsync 请求、响应哈希、route 与最终预测；
8. seal/checkpoint 后 label service 才可 reveal next；
9. maturity/scoring 服务另行运行。

失败行保留在 planned denominator。只统计 API 成功子集的精度只能标为选择偏差诊断。

## 9. 区间与异常风险

LLM 不生成预测区间。每个 arm 的 50/80/90% 区间只能来自 outer-train inner-LOCO prequential residual；独立 calibration units 不足时为 `NA_insufficient_calibration_units`。

Agent risk 只是路由 telemetry。只有通过训练侧冻结映射、明确标签和独立验证后，才可变成数值 anomaly risk；不能把自然语言风险当概率。

## 10. 固定 Eval

正式主要指标在 Freeze B 中按 target 冻结；默认候选是逐物理器件先聚合、再宏平均的 MAE。次指标：RMSE、标准 MASE、relative-MAE/skill、逐器件与最坏工况。

区间指标：coverage、width、interval score/WIS。系统指标：invalid JSON、fallback、timeout、429/5xx、deadline miss、call count、token、p50/p95/p99 latency。

推断单位是物理器件/duplicate group，不是窗口。所有 arm 共用 planned keys、API replicate、model、数据视图、fallback、token/call/wall-clock 上限。多主比较用预注册 Holm；Design Gate 不足则输出 `NO_CHAMPION`。

## 11. 最小执行阶梯

1. H-A0：mock/dry-run；strict JSON、taint、fallback、拓扑 call count、convex hull、secret safety。
2. H-A1：用户安全注入新 key 后，1 个 synthetic capability smoke；验证 strict JSON、返回 model、usage、latency，不看数据精度。
3. H-A2：Stress-2 小型 shadow subset；每只 column-surrogate 选一个冻结 origin，先跑 C0/C1/C2/A1/A2；只验证系统与数值 scorer。
4. H-A3：Stress-2 全 causal shadow；仍为 sanity/no-claim。
5. H-A4：Benchmark-L target gate + Design Gate + Freeze B 后，运行 C0/C1/C2/A1/A2。
6. H-A5：仅按阶段门逐级运行 A3/A4/A5。

任何 prompt、schema、model、candidate、budget 或 code 变更都产生新 arm/version，不能覆写旧 prediction ledger。

## 12. 当前实现状态

- `experiments/api_hybrid/schemas.py`：严格 request/decision 合同与 taint 防护。
- `orchestrator.py`：四拓扑、确定性 fallback 与 convex fuse。
- `arkcli_adapter.py`：环境变量凭据、无 shell argv、strict-schema dry-run、有限网络重试、reasoning 丢弃。
- `tests/test_api_hybrid.py`：13 个无网络单元测试。
- 方舟 client preview 已验证 AgentPlan stateless lane；未产生真实请求/用量。

## 13. 查新边界

- [CastFSR](https://arxiv.org/abs/2608.03031) 已采用 fast numerical prior、slow LLM deliberation 与 reflection；其[公开仓库](https://github.com/Xiaoyu-Tao/CastFSR)在本次核验时未发现根目录 LICENSE，故本实现不复制代码。
- [REATS](https://arxiv.org/abs/2608.10149) 已直接研究 LLM 自适应 ensemble routing。
- [LLM as Forecasting Planner](https://arxiv.org/abs/2607.24892) 已让 LLM 在 TSFM 轨迹上做 policy/value guidance。
- [KairosAgent](https://arxiv.org/abs/2605.30002) 已融合 LLM reasoner 与 TSFM forecaster；[TimeClaw](https://arxiv.org/abs/2606.05404) 已提供 agentic time-series harness。

因此当前方案的潜在贡献只能是电容退化的严格因果/删失/身份边界、可执行 Agent 权限合同、failure-safe shadow Eval 与经真实未见器件证明的效果；不能声称通用 LLM router 或 fast–slow–reflect 架构本身新颖。

下一人工检查点：是否批准 H-A1/H-A2，并在本机 shell 安全设置轮换后的 `ARK_API_KEY` 与 `ARK_BASE_URL`。
