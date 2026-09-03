# Plan A Problem Anchor Addendum

**版本**：2026-08-27 15:28:47 +08:00  
**状态**：`PRESEAL_PROPOSAL / UNAPPROVED / NO_API / NO_OUTER_RESULTS`  
**适用 generation**：拟议 `GENERATION_1`  
**Canonical Plan B（只读）**：

- `refine-logs/EXPERIMENT_PLAN.md` — SHA-256 `df968d2e7ba33748043e547165143d9247358afca573946f3dde573c8c04b6d2`
- `refine-logs/round-3-refinement.md` — SHA-256 `d4d40b0a7e3f5c9030bfe80e5ede3d059673c3b3c96122c9cf050097aa54f110`

本文件不修改上述两个 canonical 文件。它只提出 Plan A 的新增 Problem Anchor；有限 supersession 必须逐项出现在 `CANONICAL_SUPERSESSION_LEDGER.md`，并经人工批准后才有效。

## 1. 新 Problem Anchor

> 在严格因果的 retrospective online replay 中，一套预冻结、fold-local 选择的多 Agent 架构，能否在共同 planned keys、相同外生可见信息、匹配的物理调用与执行包络下，相对 **preregistered fold-local numerical champion candidate** `N0`（baseline adequacy pending）以及合格的同调用 control `C_k`，改善或至少不实质损害 held-out physical-unit forecasting，同时形成可数值审计的可靠闭合、deadline 内完成和证据链？

这里的“online”仅表示每个 rolling origin 只使用当时可见 prefix 的 **online-capable forecasting under causal replay**。历史数据实验不得表述为真实现场在线部署或 prospective field validation。

## 2. 研究对象与 estimand

- 独立推断单位是 physical capacitor unit；origin、window、horizon、row、API replicate 均不是独立样本。
- 主域是通过 P1 Data Gate 后的 Ren fleet；Patrizi 仅在其独立 Gate 通过时作为 separate-domain B5，两个域不池化。
- 主准确率 estimand 是 common matured planned keys 上、保留 `ACTIVE`、`DELIBERATE_FALLBACK` 与 `ERROR_FALLBACK` 的 unit-macro point loss 差。
- ESR、SOH、RUL 仅在各自 endpoint、单位和 censor 语义 Gate 通过后进入；否则机械 `NA/BLOCKED`。不得为了扩大 task grid 改名或推断 target。
- `ARCH1` 是唯一新增确认性 arm。它不是一个事后挑出的全局拓扑，而是每个 outer fold 内只用 outer-training units 和 inner whole-unit CV 机械选择候选的同一预冻结程序。

## 3. 双 storyline 是一次实验

确认性 arm 集合固定为：

```text
Plan B canonical 11 arms
  = {N0, D1-RAW, D1-PACKET, H1, RF1, RC1,
     ACT1, IF1, ENUM-ACTION, D4-H, D4-X}
plus {ARCH1}
```

Plan A 与 Plan B 共用 data/split registry、common planned keys、maturity rule、fallback、attempt ledger、prediction ledger、hash chain、seed manifest、统计程序、generation-wide barrier、一次 seal 和一次 joint unseal。Plan A 是否达标不得决定 Plan B 哪些 admitted cells 执行，也不得决定 B5 是否执行。

## 4. Plan A 的可证伪主张档位

所有差值均定义为 `ARCH1 − comparator`，loss 越小越好；所有 CI 都来自 P2 冻结的 joint multiplicity 程序。

### 4.1 进取档

进取档是基础档的严格上层。仅当 **4.2 的全部基础档前置条件先成立**，且以下条件全部成立，才允许写“在本研究冻结包络内，tested multi-Agent system package 改善预测表现”：

1. `ARCH1−N0` 的 adjusted CI 上界 `< −δ_min`；
2. 存在合格 `C_k`，且 `ARCH1−C_k` 的 adjusted CI 上界 `< −δ_min`；
3. WIS、`ERROR_FALLBACK` 与 deadline harm gates 全部通过；
4. `ARCH1−D1-RAW` 完整报告，但 `D1-RAW` 只称 direct-LLM anchor；
5. P6 独立审计通过。

