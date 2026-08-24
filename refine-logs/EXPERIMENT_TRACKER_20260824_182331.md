# CAP-ACT Experiment Tracker

**版本**：2026-08-24 18:23:31 +08:00
**Canonical plan**：`refine-logs/EXPERIMENT_PLAN.md`
**Policy**：`AUTO_PROCEED=false`；mock PASS不等于科学PASS；真实下载/API/accuracy均需对应人工Gate。
**Status vocabulary**：`COMPLETE_VERIFIED`、`COMPLETE_VERIFIED_MOCK`、`COMPLETE_VERIFIED_LOCAL`、`PARTIAL_VERIFIED`、`PLANNED`、`BLOCKED_*`、`NA`、`KILLED`。

## 本地实现基线

本轮最终执行全仓 CAP suite，executor 得到 `204 passed in 21.18s`；两个 post-fix fresh reviewers 分别得到 canonical full `204 passed`：

~~~text
PYTHONDONTWRITEBYTECODE=1 .venv-audit-cap/bin/python -m pytest -q \
  -p no:cacheprovider tests
~~~

这只支持 M0–M3 本地合同正确性；没有数据/API/accuracy/RUL结果。Ark adapter裁决为 `RELEASE_MOCK_ONLY`；evaluator裁决为严格限定的 `RELEASE_LOCAL_PROCESS_BOUNDARY`；integrated harness仍为 `RELEASE_MOCK_ONLY`。真实实验仍被concrete transport、可信capability provenance、canonical arm schema、全局scoring barrier、真实whole-unit split以及P1/P3人工Gate阻断。

