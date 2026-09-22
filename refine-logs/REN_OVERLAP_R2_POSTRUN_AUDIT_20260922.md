# Ren R2 独立运行后审查归档

2026-09-22 归档 09-21 的独立报告；昨日额度中断，没有覆盖失败记录或重新扫描。ARIS experiment-audit，same-family / provisional。

## 结论与证据边界

独立 overall verdict：**WARN，R2 观察工件无阻断**。工件对账为 **composite PASS**，不是 Data Gate PASS。

完整原文在 ignored `data/raw/ren_scs/r2_postrun_review_20260920/FINAL_REVIEW_20260921.md`；SHA-256 `74885722547bdcc03c733aea571f5bb919397accf570710dbf93e14b0f735bf1`。原始 transcript 不上传 GitHub。

生产 R2 实际退出 0，覆盖 113 命名组、233 文件、1,633 record 表、104,190,778 行。独立核对 8,013,898 个指纹、129,364 个候选、117,133 条匹配账本行。重建从 persisted spools/index/schema receipts 出发，不包含从原始 XLS 再次生成 spool。

## 保留的失败链

- attempt1 FAIL：审查脚本误将容器与 Workbook 流哈希视为同域。
- attempt2 FAIL：误要求全局词典序与分组数值序相同；后续另验证完整覆盖和组内顺序。
- attempt3 总体 FAIL：metadata/provenance、SQLite、candidate/match 三阶段 PASS；fingerprint 阶段因动态模块与 multiprocessing spawn 的 PicklingError 失败。
- attempt4 仅 fingerprint PASS：绑定 attempt3 和审查脚本后改用 fork，覆盖全部 113 组。

组合通过不改写 attempt3。attempt3 SHA-256 `af52440bb29b491e5a96380028f9a6425556d2ba7c2c3fd8c6289ef0c0b02767`；attempt4 SHA-256 `8c17a9b65a6fa4f29c4ff1febc127cb2b1b7c59cc3e99ca21b98a0a896ffdcc6`。早期 hash receipt 的文件名标签未更新是保留的非阻断缺陷，digest 值已核对对应 JSON。

## 必须进入后续裁决的发现

全部确认只涉及 **batch3/22 与 batch3/23** 一对。两组各 1,523,379 行，完整 persisted spool 按字节相同，energy 每行存在且相同。投影包括 status、局部时间、V、mA、mAh 和 energy，不包括 cycle、step、record_number 或其他工作簿内容。对应源容器与 Workbook 流哈希不同。

因此可确认测量投影完全一致，不能推断同一物理设备、独立性成立或重复无害。117,133 是重叠 anchor-derived 账本行，不是独立重复事件数。

不自动合并、排除或放入不同 folds。将该对样本带入原有 identity / duplicate / whole-unit split 裁决，并结合下一资格审计的 native key、工步/周期和来源证据。尚未解决前不运行 P2；不因这个发现重跑全量 overlap。

## A–F 摘要

| 检查 | 独立结论 |
|---|---|
| A 真值来源 | PASS，GT 不适用；确定性真实来源观察 |
| B 分数归一化 | PASS；没有模型分数 |
| C 结果存在与对账 | PASS，明确的组合证据 |
| D 执行路径 | PASS，限定所声明的观察路径 |
| E 范围 | WARN；完整覆盖不等于阳性事件相互独立 |
| F 类型 | self_supervised_proxy；更准确是无 GT 的确定性投影重叠审计 |

模型/API、容量 target、RUL、P2 未运行；物理身份与最终 Data Gate 尚未裁决。该结论只能支持 R2 观察，不能支持预测精度或论文性能声明。