没有合格 `C_k` 时，进取档不可触发，也不得把完整 system-package gain 拆成协作节点或边的因果增益。

### 4.2 基础档

仅当以下条件全部成立，才允许写“在 `δ_NI` 内非劣并取得预指定操作性收益”：

1. `ARCH1−N0` 的 adjusted CI 上界 `< δ_NI`；
2. 若存在合格 `C_k`，`ARCH1−C_k` 同样满足该非劣界；
3. `ERROR_FALLBACK` 率 `≤ r_max`；
4. 不重发条件下的崩溃闭合恢复率 `≥ r_rec`；
5. 共同 workflow deadline `T_ARCH≡T1` 内的完成率 `≥ q_min`；
6. 唯一 primary operational endpoint 相对 `C_k` 通过 P2 冻结门；
7. P6 独立审计通过。

只通过基础档时，禁止写“equivalent”“全面优势”“架构优越”或任何 superiority 暗示。若任一 required outer fold没有合格 candidate，则 `ARCH1` 在 Generation 1 全局 `BLOCKED_ARCH_DEV`，全部 ARCH1 confirmatory hypotheses固定 `status=NA, p=1`；不得只保留成功 folds。若不能为每个 required fold确定合格 `C_{4,f}`，primary operational contrast为 `NA_NO_MATCH`，两个 Plan A tier均不能触发；只能报告 ARCH1 full-package rows。

### 4.3 未达标

只有全部 admitted cells 完成、generation-wide barrier PASS、joint unseal、冻结统计程序完成且 P6 independent audit PASS 后，如基础档未达标，论文才机械采用 Plan B canonical 为主叙事；`ARCH1` 的正、空、混合或负结果仍完整保留。P6 audit failure 是 `STOP`，不是 Plan B trigger。Generation 1 不得通过同一 held-out 数据上的改 prompt、改 topology 或重跑获得第二次确认性机会。

## 5. 操作性结果与 claim ceiling

四项结果均须报告：

1. 免人工模型选择；
2. 故障韧性资格；
3. 自审计证据链；
4. 端到端任务完成率/有效输出覆盖率。

其中“免人工模型选择”和“自审计证据链”若只是设计属性，不能单独触发基础档。唯一可比较的 primary operational endpoint 由 P2 在任何 development API 或候选 inner-CV 结果可见前冻结；本 addendum 提议采用 `ERROR_FREE_CLOSED_COMPLETION_BY_DEADLINE`，精确定义见 `PLAN_A_P2_FREEZE_PROPOSAL.md`。

自然准确率/WIS 只由未注入故障的 confirmatory execution 计算。故障注入及 fault-resilience 结果属于独立 qualification lane，只证明闭合与恢复性质，不得混入或抬高 natural accuracy estimand。

## 6. 明确 anti-claims

- 不把 role prompt、普通 debate、固定投票、hash ledger 或 Graph Engineering 本身称为新的 ML 原理。
- 没有 matched `C_k` 或另行批准的 `ARCH0-SHAM`，不声称协作结构、节点、边或路由带来增益。
- 不用 LLM judge、文字合理性、解释质量或 self-score 代替 ground-truth numerical loss。
- `N0` 只称 **preregistered fold-local numerical champion candidate**；其 baseline adequacy 在明确人工决定前一直为 pending，更不得写成文献 SOTA。“first/novel/SOTA/最强”必须等待 baseline decision 和 P6 最终文献核验。
- 不计算或估算金钱成本，不报告价格，不做 cost Pareto，不作“更便宜/节省成本”结论。
- physical attempts、requested/actual tokens、latency 与 deadline 只作为执行事实、暴露量审计、复现和匹配边界，不进入论文成功条件。

## 7. 当前 Gate

`CURRENT_AUTHORITY`：只允许对已存在的 P1-Ren/P1-Patrizi bundles 做只读重新核验、执行已有 static audit，以及不执行预测的文档/代码审查和 offline release checks。当前明确禁止新下载、新数据提取、新解码工具或 parser操作、P2 fitting/training/scoring、SOH/RUL构造或评分、P3、development API、P4/P5、formal outer evaluation和任何真实 LLM电容预测。本文件只是等待人工批准的 Plan A 研究合同草案，不产生任何扩权。
