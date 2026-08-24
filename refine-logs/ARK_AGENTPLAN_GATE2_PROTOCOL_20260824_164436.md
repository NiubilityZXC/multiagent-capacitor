# Ark AgentPlan Gate-2：认证发现与合成能力探针决策包

**生成时间**：2026-08-24 16:44:36 +08:00  
**状态**：`AWAITING_ROTATED_SECRET_AND_HUMAN_DECISION`  
**AUTO_PROCEED**：`false`  
**替代范围**：本文件取代 Gate-1 中与 `accuracy_v1` retry、attempt 数和正式精度放行有关的草案；Gate-1 的公开接入路径与本地 dry-run 证据仍保留。

## 1. 本次可授权的唯一范围

本 Gate 只允许：

1. 在操作员已轮换凭据后，取得账户级 AgentPlan model-list 与当前 profile 的 text resources 快照；
2. 对二者交集中的至多 5 个候选模型，各执行 3 次固定合成 strict-schema probe；
3. 冻结 requested/returned model、schema compliance、usage、latency、错误类别与 capability matrix；
4. 生成不含凭据、原始 reasoning、自由文本错误或账户私有标识的 compact 审计工件。

本 Gate **不允许**：

- 发送 Ren、Patrizi、NASA 或任何电容测量/特征/预测 packet；
- 预测或评分 capacity、ESR、SOH、RUL、区间或异常风险；
- 运行 P4/P5 accuracy experiment、D4-H/D4-X 或任何正式 Agent graph；
- 自动扩大候选模型、重复失败请求、执行 tools、联网搜索、文件输入、cache、stateful continuation 或 store；
- 把 capability PASS 写成预测精度、可复现模型版本或论文结果；
- 使用聊天中曾暴露的 API key。

## 2. 凭据与调用前硬 Gate

用户此前在聊天中提供的 key 已视为暴露，必须在控制台撤销/轮换。新 key 只能由操作员在 repository 外的 shell/secret manager 注入；不得再次粘贴到聊天，不得出现在命令参数、脚本、配置、notebook、日志、Git history、prompt 或 shell history。

调用前必须同时满足：

- [ ] 旧 key 已轮换，运行环境只含新 key；
- [ ] `git grep`、tracked/untracked secret scan 均无 credential；
- [ ] runner 不打印环境、Authorization header 或请求 debug；
- [ ] `arkcli` 版本、可执行文件 SHA-256 和 profile 名称哈希已冻结；
- [ ] base URL 精确为 `https://ark.cn-beijing.volces.com/api/plan/v3`，数据路径为 `/responses`；
- [ ] `configs/ark_capability_probe_schema.json` SHA-256 已冻结；
- [ ] 操作员给出本文件第 9 节的精确批准语句。

任何一项不满足即保持 `BLOCKED_HUMAN_AUTH`，不得用已暴露 key “先试一下”。

## 3. 认证发现与候选选择

必须分别冻结：

1. AgentPlan 套餐返回的 model-list；
2. 当前 profile 实际可调用的 text resources；
3. 两者按服务端 callable identifier 的交集。

公开 registry `configs/ark_agentplan_models.json` 与用户截图只用于提出候选，不能证明可调用。服务端返回的 requested/returned model 必须精确一致；别名漂移、退役提示或无法固定 returned identity 的模型不进入正式 registry。

发现后的 probe 优先级为至多 5 个不同模型家族，各家族最多一个：

1. `kimi-k3`；
2. `glm-5.3`；
3. `deepseek-v4-flash` 或 `deepseek-v4-pro`，只选一个；
4. `minimax-m3`；
5. `doubao-seed-2.0-mini`。

只有出现在认证交集中的项目才可执行。截图标记即将下线的 `glm-5.2` 永久排除；coding-oriented `kimi-k2.7-code` 不进入首批时间序列预测 roster。若交集少于 4 个不同家族，D4-X 直接 `BLOCKED_CAPABILITY`，不得用 provisional ID 补齐。

## 4. 固定合成 probe

每个入选模型执行恰好 3 次相同语义、独立物理请求，总上限为：

