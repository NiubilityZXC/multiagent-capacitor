# Canonical Supersession Ledger

**版本**：2026-08-27 15:28:47 +08:00  
**状态**：`PROPOSED / UNAPPROVED / ZERO_CANONICAL_MUTATION`  
**规则**：只有本 ledger 明列的有限条目可在人工批准后解释为 supersession；未列内容一律以 canonical 为准，且 canonical Stop/Go 始终优先。

## 1. Byte-level pins

| Canonical file | Expected SHA-256 | 本轮状态 |
|---|---|---|
| `refine-logs/EXPERIMENT_PLAN.md` | `df968d2e7ba33748043e547165143d9247358afca573946f3dde573c8c04b6d2` | verified read-only |
| `refine-logs/round-3-refinement.md` | `d4d40b0a7e3f5c9030bfe80e5ede3d059673c3b3c96122c9cf050097aa54f110` | verified read-only |

## 2. Latest controlling-directive map

下表不是额外 discretionary supersession，也不修改 canonical bytes；它记录用户最新明确指令与旧文本直接冲突时的强制解释，防止“本 ledger 只有五项”反而使治理要求变得含混。

| Directive topic | Older canonical location affected | Controlling interpretation |
|---|---|---|
| no monetary analysis | `EXPERIMENT_PLAN` §§4、7、B2/B4 metrics、compute/API reporting；`round-3-refinement` cost/value clauses | 不计算/估算价格，不报告cost/Pareto/省钱；attempts/tokens/deadline仅为安全、复现、暴露量和matching事实。 |
| one joint seal/barrier/unseal | `EXPERIMENT_PLAN` P4→P5 sequencing与`round-3-refinement` pilot-gated four-call expansion | Plan A/Plan B全部 admitted cells在同一 generation先完成，再一次 barrier和joint unseal；Plan A结果不能决定是否执行已 admitted Plan B/P5 cells。 |
| B5 independent scheduling | `EXPERIMENT_PLAN` B5 “after Ren claim seal” wording | Patrizi只依其P1 Gate与共同architecture/prompt/contrast seal；不得看Ren outer结果决定是否运行。当前P1失败故机械`B5=NA/BLOCKED`。 |
| ARCH1 finite architecture tournament | canonical明确删除 hierarchy/debate/dynamic route的scope条款 | 仅新增一个 `ARCH1` arm；其内部候选恰为最多3个、fold-local选择。canonical 11 arms不变。 |
| P3 Gate-2 envelope | canonical `3–5 probes/model` | 最新固定为最多5模型、每模型恰3 probes、总≤15、每次96 output tokens；只测capability/schema。 |
| pre-seal baseline adequacy | canonical把独立 literature review主要留到paper claim前 | P2/seal前必须完成一次独立baseline adequacy审查；新增项先提案并另获批准。 |
| Plan A Problem Anchor | canonical/brief原 empirical anchor | Plan A anchor只通过独立 addendum存在；Plan B canonical anchor仍原样保留。 |
| completed P1 evidence and current authority | canonical较早的人工作业门状态 | 当前只读证据固定为 `data/audit/P1_REN_PATRIZI_DECISION_INDEX.json` SHA-256 `69cb57366da92252232bc219eb95ff62084859fede921e582ad2118d0e46fad6`、其 Markdown index SHA-256 `7dea7484b66f1c1af9620a4a0ecd2f27250a798631261a170e32bc15ef0cc7df`，以及 Patrizi/Ren bundle的 `COMPLETE`、manifest、hash-list roots（分别见 master protocol）；二者 scientific eligibility仍 `BLOCKED`。当前只允许只读重验现有 P1、已有 static audit、文档/代码与 offline release review，明确禁止新下载、Ren extraction、新 decoder/parser/author script/repair、P2/P3/API/model/SOH/RUL/P4/P5/outer evaluation。 |

这些治理映射来自用户最新明确指令，不能被实现者扩大。未列的新冲突仍 `BLOCKED_PROTOCOL_AMBIGUITY`。

## 3. Five finite Plan A supersessions

