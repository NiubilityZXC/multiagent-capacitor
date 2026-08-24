# Ark `accuracy_v1` fresh same-family independent review

**日期**：2026-08-24
**审查者**：fresh Codex same-family reviewer（独立只读审查；结论为 provisional）
**范围**：`ark_provider.py`、`provider.py`、`contracts.py`、`ledger.py`、`runner.py`、`test_vfps_ark_provider.py`，以及 canonical `EXPERIMENT_PLAN.md` 与 Gate-2 protocol 中相关合同。
**约束**：未联网、未读取环境变量或凭据、未调用 Ark、未修改产品代码或 tests。

## 明确裁决

**`RELEASE_MOCK_ONLY`**

当前代码可继续用于 mock、fault injection 和本地合同开发；不得据此放行为 offline production candidate、P3/P4 formal execution 或真实 accuracy run。原因是现有执行路径虽有良好的 fail-closed 骨架，但 durable provider evidence 仍可“哈希自洽而语义未绑定”，formal runner 还可接受并提交超过 output-token ceiling 的成功预测，authenticated capability membership 也没有机械验证。

**本裁决不能证明真实 Ark API 可用性、账户/模型可调用性、服务端 schema 行为、真实 exactly-one physical HTTP send，亦不能证明或预测任何电容预测精度。** 所有 87 个测试通过只证明所覆盖的本地行为。

## Blockers（按严重度）

### B1 — CRITICAL：durable Ark evidence 只做局部字段比对与自哈希，未绑定完整冻结语义

`ArkBindingManifest` 声称覆盖 policy/arm/packet/prompt/schema/grammar/registry/decode/provider/model/verifier/fallback/budget/capability/request contract（`experiments/vfps_agent/ark_provider.py:364-425`），但 runner 最终只持久化一个 `binding_manifest_hash`，没有持久化并 seal 可复核的 manifest 内容。`ArkInvocationAudit` 本身没有 grammar/registry/verifier/fallback/request-contract 的可复核内容（`ark_provider.py:479-561`）。

更关键的是，`_closed_result` 对 Ark audit 仅比较 attempt identity、status、time、attempt/retry、usage、resolved-model hash 与 response-ID hash；它没有核对 `binding_manifest_hash`、`prompt_hash`、`response_schema_hash`、`decode_parameters_hash`、`provider_rule_hash`、`model_version_rule_hash`、`one_call_budget_hash`、`capability_snapshot_hash`、request/raw-response binding 等（`experiments/vfps_agent/runner.py:475-527`）。随后它直接把 audit primitive 持久化。`AttemptResult` 和 ledger verifier 只检查 `provider_evidence_hash == hash(provider_evidence)` 与 forbidden-proxy scan，并不重新类型化或交叉验证 Ark evidence（`experiments/vfps_agent/contracts.py:665-670`；`experiments/vfps_agent/ledger.py:461-480, 675-688`）。STARTED 中也只有 opaque `policy_hash`，没有 policy body。

只读诊断从真实 adapter success response 出发，仅替换三个格式合法但错误的 audit hash；runner 仍输出：

```text
status= SUCCESS
error= None
persisted_forged_prompt= True
persisted_forged_schema= True
persisted_forged_capability= True
```

这正是“hash self-consistency but not semantic binding”：后验 verifier 无法证明发送时使用的是获批 prompt/schema/capability/registry，而只能证明一份任意 mapping 没有在自身哈希之后改变。

最小修复：

1. 把完整、typed、canonical 的 `ArkBindingManifest`（或独立 sealed artifact）纳入 run artifacts；phase seal 同时绑定其 bytes/hash。
2. `_closed_result` 必须接收/取得 expected manifest，并逐字段核对 audit 与 policy/attempt/budget/contract；不一致一律 `BINDING_MISMATCH` fallback。
3. ledger 的 typed FINISHED verifier应重建 `ArkInvocationAudit`，验证 outcome-specific invariants，并交叉绑定 STARTED、policy artifact、binding manifest 和 request/response hashes；不能把 `provider_evidence` 当任意 mapping。
4. 增加回归测试：逐一篡改 manifest hash、prompt/schema/decode/model/capability/request hash，要求 durable close 与 sealed phase verification均失败。

### B2 — HIGH：formal runner 可把超过 output ceiling 的 usage 当成功并提交预测

Ark adapter 自身正确地在 `output_tokens > requested_tokens` 时 fail closed（`experiments/vfps_agent/ark_provider.py:800-830`）。但 formal provider contract 是通用 `AccuracyProvider`（`experiments/vfps_agent/provider.py:31-34`），runner 的 `_closed_result` 只检查 input/output tokens 是否为非负整数，从不比较 `response.output_tokens` 与 `attempt.requested_tokens`（`experiments/vfps_agent/runner.py:445-453`）。

完整 `CAPAccuracyRun` 只读临时目录诊断使用 96-token ceiling 和一个返回合法 direct bundle、但报告 97 output tokens 的 `MockProvider`，结果为：

