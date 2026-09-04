# Ren P1-R1 恢复代码发布审查

**时间**：2026-09-04 22:04:22 +08:00

**ARIS workflow**：`experiment-bridge`

**最终裁决**：`BLOCKING / DO_NOT_RUN_R1B_OR_R1C`

**审查性质**：fresh GPT-5.6-Sol xhigh，同模型族 provisional；不宣称跨模型独立性
**用户批准范围**：`APPROVE_REN_P1R1:a7a8f5521b6b249af59a9ded0971cb02f912d9f46e8babfe3d60777cbfcc3c6d`

## 执行边界

- 已发生：固定 RARLAB URL 的本地下载/版本探测；只读 official listing；与旧 7-Zip ledger 的 exploratory 零差异检查。
- 未发生：reviewed runner 的正式 R1A seal、完整 archive test、解压、XLS 打开/解析、Data Gate、模型、预测、RUL、Ark/API、GPU。
- exploratory listing：237 members = 233 regular `.xls` + 4 directories；listed uncompressed bytes = 15,223,551,488；path/size/packed-size/CRC/compression 与旧 ledger 零差异。该结果未形成 release seal，不能解锁 R1B。

## 首轮审查与修复

首轮裁决为 `BLOCKING`，发现：R1A/B/C 未做加密绑定、verifier 可相信伪造 ledger、旧 listing/safety fields 未冻结、下载 receipt 脱离交易、路径未固定到 ignored tree、失败未可靠隔离、强停止测试不足、CSV 缺少禁止执行标志。

一次决定性修复加入了固定路径/ignore 预检、集成 HTTPS receipt、hash-pinned prior ledger、R1A/B/C byte seals、逐 member CRC 和独立 listing/CRC verifier；13 项定向测试通过。

## 唯一复审的剩余阻断

复审仍为 `BLOCKING`：raw transcripts 不应进入 tracked tree；强停止端到端测试不足；seals 未绑定代码/测试/`.gitignore`；部分非 `RecoveryError` 异常未统一落盘；verifier 未逐字段重建全部 transport/test/extraction report；verifier 未复核 ignore 与祖先 symlink。

## 强停止裁决

ARIS `experiment-bridge` 只允许一次修复后复审；第二次仍为 `BLOCKING`，所以本 generation 必须停止。当前代码只能作为 blocked remediation draft，不是可运行 release。不得运行 R1B/R1C，不得以 listing 零差异声称 archive recovery PASS。

测试证据：Ren 定向 `13 passed`；冻结 N0+ 环境下全项目 `379 passed`。审查阻断是证据/失败测试覆盖，不是现有测试失败。

完整报告：`refine-logs/REN_P1R1_CODE_REVIEW_20260904_220422.md`。
