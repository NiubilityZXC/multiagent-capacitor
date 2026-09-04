# Ren P1-R1 归档恢复与行级审计计划

**时间**：2026-09-04 14:54:23 +08:00
**状态**：`HUMAN_GATE_REQUIRED / PLAN_ONLY / NO_EXECUTION_AUTHORITY`
**ARIS workflow**：`experiment-plan`
**目标**：只解除 Ren `raw.rar` 的 RAR5 解码阻断并重做行级 Data Gate；不授权模型、预测、RUL、Ark/API、GPU 或 outer score。

## 1. 当前证据与硬阻断

| Evidence | Frozen value | Meaning |
|---|---|---|
| `raw.rar` | 2,114,703,017 bytes；MD5 `26a7a663217c59377c83fb2a8274466b`；SHA-256 `a8f1083b887f95483561a94b624b323ff42814654ee7f23e7f95bc042fa258d8` | acquisition integrity PASS |
| container | RAR5、single volume、not solid、not encrypted | 可做独立 member 对账 |
| listing | 237 members = 4 directories + 233 regular `.xls`；uncompressed 15,223,551,488 bytes | 路径/扩展名静态 allowlist PASS |
| compression | 全部 233 files=`m3:25` | 本机 7-Zip 23.01 test 返回 233 次 `Unsupported Method` |
| current P1 | `ACQUISITION_INTEGRITY_PASS_ARCHIVE_TEST_BLOCKED_NO_EXTRACTION` | 无 row、target、identity、split 或 modeling 资格 |
| N0+ SN1 | manifest SHA-256 `ec33bdf2ee5b146bae3c09403d09f2b703bb0da0f52c2874dbaaa9fcc2cbc6f3` | 仅 synthetic contract；不能替代 P1 |

父协议保持字节不变：

- `refine-logs/EXPERIMENT_PLAN.md`：`df968d2e7ba33748043e547165143d9247358afca573946f3dde573c8c04b6d2`
- `refine-logs/round-3-refinement.md`：`d4d40b0a7e3f5c9030bfe80e5ede3d059673c3b3c96122c9cf050097aa54f110`

## 2. 工具选择与可复现边界

首选候选固定为 RARLAB 官方 `RAR for Linux x64 7.23`，官方链接为 `https://www.rarlab.com/rar/rarlinux-x64-723.tar.gz`。RARLAB 下载页在本计划日期列出 Linux x64 7.23；7.23 release note 明示修复 RAR5 recovery-volume heap overflow 与符号链接越界提取问题。

工具不得全局安装。下载到项目内 ignored staging 后，先记录：最终 HTTPS scheme/host/path、响应 headers、文件 bytes、SHA-256、包内文件清单、license、解包后二进制 bytes/SHA-256、`-iver` 输出。若下载页面版本不再为 7.23、重定向到非 RARLAB 域、包结构异常或 version output 不一致，记录 `BLOCKED_TOOL_IDENTITY` 并停止。

不得用 `unrar-free` 作为静默替代；其公开说明承认缺少 RAR5 等重要特性。不得在官方工具失败后换第二个解码器继续，除非形成新的人工批准 generation。

## 3. 执行里程碑

| Stage | Action | Mechanical PASS | Strong stop |
|---|---|---|---|
| `R1A` | 重新校验原 RAR bytes/MD5/SHA；磁盘预检；获取并哈希官方 7.23；用新工具重新 listing | source hash 不变；工具身份完整；237/233/4、member path、size、CRC、encryption/link flags 与旧 listing 精确一致 | 任一 source/tool/member 差异即 BLOCKED，不提取 |
| `R1B` | 对整个 RAR 执行一次 archive test | exit 0；233 members 全部 CRC/test PASS；无 password/data/CRC/unsupported warning | 非零、warning 或 member 不一致即 BLOCKED，不提取 |
| `R1C` | 提取到新建、空、run-specific、append-only 目录 | 所有输出均在该目录；233 regular `.xls`；0 symlink/hardlink/device/socket/FIFO；逐文件 size/CRC 对账 | 任一越界、链接、类型、数量、size/CRC 不一致即 quarantine + BLOCKED |
| `R1D` | legacy XLS 静态安全审计 | OLE/BIFF container 识别；macro/embedded/external-link ledger 完整；绝不执行 workbook code | active content 无法静态分类则 BLOCKED_ROW_PARSE |
| `R1E` | isolated Python reader 对 workbook schema/rows 做 chunked/read-only audit | package lock与wheel hashes冻结；sheet/column/type/unit/row/nonfinite ledger 完整；parser 不执行公式或宏 | parser crash、截断、formula cache/单位不可解释均 fail closed |
| `R1F` | identity/chronology/duplicate/target/censor/split Data Gate | 稳定 physical-unit identity、时间顺序、target derivation、duplicate groups、whole-unit split 均有 row evidence | filename/batch stem 不得单独当物理身份；任一必要 gate 未过则 P2 继续 blocked |