```text
attempt_status= SUCCESS
output_tokens= 97
commit_disposition= PREDICTION
commit_reason= VERIFIED_RESPONSE
```

这违反“invalid/over-ceiling usage fail closed”，也说明 formal runner 的安全性依赖调用者恰好使用 Ark adapter，而类型合同并未保证这一点。

最小修复：在 `_closed_result` 无条件执行 runner-owned usage checks：缺失两字段仍为有效 `UNKNOWN`；任一字段类型/符号非法、只有一半 usage、或 `output_tokens > attempt.requested_tokens` 时，slot 已消费但 status/error 必须闭合为 invalid response并强制 N0 fallback。对携带 Ark audit 的响应，还要核对 audit total/input/output consistency。增加一个 full `CAPAccuracyRun` regression，断言 97/96 不得产生 `PREDICTION`。

### B3 — HIGH：capability snapshot 与 approved model membership 只有任意 hash，没有语义验证；same-version schema 可自洽替换

`ArkModelRule` 只验证 model token 与一个 64-hex capability hash的格式（`experiments/vfps_agent/ark_provider.py:262-279`）；static binding 只验证 policy hash字段与 contract 自己相等（`ark_provider.py:931-952`）。它从未读取或验证 authenticated model-list ∩ text-resource snapshot，也不证明 requested model 是该交集成员。只读诊断用 `unapproved-model` 和任意 `a*64` snapshot hash构造自洽 policy/contract；returned model精确相同后 adapter `SUCCESS` 且发生一次 send。

同样，schema binding 只要求 root object 的 `schema_version.const` 与 arm版本相同（`ark_provider.py:953-962`），而不是绑定 canonical arm schema。现有测试本身用只含 `schema_version` 与 `value` 的 schema 冒充 D1 direct response（`tests/test_vfps_ark_provider.py:47-57`），adapter报 `SUCCESS`；交给真实 arm verifier后才变成 error fallback。runner 的第二层 verifier保护了预测，但 adapter/schema capability evidence会错误声称成功，而且没有 canonical full response-schema artifact进入 durable seal。

最小修复：

1. 引入 typed、detached、canonical capability snapshot artifact，验证 snapshot hash、authenticated intersection、requested model membership与资格状态；将 artifact/seal纳入 policy和run seal。
2. 为每个 arm/permission维护 canonical response-schema bytes/hash registry；adapter只能从 registry按 arm选取，禁止调用者传入任意同-version schema。
3. 保留现有 exact returned string equality（`ark_provider.py:1279-1295`），但把它作为 membership验证之后的第二道 Gate。
4. 加入 arbitrary-model/fake-snapshot、same-version schema swap、H1/RF1 permission schema swap的 pre-send rejection tests。

### B4 — HIGH：STARTED-before-send 顺序正确，但 ledger append 忽略 short write返回值

正常控制流满足 `append_started` 后才 `provider.invoke`（`experiments/vfps_agent/runner.py:1121-1134, 1213-1218`），且 `_append` 在返回前 flush+fsync（`experiments/vfps_agent/ledger.py:318-322`）。然而 `_append` 忽略 `self._stream.write(...)` 的返回字节数（`ledger.py:318-326`）。若 regular-file write短写但不抛异常，fsync只会持久化已写前缀，方法仍推进内存 hash/sequence并返回；runner随后可能发送请求，而磁盘上没有一个可验证的完整 STARTED。seal writer与 runner exclusive writer都正确使用循环，反而凸显 ledger append缺口（`ledger.py:413-420`；`runner.py:307-315`）。

最小修复：把每条 canonical JSONL record变为显式 write-all loop（或严格检查返回长度并继续写），仅在完整 bytes写入且 fsync成功后推进 `_sequence/_previous_hash`。用可注入的 short-write stream回归测试：第一次写 N-1 bytes时不得返回成功、不得允许 provider send。

### B5 — HIGH：adapter保证一次 `transport.send()` 调用，但不能机械证明一次 physical HTTP request/零内部 retry

adapter用锁在调用前消费实例 slot，第二次 invoke会拒绝，且源码只有一个 `transport.send` call（`experiments/vfps_agent/ark_provider.py:1178-1188`）；budget/static binding也强制 one call、zero retry（`ark_provider.py:931-940`）。但 `ArkTransport` 的“不 retry”仅是 Protocol docstring（`ark_provider.py:473-476`）。任意注入 transport可在一次 `send()` 内执行多个 HTTP attempts，adapter的 `physical_attempts==1`仍会声称只有一次。当前 scope内也没有 concrete authenticated transport可审计。

最小修复：正式 release必须审计具体 transport，冻结其 implementation/config hash，关闭 HTTP client自动 retry/redirect/replay，并返回可验证的单-attempt receipt；failure injection要证明内部重试关闭。否则只能声称“一次 adapter send invocation”，不能声称 exactly one physical request。

## Nonblockers / hardening

