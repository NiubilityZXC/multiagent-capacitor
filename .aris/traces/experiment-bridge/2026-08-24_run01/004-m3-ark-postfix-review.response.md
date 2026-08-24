# Ark post-fix fresh re-review

审查日期：2026-08-24
审查范围：`experiments/vfps_agent/{ark_provider,provider,contracts,ledger,runner}.py`、`tests/test_vfps_ark_provider.py` 及其直接 formal runner/ledger contract。审查为离线、只读；未读取环境变量或凭据，未调用 Ark，未修改产品代码或测试。

## 裁决

**RELEASE_MOCK_ONLY**

本轮没有发现新的、独立于原 B1–B5 的 critical blocker。B1、B2、B4 已修；B3 的离线 typed capability、精确交集/成员关系以及 formal schema fallback 已修，但真实认证 artifact provenance 仍只能由 P3 实证；B5（concrete transport 内部是否发生重试/重定向/二次物理发送）仍未修，因此不能裁决为 `RELEASE_OFFLINE_PRODUCTION_CANDIDATE`。

此裁决**不能证明真实 Ark API 可用性、真实认证/权限、concrete transport 的 exactly-one physical send，也不能证明预测精度**。Mock 与本地 formal tests 不能替代 Gate 中的 P3 真实调用证据。

## Blocker

### B5 — 未修：adapter 只能证明调用了一次 `transport.send`，不能证明 concrete transport 只做了一次物理发送

- `ArkTransport` 仍只是 protocol；其契约文字要求一次物理请求，但没有可验证的 retry/redirect/connection-replay receipt（`experiments/vfps_agent/ark_provider.py:522-525`）。
- adapter 在锁内只调用一次 `self._transport.send(...)`，并只把自身计数器加一（`experiments/vfps_agent/ark_provider.py:1667-1674`）。一个恶意或普通带内部 retry 的 transport 可以在这一次方法调用里发两次，adapter 仍报告成功和一次 attempt。
- 独立只读诊断用 transport 的单次 `send()` 模拟两个 hidden physical sends，得到：`B5=SUCCESS adapter_attempts=1 hidden_physical=2`。这复现了原 B5，而不是 mock 可以关闭的证明缺口。

最小修复建议：把 concrete transport 纳入受审实现与 immutable binding；显式禁用 SDK/client retry、HTTP redirect 与可重放中间层；让 transport 返回可校验的单物理发送 receipt/attempt count，并在 adapter、typed evidence 和 ledger verifier 中 fail-closed 校验 `physical_attempts == 1`。增加一个内部重试 transport 的负测，要求 adapter/formal runner 拒绝，而不是成功提交。

## 原 B1–B5 复核

### B1 — 已修：typed evidence 不再只是 self-consistent hash；formal ledger 逐字段重建并交叉 STARTED/FINISHED

- `ArkProviderEvidenceEnvelope` 携带并重建 policy、budget、request contract、binding manifest 和 audit；构造时重新计算机械绑定，不信任提交者自报 hash（`experiments/vfps_agent/ark_provider.py:909-1046`）。
- typed parsers 对嵌套结构做严格重建/round-trip；manifest 绑定 policy/arm/prompt/schema/decode/registry/budget/deadline/model（`experiments/vfps_agent/ark_provider.py:706-906`）。这关闭了 schema swap、prompt/decode/model artifact 换绑后再自洽重哈希的原漏洞。
- runner 从 provider response 重建 envelope，并和预期 policy/budget、audit、content、usage、model、时序及 ephemeral hashes 逐项比对；任一不一致闭合为 `ERROR/BINDING_MISMATCH`（`experiments/vfps_agent/runner.py:528-655`）。
- ledger 在读取/恢复时重建 typed envelope，并把 FINISHED evidence 同对应 STARTED attempt、FINISHED result 交叉校验（`experiments/vfps_agent/ledger.py:474-502`, `experiments/vfps_agent/ledger.py:650-725`）。
- 负测覆盖 attempt 字段、ephemeral hash 以及 policy/budget/manifest/audit/prompt/decode/provider/model artifact/schema 的 post-hoc tamper（`tests/test_vfps_ark_provider.py:512-597`）。独立诊断结果：运行时 tamper 为 `ERROR BINDING_MISMATCH`；即使重算 evidence hash 和 ledger record hash，resume verifier 仍拒绝：`B1_ledger=REJECTED`。

结论：原 B1 已修。这里的“已修”指本地机械/语义绑定与 durable resume verifier，不代表远端 artifact 的真实性已经得到认证。

### B2 — 已修：usage 由 formal runner fail-closed，97/96、partial、invalid 都进入 CAP fallback

- runner 只接受 input/output 两项同时存在、为非负整数且 `output_tokens <= requested_tokens`；partial、布尔值、负数和 over-ceiling 全部归一为 `ERROR/INVALID_RESPONSE`、`UNKNOWN` usage（`experiments/vfps_agent/runner.py:465-526`）。
- 因为只有 `SUCCESS` 且非 late 才执行 provider action，其余路径走 fallback，所以无效 usage 不会 commit provider decision（`experiments/vfps_agent/runner.py:1332-1347`）。
- formal tests 明确覆盖 97/96、partial、bool、negative，并验证 `FALLBACK` 和 sealed phase（`tests/test_capact_m2_runner.py:301-337`）。
- 独立诊断结果：`B2_97_over_96=ERROR INVALID_RESPONSE FALLBACK`；`B2_partial=ERROR INVALID_RESPONSE FALLBACK`。

missing usage 保持合法：两项都缺失时为 `UNKNOWN`，不会伪造 token 数；invalid/over-ceiling 则 fail-closed。原 B2 已修。

### B3 — 部分修：离线 exact intersection/membership 与 formal weak-schema fallback 已修；真实认证 provenance 尚未证明

