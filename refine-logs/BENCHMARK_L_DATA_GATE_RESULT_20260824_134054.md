# Benchmark-L P1 Reference-aware Data Gate 结果

**执行时间**：2026-08-24 13:21–13:39 +08:00  
**执行范围**：5.04 GB archive re-verification、ES10/12/14 reference-aware parsing、Data Gate；未运行模型、RUL 或 API。  
**生成器裁决**：`FAIL`  
**独立 bundle verifier**：`PASS`  
**下游裁决**：Benchmark-L modeling、capacity、ESR/SOH、RUL 均继续 `BLOCKED`。

## 机械对账

- 24 个 provisional EIS labels × 73 events = 1,752 event slots；
- 9,316 raw Header/Data slots = 8,835 eligible nonempty + 481 paired canonical empties + 0 quarantine；
- condition nonempty：ES10 2,981，ES12 2,921，ES14 2,933；
- raw matrix shapes：8,834 个 `(18,59)`，1 个 `(18,58)`；
- EIS nonfinite：0；exact EIS matrix duplicate candidates：0；
- raw-order nonchronological unit-events：ES10 16、ES12 13、ES14 10；Header/Data 已先配对再按 acquisition time 稳定排序；
- 46 个 transient VL/VO arrays；
- duplicate candidate：ES12 与 ES14 的 transient timestamp 序列完全相同，身份含义未决，不生成 split group。

## Gate 结果

| Scope | Status | 含义 |
|---|---|---|
| Source bytes | PASS | ZIP/MAT SHA、CRC、size、HDF5 open 与 integrity manifest 一致 |
| EIS references | PASS | 9,316 raw slots 完整对账 |
| EIS columns/frequency | PASS | 20→18 column mapping；保留 58/59 行与 51-point positive-frequency sweep |
| EIS acquisition chronology | PASS | 8,835 timestamps 均解析，0 ties；pair-before-sort |
| EIS causal availability | BLOCKED | `Saved on` 为空；finish 只能由 start + max(time/s) 推断 |
| ES10 transient time | FAIL | 1 次 reversal；minimum gap ≈ −11,880 s |
| ES12 transient time | BLOCKED | 77,241 timestamps 与 77,237 signal rows 不一致；不截断/插值/修复 |
| ES14 transient time | PASS | 77,241 rows，chronology pass |
| Transient missingness | PASS | 全部 VL/VO 的 chunked content 与 NaN mask 已审计 |
| Physical identity | BLOCKED | 无稳定 serial/board/batch/replacement/reuse 证据 |
| Content duplicates | BLOCKED | ES12/ES14 timestamp exact duplicate candidate 未解决 |
| Capacity target | BLOCKED | Cs/Cp 只是 raw observables；频点、replicate、物理 target 规则未冻结 |
| ESR/SOH target | BLOCKED | Re(Z) 不能直接改名 ESR；缺 ESR fit、R0、SOH 规则 |
| Outcome/RUL | BLOCKED | 无 termination/censor/EOL 语义；sequence end 不是 EOL |
| Deterministic reproduction | BLOCKED | 当前只有一次 sealed run |

因此，`FAIL` 是预注册数据语义防线正常工作，不是 parser 工件损坏。结构解析成功不得升级为 target 或建模资格。

## 独立 verifier

独立 verifier 未导入生成器，验证了 21-file bundle、manifest/hash/COMPLETE、四路 lineage、CSV schema/rows、gate status precedence 和 golden real-data counts：

```json
{
  "verification_status": "PASS",
  "bundle_status": "FAIL",
  "artifact_file_count": 21,
  "scientific_artifact_count": 18,
  "gate_scope_count": 15,
  "benchmark_l_modeling": false,
  "rul": false
}
```

## 关键工件哈希

- `ARTIFACT_MANIFEST.json`: `432b51b1c5615c0c5f6237c747f89fa73e93bf49b61c4d36b70a43c025cfc70c`
- `COMPLETE.json`: `4a0283a3cf4c59b29afad9176ddb540af6ea79d7e1da49efd9fd58adbe5a1b07`
- `DATA_GATE_SUMMARY.json`: `f023295e7bd0bae3db60899f1a198ded4a6404551eeff72ac5686213db0aafa5`
- `DATA_GATE_REPORT.md`: `a2452433338a76f19402d1a5be64d5ec18d3aea87b5ef6d18a3505f1d75d30ca`

本地 bundle：`data/audit/NASA/capacitor_electrical_stress/p1_20260824_132100/`。

## 对 Agent 研究的影响

1. Benchmark-L 不能用于当前 direct LLM、multi-agent 或 hybrid 精度实验；
2. Stress-2 仍只用于 pipeline/scorer/API shadow sanity；
3. 高水平方法论文需要额外公开/获授权的独立电容 corpus，或先解决 physical identity、target construction、time repair 和 outcome semantics；
4. RUL 在所有当前大包 Agent arms 中必须为 `NA`；
5. 允许继续 no-network architecture/failure tests 和合成 capability probe 设计，但真实预测实验仍需独立 human/API Gate。
