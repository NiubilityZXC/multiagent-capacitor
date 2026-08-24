# P1 Ren / Patrizi 数据获取与审计人工决策包

**生成时间**：2026-08-24 15:32:27 +08:00  
**状态**：`AWAITING_HUMAN_DECISION`  
**阶段**：P1 new-data acquisition / row-level Data Gate  
**依据**：`refine-logs/EXPERIMENT_PLAN_20260824_151915.md`、`idea-stage/DATASET_EXPANSION.md`、`RESEARCH_BRIEF.md`  
**AUTO_PROCEED**：`false`

## 1. 本次决策的准确边界

本决策包把 Ren 与 Patrizi 设为两个相互独立的批准项。批准某一项，只授权从下列已冻结的 Figshare 路径获取对应 payload，并在 `/home/user/multiagent-capacitor` 内完成来源、完整性、安全解包和 row-level Data Gate 审计。

P1 **不授权**：

- 运行数值模型、统计模型、机器学习模型、LLM 或 Agent；
- 生成、拟合或评分 RUL；
- 调用 Ark 或任何其他模型/API；
- 下载 Warwick、作者代码、其他论文附件或未列出的补充文件；
- 把原始 payload、解包内容或潜在敏感响应提交到版本库；
- 因审计失败而推断修复 rows、重命名 target、补造事件或改变 frozen estimand。

P1 可以审计“RUL 是否在未来可定义”，但不能在本 Gate 内产生可用于建模或评分的 RUL 标签。任何 P2 数值实验、P3 API capability、P4/P5 Agent 预测都需要各自后续 Gate。

## 2. 已发布来源与精确 acquisition envelope

以下数值来自当前已冻结的本地来源证据；本轮尚未联网复核、下载或解包。

### P1-Ren：独立批准项

| 字段 | 冻结值 |
|---|---|
| 数据集 | Ren et al., `SCs` |
| Figshare landing URL | `https://figshare.com/articles/dataset/SCs/11522082` |
| DOI | `10.6084/m9.figshare.11522082.v1` |
| Licence | `CC BY 4.0` |
| Payload | `raw.rar` |
| Published direct URL | `https://ndownloader.figshare.com/files/20691603` |
| Expected bytes | `2,114,703,017` |
| Published MD5 | `26a7a663217c59377c83fb2a8274466b` |
| 本项预计下载量 | **`2,114,703,017` bytes** |

已知但尚未由 rows 证明的描述是：113 个 Eaton HV 1 F/2.7 V carbon EDLC，四个 batches，其中 88 个 constant-20 mA、25 个 stepped-charge/20 mA-discharge devices。它们是审计假设，不是预先接受的 unit registry。

**人工决定**：

- [ ] `APPROVE_P1_REN_ACQUISITION_AUDIT`
- [ ] `REJECT_P1_REN_ACQUISITION_AUDIT`

### P1-Patrizi：独立批准项

| 字段 | 冻结值 |
|---|---|
| 数据集 | Patrizi et al., `Study of Accelerated Ageing Effects on Hybrid Supercapacitors Under Different Fast-Charging Strategies` |
| Figshare landing URL | `https://figshare.com/articles/dataset/Study_of_Accelerated_Ageing_Effects_on_Hybrid_Supercapacitors_Under_Different_Fast-Charging_Strategies/29153561` |
| DOI | `10.6084/m9.figshare.29153561.v2` |
| Licence | `CC BY 4.0` |
| Primary payload | `Dataset_HSC.mat` |
| Primary published direct URL | `https://ndownloader.figshare.com/files/54852761` |
| Primary expected bytes | `225,986,697` |
| Primary published MD5 | `57e71c60cbae63142db44559edfa8ae0` |
| Information payload | information PDF |
| Information published direct URL | `https://ndownloader.figshare.com/files/55269047` |
| Information expected bytes | `397,625` |
| Information published MD5 | `0189a89a72c73080cece2104ba834bce` |
| 本项预计下载量 | **`226,384,322` bytes** |

已知但尚未由 rows 证明的描述是：8 个 4.2 V hybrid supercapacitors，每种 fast-charge strategy 一个 device，20 °C、40% RH、4 A discharge。由于一策略一设备，device identity 与 strategy 完全混杂；即使本项通过，也只能作为 separate-domain、confounded cross-strategy stress test。

**人工决定**：

- [ ] `APPROVE_P1_PATRIZI_ACQUISITION_AUDIT`
- [ ] `REJECT_P1_PATRIZI_ACQUISITION_AUDIT`

