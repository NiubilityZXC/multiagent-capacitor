# Ren P1-R1 R4 执行结果与停止点

时间：2026-09-08 15:22:49 +08:00。运行：`p1r1_20260908_150800`。
状态：`RECOVERY_PASS / STATIC_AUDIT_COMPLETE / BLOCKED_ROW_PARSE`。

## 已完成的真实执行

- R4/v5 独立 pre-run review：PASS，0 blocking；审查者 72 项定向测试通过，主执行者 492 项全项目回归通过。
- R1A：原始归档与批准记录哈希一致，RARLAB 7.23 工具身份、旧 listing 对账、磁盘预检通过。
- R1B：完整 archive test 通过，233 文件与 4 目录精确匹配，无 warning/error。
- R1C：新 append-only 隔离目录提取通过，233 文件、4 目录、15,223,551,488 bytes，逐成员大小/CRC/类型/路径一致。
- 独立 verifier：`PASS_R1ABC_INDEPENDENT_VERIFICATION`，独立重建各报告及重新核验文件。
- R1D：隔离环境内全部 233 XLS 完成静态结构检查，无公式/宏执行、无行解析。

## 实际阻断

| 扫描器标记 | 涉及工作簿数 |
|---|---:|
| 未分类 BIFF 记录类型 | 233 |
| 未分类 CONTINUE 上下文 | 6 |
| 宏类 OLE 目录条目 | 83 |
| 嵌入对象类 OLE 目录条目 | 83 |

计数可重叠，不应相加当作工作簿总数。共有 60 种未分类 record ID。宏/嵌入对象标记来自保守的 OLE 目录名称规则，不等同于恶意内容或已验证的代码行为。未知记录也不等同于损坏；当前分类器的识别范围不足以证明它们可安全进入行级审计。

R1E 未执行；R1F identity、target、chronology、duplicate、censor 无行级证据，split 未构建。P2 和 RUL 均不 eligible。八份下游 CSV 是显式 `NOT_EVALUATED_R1D_BLOCKED` 占位记录，不是伪造的行级审计结果。COMPLETE 只表示静态清点完成，绝非 Data Gate PASS。

## 工件核对及边界

主执行者另外用独立汇总代码读取 233 份静态 JSON，核对唯一成员、容器/阻断计数、安全 ledger 的成员/哈希/大小/标记与所有 false 执行标志，并重新计算 ARTIFACT_MANIFEST 的 255 个绑定文件哈希：全部通过。此检查没有重新打开工作簿，也不是第二套独立 BIFF 分类器或科学验证。

完整恢复证据：`data/audit/ren_scs/p1r1_20260908_150800/`。
静态结论及清单：`data/audit/ren_scs/p1r1_20260908_150800_static/`。
原始 transcripts、逐工作簿结构 JSON、工具与解压数据仍在 ignored staging，不提交 Git。R2/R3 失败运行和旧审查记录未改写。

## 下一步与实验启动条件

按原冻结计划强停止，不绕过 R1D、不直接交给 xlrd，不删宏、不转换工作簿、不凭文件名排除样本。下一修复版本应先针对这 60 种实际记录和 CONTINUE 的上下文做规范级分类，并单独明确宏/嵌入对象的只读隔离边界；任何处理或排除规则须显式记录，经过合成对抗测试与独立 pre-run review，不反向改写本轮结果。

当前不能承诺模型实验日期。最早开跑条件仍是：R1D 问题解决 → R1E/R1F 有真实行级证据并通过 → 冻结新的 P2 eligible units/targets/splits/origins/horizons 与模型实验预算 → 用户批准 P2 seal。届时才比较大模型 Agent 直接预测、多 Agent 和 Agent＋专用模型；本轮没有模型、API、GPU、RUL 或性能结果。

截至本报告，恢复证据已推送 GitHub commit `5589fcc`；静态结果将在本轮收尾提交中同步。
