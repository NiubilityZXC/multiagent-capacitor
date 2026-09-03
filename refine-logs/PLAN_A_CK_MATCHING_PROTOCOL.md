# Plan A `C_k` Matching and Selection Protocol

**版本**：2026-08-27 16:05:00 +08:00  
**状态**：`PRESEAL_PROPOSAL / UNAPPROVED / NO_RESULTS`  
**目的**：确定 `ARCH1` 的唯一同执行包络 control；不能用 outer 结果挑 control

## 1. Estimand boundary

`C_k` 是每个 outer fold 内，从 Plan B canonical 11 arms 中按本协议确定的唯一执行包络 control。它用于区分“完整 ARCH1 package 有效”与“协作结构在匹配条件下有增量”。`C_k` 不是按 outer performance 选出的最强对手，也不替代 numerical champion `N0`。

若没有合格 control：

- 记 `C_k=NA_NO_MATCH`；
- 仍执行并报告已 sealed 的 `ARCH1`；
- `ARCH1−C_k` 与 primary operational contrast机械 NA；
- 禁止声称协作结构、角色、节点、边、debate 或 routing 造成增益；
- 只能讨论 `ARCH1` full-system/package 相对 N0 和其他已冻结 anchors 的结果。

## 2. Matching dimensions

每个 outer fold、每个实际选中 ARCH1 candidate，逐一扫描 11 canonical arms。所有 hard dimensions 必须同时通过；不做加权“总体接近”。

| Dimension | Hard caliper | Evidence |
|---|---|---|
| physical slots | 与 ARCH1 同为每 origin/replicate 恰好 `k=4`；reserved/started/consumed语义一致 | sealed slot manifest + attempt ledger schema hash |
| visible data | data-section canonical bytes及其 hash完全相同；同 prefix、features、numerical candidates与 identity redaction | request packet hash decomposition |
| external context | 均为 none，或同一 frozen context artifact hash | tool/context registry |
| model capability | requested model rule与 returned model roster multiset一致；同 homogeneous/heterogeneous结构 | authenticated model registry + fold-local mapping |
| role-independent model exposure | 每个 physical slot接收的可见 data bytes一致；role instructions可以不同但须单独报告 | per-slot data hash |
| tools | tool allow/deny map完全相同；本研究 formal candidates默认全部关闭 | tool-policy hash |
| requested ceiling | total `B_ARCH`完全相同；per-slot ceiling multiset完全相同 | request manifest |
| deadline | workflow deadline与slot sub-deadline schedule完全相同 | deadline policy hash |
| decode | temperature/top-p/max-output/seed/support policy完全相同；不支持字段同样省略 | decode hash |
| retry/late | accuracy no-retry、ambiguous consumption、late discard与closure规则完全相同 | transport policy hash |
| cache/store/session |均关闭或完全相同；不得让某臂获得跨 origin memory | provider policy hash |
| fallback |同一个 `N0=b_star=FALLBACK` object、相同 planned denominator与状态定义 | fallback bundle/schema hash |
| validator | target/unit/quantile/schema validator相同；不得只对 ARCH1宽松 | validator executable hash |
| time block |同 unit/origin block内随机化/轮转，服务时段平衡 | arm-order manifest |

以下不是允许放宽 hard caliper 的理由：实际 token 偶然接近、同模型家族但不同 returned ID、相同字段名但 data bytes不同、平均 deadline相近、或 fallback 数值事后相等。

## 3. Candidate-specific likely controls

这只是 seal 前的预期审计路线，不预判资格：

| ARCH1 candidate | 首先审计 | 主要失败风险 |
|---|---|---|
| `A01-HIER-VERIFY-4H` | `D4-H` | role artifact使后续slot可见信息增加；若 D4-H 无相同 artifact envelope，则 packet mismatch |
| `A02-PAR-DEBATE-4X` | `D4-X` | adjudicator看到前三个输出，而 fixed local median control没有同等第四-slot输入/authority |
| `A03-TYPED-ROUTE-4X` | 所有11臂，预期很可能无匹配 | hybrid numerical candidate信息与四调用typed route在 canonical arms中可能不存在 |

“首先审计”不等于自动合格。尤其是 A02 与 D4-X：虽然均为四个异构模型调用，但一个是3 proposal+1 adjudicator，一个是4 independent proposals+local median；只有当 model roster、总 ceiling、data exposure、slot权限与 deadline 的预冻结 caliper全部满足，才能将其视为执行包络 control。该比较仍只识别完整 orchestration package，而不单独识别某条边。

