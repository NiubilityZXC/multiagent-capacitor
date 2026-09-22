# 容量资格审计：跨 Workbook 组级整合

2026-09-22。ARIS experiment-bridge；仅合成实现与验证，尚无真实扫描 release。

## 已接通的路径

`ren_target_group.collect_group` 接受外层已确定顺序的 member 清单、各自 schema、允许 BIFF 集合及隔离 Workbook 字节 loader；自身不打开路径，不替代容器来源/批准检查。

对每个来源一次消费所有 record/step/cycle 事件，按 schema 逐个核对类别与原始位置；少行、多行、错位、重复来源或晚到读取失败都不能返回完成。跨 sheet/文件持续累计 native 工步，不重置工步状态。来源信息绑定到每条 summary 及工步首末位置。

原始记录不整组缓存，内存随工步/summary 数增长。新增每工步首末 energy 与缺失行数；仅唯一匹配且所有记录 energy 存在时输出 summary-minus-endpoint energy 差值，不补零、不自动设容差。

周期保留所有工步与所有周期汇总行索引；正、负、零、混合电流工步分别列明，不按 status 编码臆断。唯一周期汇总的容量与同符号工步末端 mAh 和之差，仅为明确标记的算术假设（sum_semantics_verified=false），不是仪器语义或容量 target。重复周期行不会被选首条或覆盖。比较字段按复审建议命名为 `cycle_capacity_minus_current_sign_bucket_endpoint_sum_mAh`，没有给 mAh 取正负号。

只登记 last_observed_cycle；不把末点当失效，不声称最后周期完整，不生成 F/SOH/RUL。所有 target/identity/Data Gate/P2 flags 保持 false。

## 实际测试与失败记录

首轮新测试为 1 failed、7 passed：测试试图给 fixture 的 tuple 项赋值，尚未执行该案例的组级逻辑。改为修改 tuple 内部测试列表后，组级与 adapter 合跑 58 passed（0.28 秒）。随后增加边界用例。

另复现了一项真实资源释放缺陷：reducer 在记录编号 10→12 时抛错，保留异常 traceback 会使 Workbook 流延迟关闭。独立 reviewer 确认修复前为阻断。现显式持有 record_rows iterator 并在 collect_group finally 内关闭；新增保留异常对象的回归，证明无需依赖 GC 才释放资源。

最终版组级测试：13 passed（0.23 秒）。完整 Ren 审计与持久日志回归：469 passed、无跳过，11.08 秒。一般环境回归：721 passed、121 skipped，41.34 秒；新增 13 个组级测试在缺 xlrd 的一般环境跳过，已由专用环境实际覆盖。

独立审查首次因额度中断为 ERROR，14:00 后恢复同一 reviewer。最终 fresh GPT-5.6-Sol xhigh 复审 PASS，无剩余组件阻断，修复前资源释放 blocker 保留。独立定向测试 78 passed（0.33 秒）。same-family / provisional，不是实际数据资格放行。

完整报告 ignored：`data/raw/ren_scs/target_group_review_20260922.md`；SHA-256 `a137beb661fdd96c05cf45fd671221d7642404df9175fb26873707eab29d285e`。完整 trace 位于 `.aris/traces/experiment-bridge/2026-09-22_run01/`。

## 最终版本与后续

- implementation SHA-256：`575f63f786796ed4c56a169d3d00052fe1b1c3509398f791f084498f6e5acdcc`。
- tests SHA-256：`88b92556b95e93e3a2c06272ab7a95fb8348e98d72310aba01c2f71ce63f8238`。

完整 source-bound fleet caller、持久化输出字段的独立 verifier、精确 release/覆盖/预算以及整体 pre-run review 尚未完成；本组件不是执行入口。后续复用现有来源保护与持久日志启动器，不重跑 R2 overlap、不改 R2 seals、不自动处理重复投影对。模型/API/P2 均未运行。