- `ArkCapabilitySnapshot` 是 typed snapshot；要求候选集合排序非空，且 eligible IDs 必须等于 authenticated model IDs 与 authenticated text resource IDs 的精确交集（`experiments/vfps_agent/ark_provider.py:265-301`）。
- `ArkModelRule` 要求请求 model 是该精确 eligible 集合成员，响应 model 必须精确相等（`experiments/vfps_agent/ark_provider.py:304-328`）；provider 在响应解析时再次执行 exact returned-model check（`experiments/vfps_agent/ark_provider.py:1765-1774`）。对应构造负测在 `tests/test_vfps_ark_provider.py:600-610`；独立诊断为 `B3_intersection=REJECTED`、`B3_membership=REJECTED`。
- adapter 的本地 weak schema 仍只做 version/shape 级接受（`experiments/vfps_agent/ark_provider.py:1788-1792`），但 formal runner/verifier 会拒绝同版本弱语义输出并走 `FALLBACK/INVALID_RESPONSE`；canonical test 覆盖这一边界（`tests/test_capact_m2_runner.py:387-488`）。这是“adapter 可解析、formal verifier 不 commit”的预期防线。

仍未证明的是 capability snapshot 所称“authenticated”数据确实来自 P3 的真实控制面/认证来源；当前 typed object 只能保证输入后的精确集合语义，不能自行证明来源真实性。因此原 B3 的本地 mechanics 已修，真实 provenance 部分仍开放，不能由 mock 替代。

最小后续要求：P3 保存可验证、脱敏的 authenticated model/resource artifact 及其 provenance，把其 digest 纳入现有 manifest；由独立 verifier 重算 exact intersection，并证明请求 model 当时确属成员。

### B4 — 已修：ledger short-write 会在 send 前失败

- ledger append 使用 write-all 循环，拒绝非整数、零或越界 write count；仅在完整写入、flush、fsync 后才推进内存状态（`experiments/vfps_agent/ledger.py:300-339`）。
- runner 在 provider invoke 前 durable append STARTED（`experiments/vfps_agent/runner.py:1239-1248`, `experiments/vfps_agent/runner.py:1323`）。因此 STARTED 的 partial write/stall 抛错时不会进入 send。
- short-write formal test 验证 ledger 状态未推进、provider attempts 为 0（`tests/test_capact_m2_runner.py:340-384`）。

原 B4 已修；同时满足 STARTED-before-send 和 crash/resume invariant。

### B5 — 未修

见上方唯一 blocker。对 Python adapter 的 exactly-one method call/zero retry 已证明；对 concrete transport 的 exactly-one physical send 未证明。

## 其余指定安全性质

- **local strict envelope/schema**：provider 严格解析响应 envelope，并做 exact returned-model、content 与 usage 约束；formal verifier 对弱语义同版本 schema 仍 fail-closed（`experiments/vfps_agent/ark_provider.py:1727-1792`, `experiments/vfps_agent/runner.py:445-655`）。
- **late semantics**：result 的时序/late 与 typed evidence 交叉校验；late response 不执行 provider action而走 fallback（`experiments/vfps_agent/runner.py:445-655`, `experiments/vfps_agent/runner.py:1339-1347`）。
- **safe durable evidence**：成功路径不持久化 provider raw response ID，只保留 SHA-256；evidence 中是结构化字段和 hashes（`experiments/vfps_agent/ark_provider.py:1836-1853`）。
- **secret/raw-body/raw-response/raw-ID non-persistence**：success/error tests 检查 raw body、response ID、Authorization/secret canary 不进入 ledger（`tests/test_vfps_ark_provider.py:483-509`, `tests/test_vfps_ark_provider.py:613-664`）。未发现 response ID 明文泄漏分支。
- **异常分支闭合**：evidence、usage、model、schema、timing、ID/hash 任一不一致均归入 formal error/fallback，未发现可绕过到 provider action 的新分支（`experiments/vfps_agent/runner.py:445-655`, `experiments/vfps_agent/runner.py:1332-1347`）。

## 测试与只读诊断

执行命令：

```text
PYTHONDONTWRITEBYTECODE=1 .venv-audit-cap/bin/python -m pytest -q -p no:cacheprovider tests/test_vfps_ark_provider.py tests/test_capact_m2_runner.py tests/test_vfps_budget_ledger.py tests/test_vfps_contracts.py
```

结果：`101 passed in 3.96s`。

Canonical project test command：

```text
PYTHONDONTWRITEBYTECODE=1 .venv-audit-cap/bin/python -m pytest -q -p no:cacheprovider --import-mode=importlib tests
```

结果：`204 passed in 23.95s`。

另执行未落盘的只读 Python harness，分别篡改 typed evidence、重哈希 ledger、注入 97/96 和 partial usage、构造错误 capability intersection/membership，并模拟 transport 内部二次发送。关键输出：

```text
B1_runtime= ERROR BINDING_MISMATCH
B1_ledger=REJECTED
B2_97_over_96= ERROR INVALID_RESPONSE FALLBACK
B2_partial= ERROR INVALID_RESPONSE FALLBACK
B3_intersection=REJECTED
B3_membership=REJECTED
B5= SUCCESS adapter_attempts 1 hidden_physical 2
```

## 最终结论

Post-fix 代码已经关闭原 B1、B2、B4，并关闭 B3 的本地 typed/mechanical enforcement 与 formal schema-commit 漏洞；没有发现新的同等级本地 blocker。B5 仍然使“真实链路 exactly-one physical send/zero retry”不可证，B3 的 authenticated provenance、真实认证/API 可用性以及预测精度也仍需 P3。因此最终且唯一合适的裁决是：**RELEASE_MOCK_ONLY**。