## 4. 固定审计纪律

1. 解压目录必须是本次 run 新建的显式路径；禁止覆盖或复用旧失败目录。
2. 先完整 test，后 extraction；test 不通过时 extraction attempt 必须为 false。
3. 解压工具只接触固定 `raw.rar` 和固定 destination，不执行归档内任何文件。
4. `.xls` 一律视为潜在 active-content container；不启动 Excel、LibreOffice、Wine、作者脚本或宏。
5. parser 依赖只装入新的 isolated audit venv；安装前生成 exact version lock，安装后记录 package source、wheel SHA-256、`pip check` 和 import smoke test。
6. raw/extracted data、decoder tarball/binary、临时日志继续 ignored/local-only；Git 只提交脱敏的 audit ledgers、代码、hashes 和报告。
7. paper/PDF/作者描述只作对照；与 raw rows 冲突时 raw evidence 优先并标记 BLOCKED，不做静默修复、插值、截断或单位换算。
8. 不能把 `batch*/<number>[_suffix].xls` 自动宣称为 113 个独立物理 devices。identity 不可核验时 whole-unit LOCO 不成立。
9. capacitance、capacity、ESR/IR、SOH、EOL、RUL 分开裁决；sequence end 不是 failure。RUL 默认 `NA`，除非另一个 endpoint/censor Gate 被批准并通过。
10. 任何候选模型、feature、prompt 或 Agent 都不得读取本阶段数据；本阶段不生成 numerical forecast。

## 5. 必须输出的工件

- `TOOL_IDENTITY.json` 与下载/二进制 hash ledger；
- `ARCHIVE_LISTING_DIFF.json`、`ARCHIVE_TEST_REPORT.json`；
- `EXTRACTION_MANIFEST.json`、逐 member size/CRC/type ledger；
- `XLS_STATIC_SAFETY_LEDGER.csv`；
- `WORKBOOK_SCHEMA_LEDGER.csv`、`ROW_COUNT_LEDGER.csv`、`MISSINGNESS_LEDGER.csv`；
- `UNIT_IDENTITY_LEDGER.csv`、`CHRONOLOGY_LEDGER.csv`、`DUPLICATE_OVERLAP_LEDGER.csv`；
- `TARGET_DEFINITION_LEDGER.csv`、`EVENT_CENSOR_LEDGER.csv`、`SPLIT_LEAKAGE_LEDGER.json`；
- `DATA_GATE_SUMMARY.json`、`DATA_GATE_REPORT.md`、`ARTIFACT_MANIFEST.json`、`COMPLETE.json`；
- 独立 verifier 与 deterministic/failure tests。

所有工件必须明确记录 `model_or_api_executed=false`、`numeric_target_emitted=false`，直到最终 Data Gate 才能仅给出 target eligibility；不得产生预测值。

## 6. 成功与失败解释

- `R1A–R1C PASS` 只证明可重现地安全恢复 source members。
- `R1D–R1E PASS` 只证明静态 row audit 可执行。
- 只有 `R1F` 对 identity、target、chronology、duplicate、split 全部 PASS，Ren 才能成为 P2 candidate dataset。
- 即使 P1-R1 最终 PASS，也不得自动运行 N0+、LLM 或多 Agent；必须先生成一份包含 eligible units/targets/origins/horizons、MASE denominator、calibration、nested LOCO、margins/power、failure/fallback 和 dependency hashes 的新 P2 seal，并再次由用户批准。
- 若 physical identity 或 target 仍不可证，主结果不能以 113 devices/whole-device LOCO 对外声称；项目转向寻找另一公开 fleet，而不是降低 gate。

## 7. 权限请求

建议批准的唯一范围是：下载并验证 RARLAB 7.23 工具工件；创建 isolated audit venv；完整 archive test；在新目录隔离提取；静态 XLS/container/row 审计；生成并验证 P1-R1 Data Gate 工件。

明确不批准：任何模型拟合/选择、预测、outer score/reveal、RUL、Ark/外部 API、GPU、P2/P3/P4/P5、论文性能主张。

批准 token 将由独立 JSON packet 绑定本文件 SHA-256；执行前必须逐字匹配 `APPROVE_REN_P1R1:<sha256>`。
