# 方舟 AgentPlan Gate-1 接入协议

**冻结时间**：2026-08-24 13:30:47 +08:00  
**状态**：`BLOCKED_PENDING_AUTHENTICATED_DISCOVERY_AND_CAPABILITY_PROBES`  
**真实推理调用**：未执行  
**凭据策略**：不接收、不记录、不提交聊天中出现过的密钥；真实调用前必须轮换，并由操作员在运行环境外安全注入。

## 1. 适用范围

本协议约束电容在线预测实验中方舟 AgentPlan 的模型发现、请求、预算、失败处理和证据封存。它不改变数据资格或 Eval；数据 Gate 为 `BLOCKED` 的 target 即使 API 可用也不得预测或计分。

候选模型来自 `configs/ark_agentplan_models.json`。认证快照前，截图中的所有短模型 ID 均为 `provisional`。

## 2. 两类认证发现

必须冻结以下两种快照并取交集：

```bash
arkcli plans model-list --plan agent-plan --profile <PROFILE> --format json
arkcli resources list --profile <PROFILE> --modality text --format json
```

第一项回答套餐支持什么；第二项回答当前 profile 实际可调用什么。权威控制面操作为：

```text
POST https://ark.cn-beijing.volces.com/?Action=ListArkAgentPlanModel&Version=2024-01-01
```

