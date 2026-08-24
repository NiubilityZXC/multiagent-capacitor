# CAP-ACT Research-Refine Pipeline Summary

**日期**：2026-08-24 18:23:31 +08:00
**Final Method Thesis**：在 sealed whole-unit outer CV 中，以 common planned keys、19-action typed authority、共同 numerical fallback 和可审计 API envelopes，因子化比较 direct LLM、LLM+专用数值模型、deterministic selector 与最小 four-call roster，从而得到正、混合、空或负的电容在线预测实证结论。
**Final Verdict**：`REVISE`；M3 integrated=`RELEASE_MOCK_ONLY`，evaluator=`RELEASE_LOCAL_PROCESS_BOUNDARY`（honest-launcher/local only）；scientific execution=`BLOCKED`；paper=`NOT READY`。
**Canonical proposal**：`refine-logs/round-3-refinement.md`。

## Final Deliverables

- Experiment plan：`refine-logs/EXPERIMENT_PLAN.md`
- Experiment tracker：`refine-logs/EXPERIMENT_TRACKER.md`
- Pipeline summary：`refine-logs/PIPELINE_SUMMARY.md`
- M3 code review：`refine-logs/EXPERIMENT_CODE_REVIEW.md`
- Proposal source（本轮未修改）：`refine-logs/round-3-refinement.md`
- `FINAL_PROPOSAL.md`未修改；M3代码、tests、README、MANIFEST和ARIS traces已更新。

## Planning Gate

| Question | Frozen answer |
|---|---|
| 原始问题是否保留 | 是；直接回答 Agent 是否提高 strictly causal held-out forecast |
| Dominant contribution | matched-budget empirical Agent-architecture study |
| Supporting contribution | CAP-ACT reproducible harness与failure/maturity evidence |
| Primary authority | 19 syntactic Actions；`b_star=FALLBACK=N0`；RC1=8；ACT1=19 |
| Evaluation | single-batch sealed outer whole-unit CV；无全局 untouched shadow误称 |
| External | Patrizi separate-domain/confounded stress；不与Ren池化 |
| Rejected complexity | primary COMP96、ACT4、REFLECT、hierarchy、debate、dynamic route、LLM judge |
| Frontier necessity | LLM direct forecast/controller必须与ENUM/N0比较；不增加新frontier module |

## Must-Prove Claims

1. **C1 — one-call Agent value**：D1-RAW 与 ACT1 相对 N0 的 paired whole-unit效果必须完整运行并允许 positive/mixed/null/negative。
2. **C2 — factorization and scope**：information、typed-authority package、deterministic selector、permission union、IF representation、four-model roster与外域scope必须按局部claim matrix解释。

## Five Core Blocks

1. **B1**：Ren eligible data + six experts/five fusions/N0。
2. **B2**：N0、D1-RAW、D1-PACKET、H1、RF1、RC1、ACT1、ENUM-ACTION one-call anchor。
3. **B3**：information/permission/controller/IF representation isolation。
4. **B4**：minimum D4-H/D4-X four-call envelope。
5. **B5**：Patrizi external-domain + final operational/fault boundary。

## Stage Map

| Stage | Meaning | Current status | Hard Gate |
|---|---|---|---|
| M0 | mock schemas/actions/faults | COMPLETE_VERIFIED | deterministic tests |
| M1 | registry/19-action/ENUM | COMPLETE_VERIFIED | manifest/hash tests |
| M2 | blind replay | COMPLETE_VERIFIED (mock only) | typed end-to-end replay、maturity、crash/no-resend |
| M3 | Ark provider + evaluator boundary | integrated RELEASE_MOCK_ONLY；evaluator LOCAL_PROCESS_BOUNDARY | 204 tests；concrete transport、external authority和global barrier仍pending |
| P1 | new data download/audit | BLOCKED_HUMAN_GATE | Ren/Patrizi row-level Data Gates |
| P2 | numerical baselines/Eval/power | BLOCKED_P1 | N0/metric/power seal |
| P3 | authenticated Ark capability | BLOCKED_HUMAN_AUTH | rotated env credential + two approvals |
| P4 | all one-call arms | BLOCKED_P1_P2_P3 | complete common-key ledger |
| P5 | D4-H/D4-X | BLOCKED_CAPABILITY/P4 | four-call registry/budget |
| P6 | audit/results-to-claim | BLOCKED_RESULTS | independent numeric/integrity audit |

## Next executable work

1. 保持真实run为零；M0–M3本地实现、对抗审查和post-fix re-review已完成。
2. 等待P1-Ren/P1-Patrizi独立批准；收到批准前不下载。
3. 等待聊天暴露credential完成轮换并从仓库外注入，以及P3 Gate-2精确批准；收到批准前不做authenticated discovery/probe。
4. P3若获批，只执行冻结的synthetic probes与concrete transport审计；不使用电容数据，也不授权P4 accuracy。

## Human Gates

- **P1 acquisition**：分别批准 Ren 2,114,703,017-byte payload 与 Patrizi 225,986,697-byte MAT + 397,625-byte PDF。
- **P3 credential/capability**：所有聊天中出现过的key作废并轮换；只从operator-controlled environment注入。所有Ark model IDs在authenticated plan/resources交集与3–5次synthetic probes前均为provisional。
- **P4 formal spend**：依据 \(O_R,O_P,R_{API},B_1,T_1\) 的机械预算再次批准。

## Main Risks and Mitigations

- **Data Gate失败**：停止科学实验；不以Benchmark-L/Stress-2替代。
- **Metric/power不足**：输出 `NO_CONFIRMATORY_POWER`；不花真实API预算救结果。
- **API/model drift**：requested/returned mismatch即fallback或新generation。
- **Transport hidden retry**：P3必须使用可审计concrete transport并禁用retry/redirect；adapter method-count不冒充physical-send count。
- **Evaluator authority**：local process boundary不冒充secure isolation；formal run前需global generation barrier和独立writer/label authority。
- **Direct output token burden**：compact fixed-order bundle；requested与actual spend分报。
- **Fallback掩盖**：DELIBERATE与ERROR分离；planned-denominator为主。
- **Roster ability confounding**：报告D4每个worker；只称roster effect。
- **Adaptive outer reuse**：全部fold单批seal，完成前不开score。

## Best Next Action

停在 **P1/P3 human checkpoint**。用户可独立批准Ren、Patrizi或P3 synthetic capability gate；任何真实电容预测仍需Data Gate、真实whole-unit split重算、P2 numerical/power seal、P3 capability与另一次P4 spend批准全部通过后，才进入 `/run-experiment`。