### 合计

若两个批准项都通过，精确 published payload 总量为：

`2,114,703,017 + 225,986,697 + 397,625 = 2,341,087,339 bytes`

即约 2.341 GB（十进制）；该数只表示传输 payload，不含 `.partial` staging、副本、解包文件、解析缓存或审计产物。

## 3. 磁盘与解包前置条件

本地只读检查时，承载 workspace 的文件系统报告：

| 项目 | 观测值 |
|---|---:|
| Filesystem | `/dev/nvme0n1p2` |
| Total | `1,966,736,678,912` bytes |
| Used | `791,734,730,752` bytes |
| Available | `1,075,021,697,024` bytes |
| Use% | `43%` |

这是决策包生成时的瞬时值，不是执行时保证。`raw.rar` 的 member 数、listed uncompressed bytes、嵌套压缩与 extractor 临时空间在当前证据中均为 **UNKNOWN**；MAT 的安全解析峰值内存也为 **UNKNOWN**。因此不能仅凭 2.341 GB 下载量宣布磁盘 Gate 已通过。

执行时必须先重新运行磁盘检查。Ren 下载完成并通过 bytes/MD5 后，只允许做无写入的 archive listing/test；设该 listing 给出的待写 uncompressed bytes 为 `U`。在解包前，available bytes 必须至少覆盖：

`尚未完成的 approved payload bytes + U + max(10 GiB, 0.20 × U)`。

若 extractor 无法可靠列出全部 members 和 uncompressed sizes、available bytes 低于该项目安全余量、预计 staging 超出 workspace 文件系统，或任何工具会在 workspace 外写临时文件，则 **立即停机**，保持已验证 archive，不尝试解包，等待新的存储决策。

## 4. 下载、摘要与 raw-manifest 合同

每个批准项单独执行并单独裁决，不因另一个 item PASS 而自动继续。

1. 只访问本包列出的 landing/direct URLs；记录 retrieval time、HTTP status、redirect chain/final effective URL、Content-Length、ETag/Last-Modified（若服务提供）和 downloader/version。
2. 下载到 `data/raw/<source>/incoming/*.partial`。现有 `.gitignore` 的 `/data/raw/` 规则已覆盖该区域；partial、archive、extracted rows 和 local-only manifest 均不得进入版本库。
3. 完成传输后先验证 observed bytes 与 expected bytes 精确相等，再验证 observed MD5 与 published MD5 精确相等；任一不符即隔离并停机，不重复使用、不解包。
4. 在 published checks 通过后计算项目 SHA-256。SHA-256 是本项目的 immutable byte identity；不能用 MD5 或 URL 代替。
5. 仅在全部摘要通过后，把 `.partial` 原子改名为 frozen raw filename。不得覆盖已有同名文件；若已存在，先比较 size、MD5、SHA-256，任何差异都停机。
6. 在 ignored raw tree 保存 `LOCAL_RAW_MANIFEST.json`，至少包含 source/item/file IDs、DOI、licence、URLs、expected/observed bytes、published/observed MD5、project SHA-256、retrieval headers/times、local relative path、tool versions和状态。
7. 在 `data/audit/<source>/<timestamp>/` 生成不含 raw rows 的 compact acquisition manifest与 hash ledger，引用 local-only raw manifest 的 SHA-256，并明确 raw payload 为 ignored/local-only。任何未来同步只允许 compact manifest、protocol、audit summary 和 hashes。

## 5. 安全解包与静态解析合同

### Ren `raw.rar`

在写出 member 前必须 listing/test archive，并机械拒绝：

- absolute path、drive/UNC prefix、空路径、`..` traversal 或 normalize 后逃出 destination 的路径；
- symlink、hardlink、junction/reparse、device、FIFO/socket 或其他非普通文件；
- encrypted/password-protected member、无法列出 size 的 member、CRC/test failure；
- unexpected nested archive、可执行文件、脚本、宏/active content，除非先单独人工批准；
- duplicate normalized path、case-fold collision、会覆盖既有文件的 member；
- listed bytes/member count 与 extraction 后事实不一致。

只可解包到新建、空的 `data/raw/ren_scs/extracted_<timestamp>/` quarantine 目录；禁止 overwrite，禁止执行任何内容，记录 extractor binary/version、listing、test log、member path、compressed/uncompressed bytes、CRC（若有）与每个 extracted regular file 的 SHA-256。解包完成前不得由 parser 读取半成品目录。

