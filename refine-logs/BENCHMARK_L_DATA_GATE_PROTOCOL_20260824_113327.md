# Benchmark-L P1 Reference-Aware Parser 与 Data Gate 合同 v1.0

**冻结时间**：2026-08-24 11:33:27 +0800  
**范围**：仅解析、审计、隔离与 Data Gate；禁止模型、RUL、正式 Design Gate、Freeze B 与 Agent 拓扑评测。  
**输入**：冻结 SHA-256 的 `ES10.mat`、`ES12.mat`、`ES14.mat` MATLAB v7.3/HDF5 文件。

## 1. 状态语义

每个状态必须绑定 `(gate_id, scope_id)`：

- `PASS`：该 scope 的全部强制断言通过，原始记录完全对账，没有相关 unresolved quarantine。
- `AMBER`：解析或审计完成，可用于 parser 开发或描述性报告；不解锁正式建模。
- `FAIL`：观察到违反合同的事实，例如引用错配、静默截断、未对账丢行或未来依赖。
- `BLOCKED`：所需证据不存在、尚未执行或无法从当前数据识别。

聚合优先级为 `FAIL > BLOCKED > AMBER > PASS`。只有目标 scope 的全部依赖为 `PASS` 且获得新的人类批准，才允许进入下一阶段。

## 2. 冻结机械常量

- 24 个 provisional EIS labels × 73 events = 1,752 个 event slots。
- 8,835 个非空 EIS matrices：ES10/ES12/ES14 分别为 2,981/2,921/2,933。
- 23 个 transient labels、46 个 VL/VO arrays；ES10C8 是 EIS-only。
- ES10 transient：75,826 timestamps 与 signal rows；ES12：77,241 timestamps、77,237 signal rows；ES14：77,241 timestamps 与 signal rows。
- 20 个原始 column tokens 只能合并 `cycle + number`、`I + Range`，得到唯一 18-column schema。
- Header/Data 必须先按 raw replicate index 配对，再按 acquisition time 稳定排序。
- event aggregation 的 causal-availability candidate 取纳入 replicate 的最大 acquisition-finish candidate；若 finish 只能由 start + `max(time/s)` 推导，证据等级保持 inferred。
- EIS Reference Table 第四字段只能叫 `elapsed_like_raw`，不得命名为 hours、aging time 或 RUL time。
- 路径、文件名、原始 header、HDF5 reference name、condition/unit label 全部是 provenance-only 禁用特征。

计数不符时必须 `FAIL`，除非先发布合同修订版并重跑；不得在结果阶段临时解释。

## 3. Reference-aware parser 规则

1. 只访问 allowlist 路径；拒绝 symlink 输入、HDF5 external storage、VDS、坏引用、超出资源上限的 char/matrix/cell。
2. 每个 outer Header/Data/ColumNames reference 都必须解析；empty pair 显式计数，asymmetric empty 为 `FAIL`。
3. 每个非空矩阵键为 `(source_sha, condition, provisional_unit, event_index, raw_replicate_index)`；恰好归属一次。
4. header 只白名单解析 acquisition start、channel/instrument、measurement protocol；原始内容只保留 SHA-256，不输出用户、目录或文件名。
5. raw matrix `[18,n]` 只按冻结方向转为 canonical `[n,18]`；不插值、不删除频点、不填补。
6. column map 除 token 全等外，还用 `|Z|`、phase、Y、Cs/Cp 与 Re(Z)/-Im(Z)/frequency 的代数关系做独立数值 sanity；失败只影响相应 schema/target scope。
7. transient 逐块扫描并保留 NaN mask geometry、canonical content hash、time reversal/duplicate/gap；不修复、不排序、不裁剪原始行。
8. ES12 不允许 `min(length)`、head/tail trim 或插值。没有唯一 index map 时输出候选解释并保持 transient time `BLOCKED`。

## 4. 内容重复规则（扫描前冻结）