- 候选模型数：`<=5`；
- 每模型请求数：`3`；
- inference 请求总数：`<=15`；
- 每请求 `max_output_tokens=96`；
- `stream=false`、`store=false`、cache disabled；
- 无 tools、无文件、无 URL、无搜索、无 `previous_response_id`；
- 输入只要求返回 `configs/ark_capability_probe_schema.json` 中的三个常量。

每次请求必须满足：

- HTTP/service 状态为 completed；
- strict JSON Schema 通过且无额外字段；
- `schema_version=capact.ark.capability-probe.v1`、`ok=true`、`echo_integer=7`；
- requested model 与 returned model 精确一致；
- response 未截断；
- usage 若服务端未返回则标 `UNKNOWN`，不得本地伪造；
- response ID 只持久化 SHA-256；原始 response envelope、provider error、reasoning 与自由文本不持久化。

一个模型只有 3/3 probes 全部通过才标 `CAPABILITY_PASS`；2/3 或更少一律 `CAPABILITY_FAIL`，本 Gate 内不补跑。

## 5. accuracy 与 resilience 严格分账

### `accuracy_v1`

正式预测阶段的每个 arm × origin × replicate：

- 恰好一个预占 physical slot；
- 最多一个 physical attempt；
- retry = 0；
- `STARTED` 必须在发送前 fsync；
- timeout、late、provider error、model mismatch、invalid schema、unknown usage 均消费该 slot并提交冻结 N0 fallback；
- crash-left `STARTED` 在恢复时只允许 `CRASH_RECOVERY` fallback，绝不重发；
- provider 原始响应仅在内存中验证，账本只保存闭合状态、哈希、验证后的 prediction 与 per-key execution。

### `resilience_v1`

401/403、429、transport reset、partial response 等 retry/failure injection 只能在独立 `resilience_v1` synthetic suite 中执行。其 attempts、成功率和恢复行为与 accuracy 结果完全分表，不得回填、替换或改善 `accuracy_v1` 的任何 prediction。

因此 Gate-1 的“最多 3 attempts”仅可作为被重写前的 resilience 研究草案，不能进入正式 accuracy protocol。

## 6. capability matrix 与裁决

每个模型记录：

- authenticated model-list membership；
- text-resource membership；
- requested/returned identity；
- 3 次 schema pass/fail；
- usage fields presence；
- latency；
- supported reasoning/config 参数；
- cache/store/tool/file/search 是否在发送前禁用；
- closed error code；
- model registry hash与 probe evidence hash。

裁决：

- 至少 1 个模型 `CAPABILITY_PASS`：只满足未来 D1/H1/RF1/RC1/ACT1 与 D4-H 的模型可调用前提；
- 至少 4 个不同家族 `CAPABILITY_PASS`：只满足未来 D4-X 的 roster 前提；
- 0 个通过：`BLOCKED_API`；
- capability PASS 从不等于 accuracy PASS。

## 7. 产物与秘密防护

应生成 timestamped + latest：

1. authenticated discovery summary；
2. redacted model/resource intersection；
3. per-probe closed-status ledger与 seal；
4. capability matrix；
5. pre/post secret scan报告；
6. P4 candidate registry草案。

账户原始控制面快照如含 account/profile 私有字段，只能保存在 ignored local audit tree；公开工件仅保存必要 logical model ID、字段级裁决和原始文件 SHA-256。禁止持久化 Authorization、API key、完整 provider envelope、reasoning、自由文本错误或原始 response ID。

## 8. 后续人工 Gate

P3 capability 完成后仍禁止电容预测。必须先满足 P1 row-level Data Gate、P2 numerical/metric/power freeze，并生成精确 `O_R`、`R_API`、`B_1`、`T_1`、请求总数和 token ceiling，随后由人类另行批准 P4 formal-spend envelope。

## 9. 人工签署区

若要仅批准认证发现与合成能力探针，请使用精确语句：

`批准 P3：已轮换聊天中暴露的 key，并已在仓库外安全注入；允许认证发现及最多 5 个模型×3 次、每次 96 输出 token 的 strict-schema 合成探针；不批准任何电容预测、P4/P5 或 retry accuracy。`

在收到该语句前，状态保持 `BLOCKED_HUMAN_AUTH`。本文件与之前用户提供过 key 的事实均不构成批准。

