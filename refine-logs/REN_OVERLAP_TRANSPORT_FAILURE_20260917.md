# Ren 全量重叠审计：传输故障与修复

## 已证实的失败状态

2026-09-17只读核验：`overlap_fleet_20260915_v1` 的BLOCKED回执为 `BrokenPipeError`，group=`batch2/22`，groups_indexed=50。本地有50份组回执，合计11,932,996条记录，SQLite group表也为50项。runtime.log只留到48/113，未记录实际child_returncode；SUMMARY和COMPLETE均不存在，未发现仍在运行的原入口进程。

BLOCKED.json SHA256：`4088156530860dd17421312c901371006143f4c23e651eafe828612490811200`。全部29项冻结policy文件仍与release逐字节一致。

这是未完成运行，不是数据重叠结论或Data Gate通过。50份回执不等于完整索引和跨组匹配已核验；原始spool/index/log保留，绝不覆盖或删除。

## 根因边界

原启动层将任务输出通过 `tee` 连接工具会话。pipeline在组证据提交后执行进度print；持久化组数50而日志停在48，与输出管道接收端消失一致。BrokenPipeError可确认输出管道故障，但当前没有OS事件记录，不能断言具体由哪一次用户消息或宿主生命周期动作触发。

## 已实施的启动层修复

新增 `experiments/audit_cap/durable_local_job.py`，不修改冻结数据代码。以新session启动supervisor，stdin为DEVNULL、stdout/stderr直接写普通本地文件、close_fds=True；supervisor等待实际child退出并另写RETURNED.json。原父进程退出不再使子进程依赖tee管道。

目录只能新建；没有自动retry/resume或数据资格提升。STARTED/PID仅表示启动，只有实际child_returncode及后续审计输出对账才能说明完成。宿主重启/强杀supervisor仍可能只留下STARTED；这种情况必须视作未完成而非成功。不得把凭据放进argv，因为REQUEST.json保存参数；本项目用途仅为本地P1审计。

合成测试：4 passed，覆盖父进程退出后子进程继续输出、stdout/stderr落盘、exit0/exit7、原目录拒绝重用、找不到可执行文件不写成功回执。独立工程复审待收取，不放行真实重跑。

## 新运行的批准请求

旧冻结政策明确“不自动改阈值或重试”，因此本次没有重新启动真实任务。

请求批准 R2：在保留失败v1和全部旧release的前提下，为 `overlap_fleet_20260917_r2` 新建独立入口/政策/release，使用本次持久日志supervisor。保持原113组/233文件/1633表/104190778行、精确32行投影规则、1000000候选预算、40GiB空间门槛不变；不复用未完成索引、不修改判定规则。新入口、端到端对抗测试和独立pre-run review通过后，才执行一次新目录全量审计。

批准不包含模型、API、GPU、numeric target、RUL或P2；之后仍需目标/身份/切分资格及既定P2批准。建议回复：`批准 R2：保留失败现场，使用持久日志启动器，经独立复审后重跑全量重叠审计。`
