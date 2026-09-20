# R2 恢复记录

时间：2026-09-20 11:05 +08:00。ARIS experiment-bridge；当前不构成 release 或 Data Gate PASS。

沿用 2026-09-17 R2 批准：只允许经整体独立复审后，以持久日志启动器新建一次全量重叠审计。保留 v1 BrokenPipeError 失败现场，不改阈值、不重用半成品、不运行模型/API/P2。

## 验证

- `.venv-audit-cap/bin/python -m pytest -q` 后接 R2、durable、fleet、pipeline、index、measurement_stream、overlap、chronology、fleet_schema、workbook_reader、row_pilot 的 11 个明确测试文件：218 passed，0 skipped，3.71 秒。
- 初次一般回归未限定收集目录，误收集 ignored 历史测试副本，2376 collection errors，1 skipped，exit 2；此调用失败，不作为通过证据。未删除历史副本。
- 正确调用 `.venv-n0-plus-sn0/bin/python -m pytest -q tests`：683 passed，58 skipped，40.94 秒。必需 xlrd 路径另由上述隔离必测覆盖，不能把 58 skipped 写成全部执行。
- 当前 Git 基线 c6ea238；磁盘剩余约 678 GiB，高于沿用的 40 GiB 门槛；最终以子进程 preflight 为准。
- 新 fresh gpt-5.6-sol / xhigh 集成 reviewer 已启动，属于 same-family provisional engineering；本记录写入时尚无 verdict。

## 留痕限制

内置 apply_patch 与 shell 中 apply_patch 的 Update File 都因 bwrap `Failed RTM_NEWADDR` 不能读取旧文件；Add File 可用。本记录补充旧的固定 tracker 与 MANIFEST，不声称已更新它们。旧 tracker 的 09-15 内容不能视为当前进度。后续以本轮带日期报告、release 和实际运行回执为准。

R2 尚未启动；不以 PID、测试通过或 reviewer 文字代替实际数据运行、退出码及独立结果核验。