| ID | Canonical topic | Proposed finite supersession | 保持不变的边界 |
|---|---|---|---|
| `S-001` | ARCH1 candidate space | 对 canonical `EXPERIMENT_PLAN` “明确删除/Out of scope”的 hierarchy、debate、dynamic route与 `round-3-refinement` minimal four-call边界做唯一有限扩展：确认性 arm集合为 `11 ∪ {ARCH1}`；`ARCH1`由恰好3个完全具体候选组成的 fold-local selection procedure定义。 | 11臂身份、schema、fallback和局部 contrasts不变；不把3 candidates当3个confirmatory arms；不新增第四候选。 |
| `S-002` | ARCH1 execution scale | `ARCH1` 固定 `k=4`；Ren `4O_RR_API`、Patrizi `4O_PR_API`仅表示 planned/reserved slot count与最大 provider send opportunities。每 slot实际 send为0或1，因此 realized attempts可低于上界；每个 slot仍必须闭合。worker slots、tokens、deadline与attempts进入审计。 | `R_API∈{1,3}`、accuracy no-retry、replicate非独立样本保持。 |
| `S-003` | ARCH1 comparisons | 新增 `ARCH1−N0`、`ARCH1−C_k`、`ARCH1−D1-RAW`及唯一primary operational contrast；无合格`C_k`时协作因果claim机械禁止。 | Plan B 所有 canonical primary/secondary contrasts完整保留。 |
| `S-004` | Joint multiplicity | 用一个覆盖Plan A superiority、Plan A noninferiority、primary operational endpoint与Plan B canonical primary contrasts的joint strong-FWER程序，替代“Plan B primary family单独使用完整α”的解释。 | Plan B 两个 primary contrast定义、unit-level inference与bootstrap骨架不变。 |
| `S-005` | Table placement | Table 2保持numerical floor；Table 3保持one-call anchors；Table 4保留canonical contrasts并增加独立Plan A panel；Table 5在D4-H/D4-X后固定ARCH1 aggregate与worker audit；Table 6固定ARCH1 B5 row（含机械NA/BLOCKED）；Supplement给12-arm consolidated table。 | Canonical Table 2–6语义与五因素contrast matrix完整保留；不把不完整cells称full factorial。 |

本表刻意只覆盖用户允许的五类有限 supersession。Joint seal/storyline trigger、B5排程、无金钱核算和claim ceiling是最新研究指令下的治理约束，由相应独立协议记录；它们不在本 ledger 中被伪装成对 canonical 文本的额外 supersession。

## 4. Explicitly not superseded

- P1 identity/schema/unit/chronology/duplicate/target/censor/split Data Gate。
- Whole-unit outer CV、inner-only selection、common planned/matured keys和physical-unit inference。
- `N0=b_star=FALLBACK`、19-action registry、`DELIBERATE_FALLBACK`/`ERROR_FALLBACK`分离。
- `accuracy_v1` no-retry、late response不可覆盖、physical slot消费语义。
- RUL/ESR/SOH endpoint Gate与不合格时 `NA/BLOCKED`。
- P1/P3/development API/P4/P5的独立人工 Gate与 `AUTO_PROCEED=false`。
- Numerical ground-truth scoring；禁止 LLM judge/self-score。
- P6独立审计通过前不写 performance claim。

## 5. Conflict resolution

1. Canonical Stop/Go最高优先；
2. 用户最新明确禁令（尤其API人工Gate、无金钱核算）优先；
3. 经人工批准并 hash-pinned 的本 ledger 条目只在对应 topic 有限生效；
4. 其他内容回落到两个 canonical 文件；
5. 任何无法唯一解释的冲突均 `BLOCKED_PROTOCOL_AMBIGUITY`，不得靠实现者推断修复。

## 6. Approval record

当前为 `UNAPPROVED`。未来批准必须记录批准时间、被批准的 ledger SHA-256、全部 addendum hashes 与 generation ID；不能仅写“同意最新版本”。

当前 P1 index/bundle roots只是阻断证据，不是新增权限。任何 preseal bundle也必须把本段 `CURRENT_AUTHORITY` 原样绑定；没有新的明确人工批准，不得执行新 archive tool/parser、P2、P3或任何真实预测。
