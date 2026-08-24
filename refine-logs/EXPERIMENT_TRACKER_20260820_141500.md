# Experiment Tracker: AUDIT-Cap v0.2

**Updated**：2026-08-20  
**Execution policy**：按物理器件、严格因果回放；Data/Design Gate 未通过的结果族保持 BLOCKED 或 NA。

| Run ID | Milestone | Purpose | System / Variant | Split | Metrics / Artifact | Priority | Status | Notes |
|---|---|---|---|---|---|---|---|---|
| R000 | M0 | 官方大包下载与字节核验 | resumable raw download | N/A | bytes, headers, SHA-256 | MUST | RUNNING | 目标字节数 5,038,942,729；断点续传 |
| R001 | M0 | ZIP 完整性 | ZIP CRC | N/A | unzip -t, member manifest | MUST | TODO | R000 完成后 |
| R002 | M0 | MAT 完整性与容器识别 | ES10/12/14 | N/A | SHA-256, file type, HDF5 open | MUST | TODO | 不假设字段语义 |
| R003 | M0 | HDF5 schema 审计 | recursive object inventory | N/A | HDF5_OBJECTS.csv, quarantine | MUST | TODO | 记录 class/shape/dtype/ref/attrs |
| R004 | M0 | 物理器件/事件/终止审计 | canonical ledger | duplicate-group isolation | DATA_MANIFEST/AUDIT_SUMMARY | MUST | TODO | 决定 Data Gate |
| R010 | M1 | Stress-2 parser/标签 sanity | deterministic canonicalizer | LOCO-ready | 6×11, event labels | MUST | TODO | C ratio=1-loss/100；ESR ratio=1+increase/100 |
| R011 | M1 | 因果 rolling replay | context 4, h=1/2/3 | 6-fold LOCO | prediction/maturity ledger | MUST | TODO | context 3/5 敏感性 |
| R012 | M1 | 泄漏与时序哨兵 | intentional leak controls | group-disjoint | invariant test report | MUST | TODO | 失败预测不得静默删除 |
| R020 | M2 | 快速设计仿真 | 200 repeats/grid | physical-unit simulation | error/power/coverage diagnostics | MUST | TODO | 仅检验实现与极端边界 |
| R021 | M2 | 正式设计仿真 | ≥2,000 repeats/grid | physical-unit simulation | error/power/coverage diagnostics | MUST | TODO | 参数由 R004 实际结构冻结 |
| R030 | M3 | 锚点基线 | last-value | nested LOCO rolling | unit-macro metrics | MUST | TODO | 手算核验 |
| R031 | M3 | 全局漂移 | global drift | nested LOCO rolling | unit-macro metrics | MUST | TODO | event-index；禁用未来真实时刻 |
| R032 | M3 | 局部线性 | k∈{2,3,4} | inner-LOCO select | unit-macro metrics | MUST | TODO | common-origin keys |
| R033 | M3 | 指数趋势 | log-linear | inner-LOCO select | unit-macro metrics | MUST | TODO | 正值 ratio，约束为预注册变体 |
| R034 | M3 | 状态空间 | causal local-trend KF | inner-LOCO select | unit-macro metrics | MUST | TODO | filter only，禁止 RTS |
| R035 | M3 | 传统 ML | ridge causal increment | inner-LOCO select | unit-macro metrics | MUST | TODO | 只在 sample/design gate 允许比较 |
| R040 | M4 | 大包 C/ESR 锚点 | last-value | within-voltage LOCO | frozen primary + secondary | MUST-COND | BLOCKED | 等待 Data Gate + Freeze B |
| R041 | M4 | 大包趋势基线 | best simple trend | within-voltage LOCO | frozen primary + secondary | MUST-COND | BLOCKED | 外层结果不得调参 |
| R042 | M4 | 大包状态空间 | selected KF | within-voltage LOCO | frozen primary + secondary | MUST-COND | BLOCKED | 测试期仅状态更新 |
| R043 | M4 | 大包 ridge | causal ridge | within-voltage LOCO | frozen primary + secondary | MUST-COND | BLOCKED | 等待 sample/design gate |
| R050+ | M5 | 条件测量桥/Agent 扩展 | frozen challenger | separate estimand | shadow evaluation | NICE | BLOCKED | 需要新的人工检查点 |