## 4. Eligibility ledger

每个 `outer_fold × selected_candidate × canonical_arm` 生成一行：

```text
generation_id
outer_fold_id
candidate_id
control_arm_id
dimension_name
arch_value_hash
control_value_hash
hard_match {PASS,FAIL,NA}
reason_code
evidence_artifact_hash
reviewer_signature_hash
```

先完成全部 dimension rows，再生成 arm-level `ELIGIBLE/INELIGIBLE`。不允许只保存最终 winner 而丢弃被拒 control。

## 5. Mechanical selection when multiple controls qualify

若同 fold 有多个 eligible controls：

1. 只使用该 outer fold 的 outer-training units；
2. 对每个 eligible arm 使用与 ARCH tournament 相同的 inner whole-unit CV/common development keys；
3. unit 内先聚合 matured planned keys，再跨 unit 等权宏平均 MASE；
4. 排除 schema/deadline/WIS/failure/reliability gate不合格者；
5. 取 MASE 最小者；`abs(diff)<1e-12` 视为 machine tie；
6. tie 按冻结顺序 `N0 < D1-RAW < D1-PACKET < H1 < RF1 < RC1 < ACT1 < IF1 < ENUM-ACTION < D4-H < D4-X` 取小；
7. outer held-out loss、rank、suffix或terminal information完全不可见。

control选择优先复用已在 development lane中为相同 fold/key/model/policy hash形成的合法 inner-CV records；任何缺失 record所需的额外真实调用必须预先进入 `N_dev`逐 slot manifest，不能在看到候选分数后补调。最终每 fold输出唯一 `C_{4,f}`，并报告各 arm的 eligibility、training-side score与选择频率。不同 outer folds可以有不同 control；选择程序必须相同。

## 6. Paired inference

`ARCH1−C_{4,f}` 是预先定义的 fold-varying composite-policy contrast，只能在同一 physical unit 的 common matured planned keys 上形成 paired difference。若任一 required fold `C_{4,f}=NA_NO_MATCH`，整个 Plan A control-based primary slot固定 `status=NA_NO_MATCH,p=1`，不得删除该 fold、用另一 fold control补位或形成 subset confirmatory estimate；完整 mismatch范围仍报告。由 capability/matching导致的 NA 在 seal 时确定，不得根据返回成功率重建样本。

accuracy与primary operational endpoint分别形成冻结 contrast，但共享 joint multiplicity family。API replicate只在 unit内聚合，不能作为独立样本。

## 7. Optional `ARCH0-SHAM` design — not admitted

若 11 arms 中没有合格 `C_k`，可提交以下可选方案供用户另行批准：

- 保留与选中 ARCH1完全相同的四个 model slots、model/role prompts、packet bytes、total/per-slot ceiling、deadline、decode、tool policy、fallback与随机化；
- 阻断所有跨角色 artifact content，仅传固定大小、固定 schema、与 parent hash绑定的 `SHAM_NO_INFORMATION` artifact；
- 最终输出使用在 development前冻结的 local aggregation，不让第四角色看到 proposal content；
- physical attempts仍为4，失败分母完全相同。

该 sham 旨在隔离 artifact exchange/orchestration，但可能改变可见信息与角色任务，因此仍需独立科学审查。它目前是 `OPTION_NOT_AN_ARM`：没有用户单独批准，不得添加到 candidate tournament、confirmatory arm set或 master seal。

## 8. Audit verdict codes

- `CK_ELIGIBLE_UNIQUE`
- `CK_ELIGIBLE_SELECTED_INNER_CV`
- `CK_NA_CALL_MISMATCH`
- `CK_NA_PACKET_MISMATCH`
- `CK_NA_ROSTER_MISMATCH`
- `CK_NA_PERMISSION_MISMATCH`
- `CK_NA_CEILING_DEADLINE_MISMATCH`
- `CK_NA_FALLBACK_OR_RETRY_MISMATCH`
- `CK_NA_NO_MATCH`
- `CK_BLOCKED_LEDGER_INCOMPLETE`

任何未覆盖或无法唯一解释的差异均归为 `CK_BLOCKED_LEDGER_INCOMPLETE`，不是“近似匹配”。

## 9. Current gate

`UNAPPROVED / BLOCKED_P1_REN / NO_API`。当前没有 fold、实际模型 roster 或 `C_k` 结果；本文件只给出未来审计程序。
