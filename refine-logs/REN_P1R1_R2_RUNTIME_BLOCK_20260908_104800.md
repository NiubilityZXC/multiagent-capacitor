# Ren P1-R1 R2 真实运行阻断与根因

Run：`p1r1_20260907_170700`。R1A sealed PASS；R1B 真实完整 archive test 已执行；R1C 未运行。

官方 UnRAR 7.23 的测试结果：exit=0，stderr=0 bytes，`All OK`=1，全部 danger marker=0。原始 transcript SHA-256：`da54a7c9267ce8c7a766f43c409c4d846b4fb963472fd2f9c2c3754ee3c75e5e`，保持 ignored/local-only。

实际 transcript 包含 233 条 regular-file OK 和 4 条 directory OK，合计 237 条 `Testing ... OK`。它们与正式 listing 的完整 member path set 相同，没有未知/重复成员。原代码把全部 237 条当作 file OK，与预期 233 比较，形成 `BLOCKED_ARCHIVE_TEST` 和 `R1B_BLOCKED.json`，未生成 R1B seal，未提取任何成员。

这是输出解析分类错误，不是 RAR 解码、CRC、工具身份或 source 数据损坏。R2 的原始报告/阻断不回写、不改为 PASS；下一修复版需按已核验的 ledger type 分别检查 files/directories，保留未知路径/重复路径/文件缺失/危险输出的硬停止，并用该真实格式回归测试和独立 pre-run 复审。恢复工具、源数据、原批准范围均不改变。

R1D 独立复审尚未完成：reviewer 因额度错误中断，没有产生放行意见。静态 XLS/行解析/Data Gate 均未实际运行。

`model_or_api_executed=false`；`numeric_target_emitted=false`；P2/RUL/模型/API/GPU 未放行。