| Run ID | Stage | Purpose | System / Variant | Scope | Metric / Artifact | Priority | Status | Next Gate / Stop |
|---|---|---|---|---|---|---|---|---|
| CAP-M0-001 | M0 | strict packet/direct/action schemas | Raw/Hybrid packets；direct/typed arms | synthetic | duplicate/nonfinite/proxy/complete-key rejection | MUST | COMPLETE_VERIFIED | — |
| CAP-M0-002 | M0 | authority/fallback isolation | H1/RF1/RC1/ACT1/IF1 | synthetic | b_star=N0；RC1=8；数值key ACT1=19/IF1=76,969；受阻RUL=1 | MUST | COMPLETE_VERIFIED | — |
| CAP-M0-003 | M0 | transform contracts | SHIFT/INFLATE | synthetic | units、scale、nested intervals、whole-bundle fallback | MUST | COMPLETE_VERIFIED | — |
| CAP-M0-004 | M0 | no-network/fault surface | mock provider + verifier | local | no network/subprocess/env；tamper fail-closed | MUST | COMPLETE_VERIFIED | M2 E2E |
| CAP-M1-001 | M1 | numerical registry manifest | 6 models + 5 templates + FALLBACK | synthetic | canonical hashes；b_star bytes=N0 | MUST | COMPLETE_VERIFIED | P2 real fitting |
| CAP-M1-002 | M1 | action manifests | PRIMARY19 / COMP96 | synthetic | no comp96 leakage；permissions exact | MUST | COMPLETE_VERIFIED | — |
| CAP-M1-003 | M1 | deterministic selector | ENUM-ACTION19 | synthetic losses | exact argmin、global backoff、cluster SE、tie | MUST | COMPLETE_VERIFIED | P2 loss tables |
| CAP-M2-001 | M2 | durable attempt lifecycle | accuracy_v1 ledger | synthetic | STARTED before provider；no retry；late/crash fallback | MUST | COMPLETE_VERIFIED | M3 provider/evaluator boundary |
| CAP-M2-002 | M2 | blind replay E2E | reveal→commit→maturity→score | synthetic hidden suffix | checkpoint-gated origin+1 reveal；common keys | MUST | COMPLETE_VERIFIED | M3 process evaluator |
| CAP-M2-003 | M2 | maturity denominator | PLANNED/MATURED/NEVER_MATURED | synthetic stream | one execution + one maturity status/key | MUST | COMPLETE_VERIFIED | real eligible targets |
| CAP-M2-004 | M2 | suffix/identity invariance | tainted/private fixtures | synthetic | packet bytes invariant；proxy/canary rejection；tamper kill | MUST | COMPLETE_VERIFIED | real manifest recomputation |
| CAP-M2-005 | M2 | fresh release review | all typed M2 modules | synthetic/mock | 8 blockers adjudicated；130-test checkpoint；same-family provisional | MUST | COMPLETE_VERIFIED | superseded by M3 review |
| CAP-M3-001 | M3 | one-shot Ark request adapter | direct/hybrid API arms | offline injected transport | stateless `/responses` body；one adapter send；exact model；strict local parse | MUST | COMPLETE_VERIFIED_MOCK | concrete transport/P3 |
| CAP-M3-002 | M3 | durable Ark semantic evidence | typed evidence envelope | synthetic | policy/budget/contract/manifest/audit reconstruction；STARTED↔FINISHED | MUST | COMPLETE_VERIFIED_MOCK | authenticated artifact provenance |
| CAP-M3-003 | M3 | usage/write barrier | runner + canonical ledger | synthetic faults | 97/96、partial/invalid usage fallback；short write=no provider send | MUST | COMPLETE_VERIFIED | — |
| CAP-M3-004 | M3 | process evaluator | hidden suffix + IPC | same-UID local | HMAC/nonce/chains；checkpoint-gated reveal；REVEAL crash replay | MUST | COMPLETE_VERIFIED_LOCAL | separate authority/global barrier |
| CAP-M3-005 | M3 | evaluator adversarial repair | FINALIZE/journal/config/error attacks | same-UID local | early FINALIZE zero-label；head rollback detection；closed errors | MUST | COMPLETE_VERIFIED_LOCAL | coordinated rollback/TOCTOU/client loss |
| CAP-M3-006 | M3 | fresh review + post-fix re-review | Ark + evaluator | offline | 204 tests；five review traces；split release verdicts | MUST | COMPLETE_VERIFIED | integrated=`RELEASE_MOCK_ONLY` |
| CAP-P1-000 | P1 | human acquisition approval | Ren + Patrizi scope | human Gate | approved URLs/bytes/licence/storage | MUST | BLOCKED_HUMAN_GATE | no download before approval |
| CAP-P1-001 | P1 | Ren download/integrity | raw.rar | ignored raw storage | length/MD5/project SHA/manifest | MUST | BLOCKED_P1_APPROVAL | CAP-P1-000 |
| CAP-P1-002 | P1 | Ren parser/identity | all reported cells/files | raw rows | device/batch/protocol/chronology/duplicates | MUST | BLOCKED_P1-001 | fail blocks science |
| CAP-P1-003 | P1 | Ren targets/censor | capacitance/SOH/trajectory；RUL conditional | raw rows | units/derivation/reference/EOL/censor gate | MUST | BLOCKED_P1-002 | unsupported=NA |
| CAP-P1-004 | P1 | Ren split/origin freeze | sealed whole-unit outer CV | eligible units | fold hashes、absolute origins/horizons、planned keys | MUST | BLOCKED_P1-003 | no feature/prompt tuning before seal |
| CAP-P1-005 | P1 | Patrizi download/integrity | MAT + information PDF | ignored raw storage | length/MD5/SHA/manifest | MUST-JOURNAL | BLOCKED_P1_APPROVAL | separate approval allowed |
| CAP-P1-006 | P1 | Patrizi schema/target gate | 8 HSC units | raw rows | Ah/IR/EIS/termination；device-strategy confounding | MUST-JOURNAL | BLOCKED_P1-005 | fail→external NA |
| CAP-P2-001 | P2 | six expert fits | last/drift/local/log/KF/ridge | Ren outer-train/nested inner | point/interval OOF records | MUST | BLOCKED_P1 | CAP-P1-004 |
| CAP-P2-002 | P2 | five fusion algorithms | uniform/inverse/simplex-point/simplex-WIS/minimax | nested inner records | fold-local convex weights | MUST | BLOCKED_P2-001 | invalid→exclude algorithm pre-API |
| CAP-P2-003 | P2 | N0/b_star/FALLBACK | nested champion rule | each fold/key | byte-identical champion/fallback hashes | MUST | BLOCKED_P2-002 | no arm-specific fallback |
| CAP-P2-004 | P2 | metric/calibration freeze | MASE/WIS/coverage | train-only | denominator、interval calibration、margins | MUST | BLOCKED_P2-003 | undefined→NO_CONFIRMATORY_POWER |
| CAP-P2-005 | P2 | power and budget cardinality | paired physical units | sealed keys | O_R、power、δ_min、harm margins | MUST | BLOCKED_P2-004 | fail stops API accuracy |
| CAP-P3-000 | P3 | rotated secret human Gate | operator env only | account | no chat/argv/log/repo secret | MUST | BLOCKED_HUMAN_AUTH | do not accept chat key |
| CAP-P3-001 | P3 | authenticated discovery | Ark plan models ∩ text resources | account | raw snapshots、arkcli hash、callable IDs | MUST | BLOCKED_P3-000 | IDs remain provisional |
| CAP-P3-002 | P3 | capability probes | ≤5 authenticated candidates | fixed synthetic schema | exactly 3/model；≤15 calls；96 output tokens；model/usage/latency | MUST | BLOCKED_P3-001 | Gate-2 human approval |
| CAP-P3-003 | P3 | accuracy envelope/human release | B1/T1/R_API/model registry | synthetic evidence | attempts/token/deadline/usage/fallback seal | MUST | BLOCKED_P3-002 | second human approval |
| CAP-P4-001 | P4/B1 | numerical anchor | N0 + all 11 candidates | Ren sealed outer CV | primary/secondary loss、CPU | MUST | BLOCKED_P1_P2 | no API |
| CAP-P4-002 | P4/B2 | direct LLM arms | D1-RAW + D1-PACKET | same Ren keys | paired loss/WIS/failure/tokens/latency | MUST | BLOCKED_P3-003 | both must run |
| CAP-P4-003 | P4/B2 | restricted hybrid arms | H1 + RF1 + RC1 | same Ren keys | same metrics、action/fallback states | MUST | BLOCKED_P3-003 | all must run |
| CAP-P4-004 | P4/B2 | unified hybrid | ACT1 primary19 | same Ren keys | ACT1−N0/D1/ENUM/subsets | MUST | BLOCKED_P3-003 | no comp96 substitution |
| CAP-P4-005 | P4/B2 | deterministic control | ENUM-ACTION19 | same Ren keys | train-risk selector loss/CPU | MUST | BLOCKED_P2 | no API |
| CAP-P4-006 | P4/B3 | representation ablation | IF1 primary grammar | same Ren keys | IF1−ACT1；invalid/fallback | MUST | BLOCKED_P3-003 | claim ceiling=representation |
| CAP-P4-007 | P4/B5 | external one-call stress | N0/D1-RAW/D1-PACKET/ACT1/ENUM minimum | Patrizi separate LOCO | separate paired estimates、scope | MUST-JOURNAL | BLOCKED_P1-006 | never pool with Ren |
| CAP-P5-001 | P5/B4 | homogeneous repeat | D4-H | Ren same keys | 4 workers + componentwise median | MUST | BLOCKED_P3_P4 | ≥1 authenticated model |
| CAP-P5-002 | P5/B4 | heterogeneous roster | D4-X | Ren same keys | 4 distinct workers + same median | MUST-CONDITIONAL | BLOCKED_CAPABILITY | requires 4 authenticated models |
| CAP-P5-003 | P5/B4 | constituent audit | all D4 worker outputs | same attempts | per-model/repeat ability/failure | MUST | BLOCKED_P5-001/002 | diversity claim otherwise banned |
| CAP-P6-001 | P6 | deterministic integrity audit | manifests/ledgers/predictions | all completed runs | hashes、counts、key parity、tamper | MUST | BLOCKED_RESULTS | fail→no claim |
| CAP-P6-002 | P6 | statistical analysis | paired unit differences | Ren；Patrizi separate | bootstrap/Holm/effect/harm gates | MUST | BLOCKED_P6-001 | no origin-level pseudo-n |
| CAP-P6-003 | P6 | results-to-claim | frozen claim matrix | audited outputs | positive/mixed/null/negative scope | MUST | BLOCKED_P6-002 | no LLM judge |
| CAP-P6-004 | P6 | independent novelty/claim audit | paper positioning | local outputs + approved literature audit | no first/novel without evidence | MUST-PAPER | BLOCKED_RESULTS | artifact ceiling if absent |

## Immediate queue

1. M3 离线工程已收口：integrated=`RELEASE_MOCK_ONLY`；不得把 local process boundary 或 mock transport写成生产release。
2. 等待 P1-Ren/P1-Patrizi 独立人工决定；批准前不下载新payload。
3. 等待聊天暴露key完成轮换并从仓库外注入，以及P3精确批准；批准前不做authenticated discovery/probe。
4. P3只允许≤15个strict synthetic probes，并必须审计concrete transport的internal retry/redirect；不使用电容数据。
5. P1通过后先完成row-level Gate与whole-unit manifest重算；随后P2冻结numerical/metric/power。
6. P1/P2/P3均通过且另获P4 spend批准后，才运行真实direct LLM、LLM+专用模型与D4实验。
