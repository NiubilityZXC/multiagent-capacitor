# 工步汇总表对照纯函数：实现与验证

日期：2026-09-21。ARIS experiment-bridge；范围仅合成输入，不是完整 XLS caller、真实审计 release 或 Data Gate。

## 实现边界

新增 `experiments/audit_cap/ren_step_summary_join.py`，复用已审的连续工步 reducer。输入为 canonical 记录与 6/8 字段 canonical 工步汇总行；未来 XLS adapter 仍须独立验证表头、单位、单元格类型和来源位置。

逐 `(cycle, step, status)` 保留所有记录段和 summary 行的索引。重复键标为歧义，缺失和额外键分别登记；不取首条、不覆盖、不随意聚合。只有一对一键才输出观测差值。

时间同时对照末端局部时钟与采样起止差，未将任一值自动认定为仪器工步持续时间。电压端点缺失保持 None；mAh 保持 mAh，不生成 F、SOH 或 RUL。当前 record 表示没有 energy，所以保留 summary energy，但明确不做 energy 比较。

所有输入完整耗尽后才返回；类型/非有限值错误和晚到异常直接失败；不输出容差裁决或 target 资格。内存与工步段/汇总行数成正比，不缓存完整原始记录序列。

## 已执行测试

- 两个纯函数组件：38 passed，0.29 秒。
- 新组件及相邻 chronology/measurement/overlap/durable 模块：172 passed，2.58 秒；专用 `.venv-audit-cap` 环境，无跳过。
- 全项目一般回归：721 passed、58 skipped，45.30 秒；`.venv-n0-plus-sn0/bin/python -m pytest -q tests`。这些是合成/工程测试，不是真实预测精度。
- fresh GPT-5.6-Sol xhigh 独立工程复审 PASS，无阻断；审查者自行运行 38 passed in 0.24s，并完成独立迭代耗尽/键对照 probe。类别 same-family provisional，仅覆盖纯组件，不放行真实数据。
- 完整 Ren 审计测试与持久日志测试：406 passed，10.91 秒；专用审计环境，无跳过。
- 完整审查原文 ignored：`data/raw/ren_scs/step_summary_join_review_20260921.md`；SHA-256 `07b083b45671e2741c72acb7f43481ed0b7a24b0aa291baf1b67e469bb7d9ede`。

## 版本与下一步

- implementation SHA-256：`396379973368560d48d44eaecfc63e40e9bafebd41f481a972e70752a0354c17`。
- tests SHA-256：`37d48c7d3598c47c3f2db49857ec1c9c2fb51837957c3192738922abde0740eb`。

完整 caller、源位置/energy 采集、cycle 汇总对照、独立字段重建与端到端 Workbook 对抗测试仍须实现和整体 pre-run review；本组件不代替它们。R2 post-run 另行独立收尾。没有改动任何 R2 seal、原始数据或 P2 评测计划，没有调用模型/API。
