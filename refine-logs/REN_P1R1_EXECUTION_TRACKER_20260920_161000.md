# Ren Data Gate 修复进展

时间：2026-09-20。ARIS monitor-experiment / experiment-bridge / experiment-audit。

## 当前状态

全量 schema 与组内时序审计已完成：113 来源命名候选组、233 文件、1,633 record 表、104,190,778 条记录。旧报告与独立审查保留。

全量 overlap v1 在 50 组后因 BrokenPipeError 失败，现场不覆盖。用户另批准 R2，一次新运行沿用相同覆盖、候选预算与阈值；持久日志启动器和 R2 整体 pre-run 均获独立工程复审 PASS，35 项绑定核对一致。

R2 现已实际退出 0，耗时 3944.625 秒，SUMMARY/COMPLETE 已落盘：113 组、104,190,778 行，候选对 129,364、确认投影片段 117,133。这些是程序观察数，不是独立事件数、设备数或 Data Gate PASS。

fresh 独立 post-run 审查正在执行；全量指纹、候选及匹配重建尚无最终 verdict。完整审查工件保留在 ignored data/raw/ren_scs/r2_postrun_review_20260920/。不得把候选/片段直接当作同一设备，也不得未经核验称其无害。

## 并行推进

容量目标资格的纯工步 reducer 已实现，只使用合成数据，19 新测试通过、独立工程复审 PASS。合跑 237 必测通过无跳过，一般回归 702 通过、58 跳过。完整 caller、summary 表对照及真实目标审计仍未放行。见 REN_STEP_EVIDENCE_IMPLEMENTATION_20260920.md、REN_TARGET_AUDIT_NEXT_20260920.md。

来源复核见 REN_SOURCE_RECHECK_20260920.md；明确文献子集不是独立数据集、额定值与初始值 SOH 不混用。不改动冻结实验计划。

## 实验前剩余关口

1. 完成当前独立结果对账及匹配解释。
2. 完成容量可推导性、设备/工况映射、终止/删失与 whole-unit 切分的 Data Gate。容量与 RUL 资格分开；ESR 固定 NA 不自动否定容量预测。
3. 封存 P2 精确数据、target、eval 配置，完成复审与对应放行，再运行数值基线。LLM Agent 另需安全凭据、能力探测与预算批准。

未运行真实数值目标、模型/API、GPU、RUL 或 P2。所有旧 seals 与审查保留。固定 tracker 此次完整更新；此前 09-15 内容已逐字核对保存在 REN_P1R1_EXECUTION_TRACKER_20260915_141900.md，本版另存带日期副本。MANIFEST 补记仍待环境允许局部更新。
