# Ren Data Gate 修复进展

日期：2026-09-22 14:17 +08:00。ARIS experiment-audit / experiment-bridge。沿用 P1-R1 与 R2 批准；未开启模型/API/P2。

## 已完成

全量 schema、组内时序、R2 overlap 生产运行已经完成，覆盖 113 命名组、233 文件、104,190,778 行。R2 独立审查现已收尾：工件 composite PASS、overall WARN，无 R2 观察工件完整性阻断。不是 Data Gate PASS。详见 REN_OVERLAP_R2_POSTRUN_AUDIT_20260922.md；四次诊断及旧生产失败现场全部保留。

确认的投影相同只涉及 batch3/22 与 batch3/23，两组各 1,523,379 行；117,133 是 anchor-derived 匹配账本行，不是独立事件数。不能自动合并、排除或当作独立设备分开切分。

09-22 执行者对已有、哈希绑定的 chronology 075.json / 076.json 做只读补充对照：两组 24 个 sheet 的所有摘要字段（除 member_path）及 aggregate metrics 一致。这不是逐行 native-key 比较，也不属于此前独立报告的新增 verdict；物理身份仍未裁决。按 source_naming_candidate 定位组，不能混用不同审计目录的编号。

容量资格审计已完成三个经独立组件复审的模块：连续工步 reducer、工步 summary join、Workbook-byte record/step/cycle event adapter。新 adapter 支持全部已观察布局与原生位置/energy，50 项合成集成/逐字段对抗测试通过；完整 Ren 审计回归 456 passed、无跳过。一般环境 721 passed、108 skipped，缺 xlrd 的新增测试在专用环境真实覆盖。详见 REN_TARGET_WORKBOOK_IMPLEMENTATION_20260922.md。

组级 bytes-loader 已接通并经独立复审 PASS：跨片工步连续、逐事件来源覆盖、energy 端点对照、周期全部成员保留；容量端点求和仍明确为未验证语义假设。修复了保留异常 traceback 时的延迟释放问题。最终 Ren 回归 469 passed、无跳过，一般回归 721 passed、121 skipped。详见 REN_TARGET_GROUP_IMPLEMENTATION_20260922.md。两个新组件的完整 trace 已保存，compact events 因原地补丁环境故障单独放在 .aris/meta/pending-events/，没有覆盖旧事件索引。

## 尚未完成、不能省略

1. 接成外层 source-bound fleet caller，复用现有容器检查和持久日志启动器；完成持久化字段独立 verifier、固定覆盖/预算/release 及整体端到端对抗测试。组级合成接口完成不等于此入口完成。
2. 整体 pre-run review 后按批准边界最小 sanity，再执行必要容量资格审计；不重做 archive/解压/schema/overlap。
3. 裁决重复投影对、容量可推导性与 whole-unit/工况切分，完成 Data Gate。ESR 固定 NA；RUL 单独资格，不自动阻止容量任务。
4. 封存精确 P2 数据、target、eval 并按既有规则放行数值基线；LLM 另需安全凭据、能力/预算 Gate。

当前没有后台真实扫描或模型作业。昨日额度中断不计作测试/审查通过。旧 tracker 的 09-20 与 09-22 较早副本均保留；本版另存带时戳副本。已有 1–2 天估计是有条件有效工作量，不是保证开跑日期，重复投影的处理仍须证据裁决。