- Exact signature：dtype、shape 与 endian/NaN/zero canonicalized bytes 的 SHA-256。
- EIS near-candidate sample：同 event、同 sorted replicate rank、同 canonical shape；从 flattened matrix 固定选 64 个等距位置。
- Transient near-candidate sample：固定 257 个等距 row × 17 个等距 waveform positions。
- 仅在 finite overlap ≥64、Pearson `r ≥ 0.999999` 且 pooled-RMS normalized RMSE `≤ 1e-5` 时标 `near_duplicate_candidate`。
- Exact 或 near 只能产生 candidate，不能自动证明同一物理器件；没有外部身份依据时 resolution 为 `quarantined_unresolved`，不得生成可用于 split 的 duplicate group。

## 5. Gate families

| Gate | Scope | PASS 条件摘要 |
|---|---|---|
| G00 | source/bytes | ZIP/MAT SHA、CRC、size、HDF5 open 与冻结 manifest 一致 |
| G01 | references | 1,752 event slots、8,835 matrices、pair/empty/orphan 全对账 |
| G02 | columns/frequency | 唯一 18-column schema、orientation、finite positive monotonic frequency、完整 grid/shape ledger |
| G03 | time | EIS acquisition 全解析且 pair-before-sort；transient 每 signal row 唯一映射 timestamp |
| G04 | missingness | NaN/Inf、row/position/run geometry 与 mask hash 完整；不填补、不删除 |
| G05 | identity | 稳定 physical ID、serial/board/batch/replacement/reuse 证据完整 |
| G06 | duplicates | exact/near 扫描完成，所有 candidate 有外部证据裁决且 split groups 无 unresolved |
| G07 | capacity | 唯一 Cs/Cp、frequency、replicate aggregation、单位、C0、availability 与 failure rule 有物理依据 |
| G08 | ESR/SOH | 唯一 ESR derivation/fit 与 R0/SOH 公式通过；Re(Z) 不得直接改名 ESR |
| G09 | outcome/RUL | termination/censor/EOL 语义逐物理器件可核验；sequence end 不作 EOL |
| G10 | invariance | 两次稳定工件逐字节一致，repair/quarantine/version/COMPLETE 全绑定 |

## 6. 必需工件

- JSON：`DATA_GATE_CONTRACT.json`、`DATA_MANIFEST.json`、`TARGET_DEFINITIONS.json`、`SCHEMA_TEST_RESULTS.json`、`DATA_GATE_SUMMARY.json`、`ARTIFACT_MANIFEST.json`、`COMPLETE.json`。
- CSV：`REFERENCE_LINKAGE_LEDGER.csv`、`EIS_EVENT_LEDGER.csv`、`COLUMN_FREQUENCY_LEDGER.csv`、`TRANSIENT_ALIGNMENT_LEDGER.csv`、`MISSINGNESS_LEDGER.csv`、`UNIT_IDENTITY_LEDGER.csv`、`CONTENT_SIGNATURE_LEDGER.csv`、`DUPLICATE_CANDIDATE_LEDGER.csv`、`REPAIR_QUARANTINE_LEDGER.csv`、`TARGET_TRAJECTORY_LEDGER.csv`、`OUTCOME_LEDGER.csv`、`ELIGIBILITY_MATRIX.csv`。
- 报告：`DATA_GATE_REPORT.md`、`ARTIFACT_HASHES.sha256`。

所有原始槽位必须满足 `raw = eligible + quarantined + structural_empty`。输出目录必须新增且非 symlink；科学工件不含运行时间或绝对输出路径，便于确定性复跑。

## 7. 下游锁定

- EIS parser release 需要 G00–G03、G10 对 raw-EIS scope 全部 PASS。
- Transient parser release 还需相应 G03/G04 PASS；条件可分别阻断。
- capacity official Eval 还需 G05–G07 PASS；within-voltage LOCO 还需 G06 PASS。
- ESR/SOH 需 G08 PASS；RUL/survival 需 G09、正式 Design Gate 与 Freeze B。
- 模型、冠军、Agent 拓扑、影子验证和上线在 P1 全部固定为 `BLOCKED_BY_USER_SCOPE`。

P1 允许输出 raw `Cs/Cp/Re(Z)` 质量审计和明确命名的 proxy candidate；不得把它们改名为 capacity、ESR、SOH 或 RUL。