1. **错误分类被压平。** Ark `INVALID_RESPONSE`、HTTP、transport等在 adapter audit中区分，但 runner只按 generic status把 ERROR映射成 `PROVIDER_ERROR`（`experiments/vfps_agent/runner.py:461-467`），commit通常成为 `PROVIDER_FAILURE`（`runner.py:1241-1254`）。预测会 fallback，安全性尚闭合，但 formal failure table会丢失类别。应从已验证的 `ArkClosedOutcome`机械映射到 closed error/commit reason。
2. **raw response ID虽不落盘，仍逃出 adapter。** success response把 raw ID放入 ephemeral `ProviderResponse.provider_response_id`（`ark_provider.py:1336-1346`；`provider.py:16-28`），runner再哈希（`runner.py:454-459`）。现有 ledger测试证明未持久化（`tests/test_vfps_ark_provider.py:468-491`），所以未发现 durable leak；但 dataclass repr/logging仍有误泄露面。建议 adapter只向 runner传直接 SHA-256，不再暴露 raw ID。
3. **Ark tests不是完整 formal-run integration。** Ark tests直接调用 adapter，并在发送完成后才手工 append STARTED/FINISHED（`tests/test_vfps_ark_provider.py:468-485`）；它没有覆盖 `CAPAccuracyRun -> ArkProviderAdapter -> durable close -> crash/resume -> phase seal`。应增加真实组合测试并在 transport callback里验证 STARTED已经可由独立 fd读取和 typed verify。
4. **两种 response-ID hash域不一致。** audit使用 `sha256(raw_id_bytes)`（`ark_provider.py:1271`），AttemptResult使用 `canonical_sha256({provider_response_id: raw})`（`runner.py:455-458`）。二者都不泄露 raw ID，但应统一命名/域分离，避免后续误比较。

## 逐项结论

| 要求 | 结论 | 证据摘要 |
|---|---|---|
| `accuracy_v1` one-send/zero-retry | **PARTIAL/BLOCKER** | adapter只调用一次 `send`且实例不可重用；transport内部physical retry不可观察（B5） |
| STARTED-before-send | **PARTIAL/BLOCKER** | 控制流顺序与fsync正确；short-write未检查可破坏durable前置（B4） |
| policy/arm/prompt/schema/decode/registry/budget/deadline/model immutable binding | **FAIL** | runtime局部绑定较强，但 durable evidence未复核完整manifest，capability/schema仍可自洽伪绑定（B1/B3） |
| exact returned model | **PASS with prerequisite gap** | exact string mismatch fail closed；approved snapshot membership未验证 |
| local strict envelope + schema | **PASS syntactically / PARTIAL semantically** | duplicate/nonfinite/extra-field/envelope检查严格；canonical arm schema authority未固定 |
| missing usage => valid `UNKNOWN` | **PASS** | adapter保留成功，runner持久化UNKNOWN（`ark_provider.py:1272-1278`; `runner.py:536-548`） |
| invalid/over-ceiling usage fail closed | **FAIL formal runner** | Ark adapter pass；generic formal runner可97/96提交预测（B2） |
| late semantics | **PASS** | late标记并由runner忽略response、提交fallback（`ark_provider.py:1311-1346`; `runner.py:1228-1245`） |
| safe durable evidence | **FAIL** | raw body不落盘，但binding evidence仅自哈希且不可后验语义验证（B1） |
| secret/raw-body/raw-response non-persistence | **PASS in covered path** | transport exception不串联；ledger只存hash/closed data；canary tests通过 |
| crash/resume invariant | **PASS normal writes / BLOCKER under short write** | STARTED/FINISHED/prediction crash恢复均不重发；ledger write-all缺口见B4 |
| response-ID non-persistence | **PASS, harden** | ledger只含hash；raw ID仍在ephemeral object，见nonblocker 2 |

## 执行的 tests 与只读诊断

Focused suite：

```text
PYTHONDONTWRITEBYTECODE=1 .venv-audit-cap/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_vfps_ark_provider.py \
  tests/test_capact_m2_runner.py \
  tests/test_vfps_budget_ledger.py \
  tests/test_vfps_contracts.py \
  tests/test_vfps_evaluator_service.py

87 passed in 6.22s
```

另外执行了三个不改源码/tests的 inline Python diagnostics：

- 篡改成功 Ark audit 的 prompt/schema/capability hashes后调用 `_closed_result`：仍为 `SUCCESS`并持久化伪hash（复现 B1）。
- `CAPAccuracyRun` + valid direct response + `output_tokens=97`/ceiling 96：提交 `PREDICTION / VERIFIED_RESPONSE`（复现 B2）。
- `unapproved-model` + 任意自洽 capability hash + exact same returned model：adapter `SUCCESS`并调用一次 transport（复现 B3）。

## Release boundary

修复 B1–B5并新增相应 full-path regressions之前，唯一诚实的 release标签是 **`RELEASE_MOCK_ONLY`**。即使全部修复并转为 offline production candidate，仍必须通过 Gate-2 的 rotated-secret、人类批准、authenticated discovery、真实 capability probes及 concrete transport audit；这些后续证据也仍不能替代 held-out numeric accuracy evaluation。