### Patrizi MAT/PDF

`Dataset_HSC.mat` 与 PDF 不作为可执行内容运行。MAT 只用记录版本的安全静态 reader 分块读取 keys/dtypes/shapes；不得 `eval`、不得运行 embedded object/code、不得调用作者脚本。PDF 只作为说明性 provenance，不能覆盖 raw rows。若 MAT parser 需要整文件/整数组载入且内存预检不通过，或 container/version 不受当前 reader 支持，则停机并提交新的 parser 方案。

## 6. Row-level Data Gate 检查矩阵

每个 source 产生独立 `PASS`、`FAIL` 或 `BLOCKED`；“可下载”不等于“可建模”。

### A. Identity Gate

- 枚举 archive/member/workbook/sheet/MAT key 的完整层级和 SHA-256；建立 raw-file → physical-device → batch/protocol/strategy 的证据链。
- Ren 必须从 rows/metadata 证明 exact unique device count、稳定 device IDs、四 batch 映射、88/25 protocol 分组；不能从 filenames、file length、terminal cycle 或论文子集数量推断。
- Patrizi 必须证明 8 个 unique devices、每个 strategy 的唯一映射及是否存在额外 calibration/reference runs；明确 LOCO 同时是 leave-one-strategy-out。
- 无法把 trajectory 唯一归属到 physical device，或 paper/PDF/author description 与 raw identity 冲突时，source scientific Gate 为 `BLOCKED_IDENTITY`。

### B. Schema / Unit Gate

- 对每列/key记录 exact name、dtype、shape、unit、missing/nonfinite count、sampling granularity、native/summary/derived status和证据来源。
- Ren 重点审计 voltage、current、time、cycle/index、mAh、mWh；检查 workbook formula、hidden rows/sheets、merged cells、locale/time encoding和符号约定。
- Patrizi 重点审计 time、cycle、current、voltage、`Cap_ch`、`Cap_dis`、IR、temperature、method、per-cycle summaries及 EIS frequency/real/imaginary arrays；核验所述 61-point、100 mHz–100 kHz、每 25 cycles 的结构是否由 rows 支持。
- unit 缺失或同名字段跨 devices/protocols 含义不同，必须隔离而非静默换算。

### C. Chronology Gate

- 在 physical-unit/protocol 内验证 time/cycle 单调性、重复/倒序、reset、gap、sampling interval、segment boundaries、charge/discharge direction与 terminal-record integrity。
- 所有 rolling origins 只能使用 origin 时刻及以前的 rows；final length、最后 cycle、EOL status、future gap、archive member size均不得进入 feature、packet或 split rule。
- reset 或多段实验必须有可审计 segment identity；无法区分 reboot/reset 与真实 chronology 时，相应 trajectory `BLOCKED_CHRONOLOGY`。

### D. Duplicate / Overlap Gate

- 对 raw digest、normalized row sequence、device ID、batch/protocol、cycle-time signature、waveform fingerprint 和 derived-summary fingerprint 去重。
- 检查 renamed/copy members、同一 waveform 的截断/重采样版本、同设备 summary 与 raw 双计数，以及 Ren 60/84/88/113-cell 文献子集可能造成的 fleet overlap。
- duplicate group 在 outer split 前冻结；同一 physical device 或其派生副本不得跨 folds。无法解析的重叠进入 quarantine，不计作独立 unit。

### E. Target Gate

- **Ren capacitance**：不是已列 native target。仅当 constant-current segment、voltage bounds、IR-drop handling、sign、sampling与 aggregation 可冻结时，才可考虑 `C = |I| Δt / |ΔV|`；否则 farad target 为 `NA`。
- **Ren ESR**：当前无 native ESR/EIS 证据，保持 `NA`，不得由 capacitance trend 猜测。
- **Ren SOH**：只有在 per-device `C_ref`、stabilization period、normalization和 train-only rule 冻结后，才可定义 `SOH_C(t)=C(t)/C_ref`。
- **Patrizi capacity**：`Cap_ch`/`Cap_dis` 是 Ah quantities，必须称 charge/discharge capacity 或 capacity-SOH，不能称 farad capacitance。
- **Patrizi IR/ESR**：IR 不自动等于 ESR。EIS-derived ESR 必须另行冻结 measurement convention、frequency selection/interpolation、units和 missing rule。
- 任一 target 的 native/derived provenance、unit 或在线 availability 不可证明时，该 target `NA/BLOCKED`；不能为了进入 P2 改名。

