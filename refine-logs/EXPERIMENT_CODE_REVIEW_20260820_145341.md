# AUDIT-Cap 实验代码独立审查（首轮）

**审查时间**：2026-08-20 14:53:41 +0800  
**审查方式**：fresh、零上下文独立代码审查；只运行项目根目录定向测试，不以 vendored 测试替代本项目验收。  
**结论**：**BLOCKED，修复后必须再审一次，未授权真实数值裁决。**

## 已通过的核心检查

- 外层按整只 surrogate unit 做 LOCO，内层验证单元会从全局拟合中排除；未发现行级随机切分。
- `context=4` 时 11 个观测点对 h=1/2/3 分别产生 7/6/5 个原点，目标索引为 `origin+h`，现有测试覆盖该约定。
- 成熟标签来自 held-out unit 的真实后续观测，不是模型生成值；Stress-2 的 5 个容量区间越界、0 个 ESR 越界以及未知终止处理保持保守。
- MASE 分母来自 outer-train units 的一阶差分；指标先单位内聚合、再单位宏平均。相对 last-value 指标没有冒充标准 MASE。
- 设计仿真的 10% 乘法效应与 Holm step-down 实现代数上正确；quick 状态固定为非裁决，RUL 保持 NA。

## 阻断项

1. **HDF5 外部数据越界**：external storage 与 VDS 在数值扫描中可能读取 ZIP/MAT 之外的 payload。必须默认隔离，数值扫描不得解引用外部源，并增加 external/VDS 测试。
2. **“字节匹配”证据不足**：提取 MAT 与 ZIP member 只比较 size+CRC32，却宣称 byte match。必须对 ZIP 解压字节流与提取文件分别做 SHA-256 并逐一相等；CRC 仅作辅助。
3. **预测未在标签访问前持久封存**：预测和 actual maturity 在同一循环中构造，结束后才批量写 CSV。必须拆成 blinded 两阶段，prediction ledger 逐行 append、fsync、hash-chain 并 seal 后，独立 label/maturity 阶段才可读标签。
4. **失败公平性不完整**：候选选择或状态拟合可在 try 外中止整跑，聚合默认跳过 NaN。任何 planned key 的配置、拟合、预测或成熟失败都必须显式 FAIL/NA，聚合不得把失败样本静默删除。
5. **预测 lineage 不足**：prediction ID 与 train-set hash 未覆盖 protocol/code/raw-data/split/seed/因果前缀。必须纳入这些哈希以及训练快照、特征输入快照，防止不同运行碰撞。
6. **设计 missingness 被改写**：全缺失 mask 时强制首点 observed，会高估可用性。必须显式 FAIL/NA 或在冻结协议中预注册条件抽样；禁止伪造观测。
7. **设计协议 effect grid 冲突**：文档一处要求 0/-5/5/10/15%，另一处 quick 仅 {0,10%}+伤害哨兵。数值执行前必须版本升级并明确 quick 与 formal cells。
8. **B0 不是完整 Data Gate**：当前审计器只是完整性/schema 扫描器，尚未生成物理 unit/event/termination/duplicate 账本，也未解析 reference payload。它可作为 partial integrity scanner，不能被表述为 B0/C1 或 Data Gate 完成。

## 非阻断但必须显式处理

- `rho` 是模型特异残差相关，不是总误差/单位损失相关；需要改名并报告 realized correlation。
- runner-up 检验存在选择后推断限制；正式模拟须校准整个选择规则或改为闭合/maxT 方案。
- seed 不应包含 repeats 预算；否则 200→2000 不保留前 200 条随机流。
- `confirmatory_eligible` 容易被误读；只能称 unit-count minimum met，且 quick 永远不是 Gate 证据。
- Stress-2 的 unverified-data bypass 必须在每个工件盖章且禁止 claim/gate，或从正式模式移除。
- 数值线程需要在导入 NumPy/sklearn 前固定并记录有效 thread pools。
- 空 failure ledger 也必须有稳定 schema；完整运行需要 COMPLETE 标志和全部工件清单。
- `global_drift` 实际是 held-unit 长历史漂移，应改名或明确定义；context 3/5 敏感性需要独立运行清单。
- 大包数值扫描要区分 HDF5 openable 与 payload scan complete，并增加资源上限/循环保护。

## 修复后验收

修复后只运行项目定向测试、`py_compile`、`git diff --check`，并由同一独立审查者进行一次 post-fix re-review。只有全部阻断项关闭后，才允许执行 Stress-2 真实回放与 quick design simulation；Benchmark L 和 RUL 仍须由 Data/Outcome Gate 单独授权。