控制面使用账户认证/签名，应交给官方 SDK 或 `arkcli`，不自行实现签名。参考：[ListArkAgentPlanModel](https://api.volcengine.com/api-explorer/?action=ListArkAgentPlanModel&groupName=Agent+Plan+API&serviceCode=ark&version=2024-01-01)。

## 3. 数据面合同

```text
POST https://ark.cn-beijing.volces.com/api/plan/v3/responses
Authorization: Bearer <runtime secret>
Content-Type: application/json
```

Base URL 后不追加 `/v1`。参考：[AgentPlan 接入教程](https://console.volcengine.com/ark/region:cn-beijing/docs/82379/2556054?lang=zh)、[Responses 快速开始](https://www.volcengine.com/docs/82379/1795150)。

正式 benchmark 默认：

- 非流式 `stream=false`、`store=false`；
- 禁用 cache、文件、URL、内置联网搜索和 debug；
- 不使用 `previous_response_id`；
- 每次请求提供完整 past-only canonical packet；
- strict JSON Schema；额外字段、截断、非法数、`status != completed` 均失败；
- 受限保存 `id`、`model`、`status`、`output`、`usage` 的哈希证据。

`store=false` 不等于法律意义的零留存；Gate-1 只允许公开或合成 fixture。函数工具按 Responses 多轮协议处理，`call_id` 必须 exactly-once。参考：[工具调用](https://www.volcengine.com/docs/82379/1958524?lang=zh)、[Response object](https://www.volcengine.com/docs/82379/1783703?lang=zh)。

## 4. Timeout 与 retry

以下是预注册 harness 策略，不是平台保证：

- connect/TLS 10 s；首字节 120 s；单请求 hard timeout 300 s；task×arm deadline 600 s；
- 每逻辑调用最多 3 个物理 attempts，全部计入 arm ceiling；
- 只重试 body 尚未完整发送的连接失败或明确的 408/429/500/502/503/504；
- 有 `Retry-After` 时遵守，否则使用冻结的确定性退避；
- body 完整发出后的 timeout、partial response、SSE EOF 记 `FAILED_AMBIGUOUS`，不自动重发；
- 401/403、模型不存在、schema/semantic/tool 错误不重试；
- timeout、late response、provider error、budget exhaustion 均返回预注册 numerical fallback，并保留 planned denominator。

## 5. Token、版本与随机性

原始 `usage` JSON 原样封存，另规范化：

```text
input_tokens  = usage.input_tokens  ?? usage.prompt_tokens
output_tokens = usage.output_tokens ?? usage.completion_tokens
total_tokens  = service-returned usage.total_tokens
```

不得以本地加法覆盖服务端 `total_tokens`。reasoning、cached、tool usage 和 retry 分别登记。失败请求没有 usage 时，token 成本为 `UNKNOWN`，不得进入 matched-token 主张。

当前没有已核验的 AgentPlan `seed` 保证；`temperature=0`、`top_p=1` 只是请求参数。每个正式模型先做 3–5 次合成能力重复探针，并同时记录 requested/returned model。别名可漂移时不得声称位级复现。

控制面 `GetUsageDetails` 只作运行后套餐/账单对账，不作为逐请求 token 账本。参考：[GetUsageDetails](https://api.volcengine.com/api-explorer/debug?action=GetUsageDetails&groupName=Agent+Plan+API&serviceCode=ark&version=2024-01-01)。

## 6. 等预算比较

正式 envelope 在能力探针后冻结；Gate-1 草案：

```text
physical_request_ceiling: 6
requested_output_token_sum: 4096
workflow_deadline_s: 600
max_parallel_requests: 3
```

| Arm | 拓扑 | 示例 token ceiling |
|---|---|---:|
| `D1` | single direct | 4096 |
| `D3-H` | 3 homogeneous workers + fixed synth | `3×768 + 1792` |
| `D3-X` | 3 heterogeneous workers + same synth | `3×768 + 1792` |
| `H2` | tool selection + continuation | `1024 + 3072` |
| `H2-control` | 相同两阶段但无 tool | `1024 + 3072` |
| `MVEC` | fixed proposers/challenger + local verifier | 与 matched direct 相同 |

这是 attempts、requested output ceiling 和 deadline 的匹配，不保证实际 token 完全相等。只有 usage 完整且实际 token 落入预注册 caliper（候选 `±5%`）时，才另报 matched-spend 子分析。主结果同时报告预测质量、实际 token、物理 attempts、端到端延迟和失败率的 Pareto 前沿。

共同规则：同一 OriginPacket、target keys、deadline 起点、retry 和 fallback；worker 失败产生冻结 sentinel，不动态增派；homogeneous/heterogeneous 使用同一 synthesizer；所有 worker、synth、tool continuation 和 retry 均计成本；最终得分只由冻结数值 Eval 给出。

## 7. Attempt ledger

每个 HTTP attempt 和工具执行各一行 canonical JSONL，字段至少包括：

```text
run/task/replicate/arm/logical-call/physical-attempt/role
discovery/registry/model-requested/model-returned hashes
prompt/input/schema/tools/config hashes
base/path/transport/store/cache/sampling/reasoning parameters
budget/deadline before and after
monotonic/wall start/end/duration
HTTP/service status, error, retry decision
raw/normalized usage
tool ledger hashes
redacted request/response hashes
schema status, accepted, privacy status
prev_entry_hash, entry_hash
```

硬规则：新 run 新目录；依赖调用前 append+flush+fsync；`COMPLETE` 只能最后写且由独立 seal 绑定全部 lineage；不记录 Authorization、key、完整环境、代理凭证或 debug body；provider ID 只存 HMAC 化标识；hash chain 无外部 anchor 时不能证明真实时间先后，论文必须如实陈述。

## 8. 无网络失败注入

Gate-1 前必须验证：

1. secret canary 出现在 env/header/stderr/response 时公开账本无泄漏；
2. request/response model 不一致 fail closed；
3. 401/403 不重试、不打印凭据；
4. provisional/404 model 阻断 arm；
5. 429 + `Retry-After` 后成功保留两个 attempts；
6. body 前 connect reset 可重试；body 后 timeout/partial response 不重发；
7. incomplete、token truncation、非法 JSON/schema 不计成功；
8. 工具非法参数不执行；重复 `call_id` 不重复执行；
9. 工具 timeout、越权路径、网络访问、超大输出隔离失败；
10. budget/deadline 到达后取消剩余调用；
11. ledger 删除、重排、截断或篡改使 seal 失败；
12. `store=true`、未冻结 cache、文件输入、debug 在发送前拒绝；
13. 并发完成顺序改变时 call graph 与归并结果稳定。

## 9. Gate-1 放行条件

- [ ] 轮换所有曾在聊天中出现的 key，只在运行环境外安全注入。
- [ ] 冻结 `arkcli` 版本、二进制/包 hash。
- [ ] 取得 agent-plan model-list 与实际 text resources 原始快照。
- [ ] 所选模型在两者交集；退役模型排除。
- [ ] 冻结 base URL、`/responses` path、registry/discovery hash。
- [ ] 所有 payload 完成本地 dry-run。
- [ ] 人工批准后，每模型只做最小 strict-schema 合成 capability probe。
- [ ] 冻结逐模型参数/工具/缓存能力矩阵。
- [ ] 冻结 Eval、任务、提示、拓扑、synth、预算、timeout、retry、fallback。
- [ ] attempt seal、secret canary 和全部失败注入通过。
- [ ] 对应 data/target Gate 通过。
- [ ] 再次人工批准后才允许正式 rolling experiment。

本协议通过不代表任何模型有效；它只允许开始能力探针。