### F. Terminal Event / Censor Gate

- observed physical failure 只接受 explicit auditable record；当前两个 source 都未获此资格。
- protocol EOL 需要预声明 threshold、smoothing、persistence、missing rule和 time/cycle axis，并由 rows 证明 first qualifying crossing。
- Ren author workflow 的 0.903 F convention 和 non-crossing behavior 不能作为 benchmark truth；无 qualifying crossing 的 unit 保留 `(last_observation, event=0)`。
- Patrizi 的“below 70% capacity stop”只是待核验 candidate。必须区分因 threshold 停机、最后记录恰好低于阈值、early truncation 和 missing terminal cycles。
- censored、extrapolated或 unresolved event time 不得作为 exact RUL truth。P1 只输出 event/censor eligibility ledger，不生成或评分 RUL。

### G. Split / Leakage Gate

- 在任何 feature、prompt、model、router、calibration或 ensemble 开发前冻结 physical-unit registry和 split hash。
- Ren 使用 sealed whole-unit outer CV；一个 device 的所有 rows/windows/origins 只属于一个 outer fold。batch/protocol holdout 单独定义；25 stepped-charge devices 不得通过 summaries或重复 trajectory 泄漏回 training。
- scaler、target reference、threshold tuning、feature selection、fusion、`b_star` 和 ENUM tables 只能来自 outer-training，并在 nested whole-unit inner CV 中选择。
- Patrizi 与 Ren 不池化。Patrizi 单独 whole-unit LOCO，明确标记 device/strategy confounding；不把 8 units 写成 per-strategy replication。
- split schedule 不得依赖 final life length、terminal event、future target、member size或其他 suffix-only metadata。

## 7. 审计产物与裁决

每个已批准 source 至少生成：

1. acquisition/source-provenance manifest；
2. published-MD5 与 project-SHA256 ledger；
3. ignored local raw/extracted manifest及其 compact hash reference；
4. archive safety/extraction report（Patrizi 记录为 static-container inspection）；
5. unit/identity ledger；
6. schema/unit ledger；
7. chronology与 terminal-record ledger；
8. duplicate/overlap ledger；
9. target-eligibility与 unavailable-target mask；
10. event/censor eligibility ledger；
11. proposed whole-unit split manifest与 leakage audit；
12. source-specific Data Gate summary，逐项给出 `PASS/FAIL/BLOCKED/NA` 和证据 hash。

P1 的最高正面裁决只能是：`ACQUISITION_INTEGRITY_PASS` 加上特定 target 的 `ROW_LEVEL_ELIGIBILITY_PASS`。它不代表 model accuracy、RUL validity、跨域泛化或 API-Agent value。

## 8. 强制停机条件

遇到下列任一条件，停止当前 source；不得以另一个 source、Benchmark-L 或 Stress-2 替代：

1. 未收到该 source 的精确独立批准 token；
2. DOI、licence、file ID、final effective URL 与 frozen provenance 无法对账；
3. HTTP/transport 不完整，observed bytes 或 published MD5 不匹配；
4. 同名 local file 的 SHA-256 不同，或 project SHA-256 无法生成/复核；
5. disk/free-space rule 不通过，uncompressed size未知，或写入会越出 workspace；
6. archive test失败、路径逃逸、link/device/special member、encryption、collision、unexpected active content或 nested archive；
7. parser 需要执行数据内容/作者脚本，或无法以静态、分块方式安全读取；
8. physical identity、schema/unit、chronology、duplicate group或 terminal record出现无法裁决冲突；
9. paper/PDF/描述与 raw rows 冲突；冲突必须记录，不能按描述修补 rows；
10. target、event/censor或 whole-unit split 不可防泄漏地冻结；
11. 任何步骤意图运行 model、RUL scoring、LLM/Agent或外部 API。

## 9. 人工签署区

允许只批准一个 source。推荐使用下列精确语句之一或同时使用两句：

- `批准 P1-Ren：仅获取并审计 raw.rar；不批准模型、RUL 或 API。`
- `批准 P1-Patrizi：仅获取并审计 Dataset_HSC.mat 与 information PDF；不批准模型、RUL 或 API。`

在收到相应批准前，状态保持 `BLOCKED_HUMAN_GATE`。本决策包本身不是批准，也不改变 P2–P5 的阻断状态。
