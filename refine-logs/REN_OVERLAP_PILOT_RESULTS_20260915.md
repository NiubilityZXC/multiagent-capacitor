# Ren 首两组重叠审计实跑结果

2026-09-15，ARIS monitor-experiment / experiment-bridge。仅 P1-R1 数据审计，不是预测实验或 Data Gate PASS。

## 实测结果

运行 `overlap_pilot_20260915_v1` 的持久化日志明确记录 `child_returncode: 0`；没有用文件存在代替退出码。原 XLS、archive、schema 和 chronology 未为收取结果重复执行。

| 来源命名候选组 | record 表 | 记录数 | 选中指纹 | ignored spool 字节 |
|---|---:|---:|---:|---:|
| batch1/1 | 3 | 181250 | 14035 | 8881250 |
| batch1/2 | 3 | 181453 | 14006 | 8891197 |
| 合计 | 6 | 362703 | 28041 | 17772447 |

跨组同指纹候选对 0，确认投影片段 0；matches.jsonl 为空。这里只能说明这两组在冻结的精确测量投影、8-row seed / 25-window 规则下未产生候选，不能推断全部113组不存在重复、近似复制不存在，或物理设备身份已验证。energy 缺失/冲突计数均0是没有匹配片段下的空集合统计，不能据此证明 energy 完整或一致。

## 可复核证据

- SUMMARY SHA256：`c1544ff993feedf4a7513562879c1a7a9032a596c68f8e63379a3cb3b7d263a9`
- COMPLETE SHA256：`b7be7a9152ad089838c9ec084bfcd981443c69a600eea952c5253937f98ca725`
- runtime log SHA256：`d7e451843652392fab87149cbc13885cc50de5e69bb9bd37cce33e2f48135112`
- index SHA256：`0f05c657e46a7d67780e904ceefbf1da137679759422ba1560dbb87a0e04bb19`
- empty matches SHA256：`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`

主执行者以只读 SQLite 和持久化 spool 复核所有指纹、49字节记录长度、group 行数、spool hash、候选数、空 matches、summary/log 一致性与 COMPLETE 绑定，均通过。此步骤复用了运行中的 reference verifier，不冒充另一套独立算法。

pre-run fresh reviewer：PASS_OVERLAP_FIRST_TWO_PILOT，193必测通过、0跳过；响应 SHA256 `caa28fe9ef44a07f5cbd35654eebd6148e1f1dda45354bab26a889a5a72b320b`。一般回归658通过、58跳过；必需 xlrd 路径已在隔离环境实际执行。release 绑定26项代码、测试、政策与 .gitignore，旧记录保留。

运行后独立复审尚待收取，其裁决将追加到本报告；不会以主执行者对账代替独立复审。

### 14:19 运行后独立复核收取

裁决 PASS，无阻断。fresh same-family provisional engineering review 使用独立 heap-based rightmost-window-min 算法，从持久化 spool 重建28,041个指纹，逐项与SQLite一致；独立digest-multiset计算也得到0跨组候选。核验全部26项release、schema receipts 001/012与六个span、所有spool/hash/长度、输出false标志及实际exit0日志一致。

完整响应保存在 ignored `data/raw/ren_scs/overlap_pilot_postrun_response_20260915.md`，SHA256 `793f85eda334afdd5270939674e2258fa8361b5a312ae23fc4791666367257cf`。该PASS仅为首两组持久化工程证据对账，不是跨模型科学接受性或最终Data Gate判定。审查未重读原XLS或执行模型。

## 下一步与边界

首两组 release 不授权全量入口。下一步复用冻结 pipeline，为113组建立单独全量 caller、资源预算、端到端测试和整体 pre-run review；通过后才运行全量重叠审计。原始测量 spool、transcripts、日志继续 ignored，仅代码和非原始测量的审计结果同步 GitHub。

Data Gate 尚待跨组全量重叠、来源与行证据结合的身份、容量/ESR资格、终止/删失和 whole-unit 切分。当前所有 model/API、numeric_target、physical_identity、target、P2、automatic_next_stage 标志保持 false。没有预测精度、RUL、SOH结果或高水平论文可发表性的数值结论。
