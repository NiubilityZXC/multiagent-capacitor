只读审查结论：当前两个实现都不能标为 `production-ready`。

- A：`experiments/api_hybrid/arkcli_adapter.py` 只是独立的 subprocess 原型，未接入 formal `CAPAccuracyRun`；formal runner 仍只接受 `MockProvider`（`runner.py:58, 860-869`）。
- B：`BlindReplayService` 仍在预测进程内持有完整 `_events`（`replay.py:138-188`），不构成真实隔离。
- `experiments/vfps_agent/schemas.py` 当前不存在；formal arm 响应语法实际应从 actions/verifier 生成，不能拿 `api_hybrid/schemas.py` 的“凸组合权重”schema 代替 direct/action/IF arm。
- 因此当前最准确的标签仍是 `RELEASE_MOCK_ONLY`。

## A. Production Ark adapter blocking acceptance checklist

### A1. 接入与类型边界

- 定义 formal `AccuracyProvider` protocol，唯一入口保持 `invoke(canonical_packet_bytes, AttemptStart) -> ProviderResponse`。
- `CAPAccuracyRun` 不得通过 duck typing 接受任意未绑定 provider；adapter 必须暴露不可变 `binding_manifest`，runner 在写 `STARTED` 前验证其 hash。
- `api_hybrid` 的 `ProviderResult/status=str` 接口不能直接桥接；必须转换到 `AttemptStatus`、`UsageStatus` 和 closed error enum。
- D1-RAW、D1-PACKET、H1/RF1/RC1/ACT1/IF1 分别绑定自己的 prompt、response schema 和 grammar；任何跨 arm schema 复用都拒绝。

### A2. 冻结值必须由可执行对象重算

不能只比较调用者给的 64 位字符串。adapter 必须从以下实际对象重算并逐项匹配 `PolicySpec`：

- exact instruction/system prompt bytes → `prompt_hash`
- exact arm-specific strict JSON Schema → `response_schema_hash`
- exact packet schema → `packet_schema_hash`
- exact decode object，包括 thinking、temperature、top-p、token ceiling 等 → `decode_parameters_hash`
- exact requested model及允许的 returned-model rule → `model_version_rule_hash`
- exact HTTPS method、host、path、redirect/TLS/cache/store/tool policy → `provider_rule_hash`
- authenticated capability snapshot的规范化内容 → `capability_snapshot_hash`
- registry、grammar、fallback、budget、verifier继续复用现有 runner 验证

需要保存可公开的非秘密 binding manifest 和 hash；不能保存 key。

### A3. 请求体机械绑定

传输 spy 必须能够证明：

- HTTP method、approved host/path、非秘密 headers 和 canonical semantic body 与 golden bytes 完全一致。
- packet bytes 的 SHA-256 等于 `AttemptStart.packet_hash`。
- request 中 `model`、instructions、response schema、decode、`max_output_tokens` 全部来自已冻结对象。
- `max_output_tokens == attempt.requested_tokens`，不能另用 adapter config 的独立值。
- `tools=none`、store/cache/retrieval/file/search 均显式关闭；没有 server-default 模糊项。
- 不加入 timestamp、随机 prompt、动态 routing 或其他未冻结科学字段。鉴权签名时间可以动态，但必须与 semantic body 分离审计。
- 若继续使用 CLI，必须证明 CLI 实际发送的 body；仅证明 `_argv()` 内容不够。CLI 无法提供该证据时应使用直接 HTTP transport。

### A4. 模型身份

- requested model 必须存在于已冻结 authenticated capability snapshot。
- returned `model` 字段必须存在；当前 `response.get("model") or self.config.model`（`arkcli_adapter.py:228`）必须删除。
- 默认 exact equality；若允许版本别名，别名集合必须在打开 outer score 前冻结并属于 capability snapshot。
- 缺失、大小写/空格变化、未知 alias 或其他模型都映射为 `MODEL_MISMATCH`，响应内容不得执行。
- 记录 exact returned-model 的 hash，不记录自由文本。

### A5. accuracy_v1 尝试与时间语义

- accuracy adapter 内部以及 HTTP/SDK 层 retries 必须为零。当前默认 `max_network_retries=1`（`:31, 136-167`）违反 formal protocol。
- timeout、429、5xx、连接重置、DNS/TLS 失败和“请求可能已送达但响应未知”均消耗该 slot，不能 resend。
- resume 看到任何既有 `STARTED` 必须零网络调用。
- deadline 由受信本地 wall+monotonic clock实施；不得信任 provider 时间或调用者可伪造的 completion time。
- 调用开始时已过 deadline：不发送，闭合为 fallback。
- deadline 后收到的完整响应：内容直接丢弃，`late=True`，commit common fallback。
- subprocess timeout必须终止并回收整个进程组，避免孙进程稍后返回或写缓存。

### A6. 响应与 usage

- outer envelope 与 inner arm response均使用 duplicate-key/NaN/Infinity 拒绝的 strict parser。
- 设置最大 response bytes、最大嵌套深度和 UTF-8要求。
- missing/extra planned key、非法 action、非法 quantile、局部 bundle 都触发 whole-origin `ERROR_FALLBACK`，不能部分接受。
- usage只接受闭合字段中的非负整数；bool、字符串、负数、溢出值均不能记为 measured usage。
- 有效预测但 usage 缺失：允许预测，记 `UsageStatus.UNKNOWN`，自动失去 matched-actual-spend claim。
- reported output tokens 超过 ceiling：记 budget/protocol failure并 fallback。
- raw response、reasoning、stdout/stderr、traceback均不得进入 ledger或公开日志。

### A7. 凭据与运行时

- base URL必须校验为预批准 HTTPS scheme/host/path，禁止 redirect。
- CLI binary使用绝对路径、regular-file检查和冻结 SHA/version；禁止 PATH lookup。当前使用裸 `"arkcli"`（`:77-80`）不足。
- child env必须是 allowlist，不得 `dict(os.environ)` 全继承（`:49-67`）。
- key只出现在指定 secret channel；packet/prompt不能进入 argv。当前 prompt在 argv末尾（`:107`），会暴露于进程列表。
- 使用隔离临时 HOME/config/cache，`close_fds=True`，权限 `0700/0600`。
- 多个 secret canary以及任意 provider text均不能进入异常、ledger、seal或测试输出。

### A8. 必须冻结的失败映射

| 情况 | formal结果 |
|---|---|
| 本地binding/preflight失败 | `ERROR` + common fallback；零传输但slot已闭合 |
| transport/HTTP/CLI失败 | `ERROR`，usage unknown，common fallback |
| deadline无响应 | `TIMEOUT`，usage unknown，无重试 |
| deadline后响应 | `late=True`，忽略内容，common fallback |
| returned model缺失/不符 | `MODEL_MISMATCH`，忽略内容 |
| outer envelope不合法 | `ERROR`，忽略内容 |
| outer合法、arm语义不合法 | whole-origin `ERROR_FALLBACK` / `INVALID_RESPONSE` |
| 输出有效、usage缺失 | prediction可用，`UsageStatus.UNKNOWN` |
| crash后存在`STARTED` | `CRASH_RECOVERY` fallback，零 resend |

## B. Process-isolated evaluator blocking acceptance checklist

### B1. 真正的权限隔离

- 仅使用 `multiprocessing.Process` 不够；预测器与 evaluator 必须是不同非特权 UID、容器或等效 mount/user namespace。
- evaluator独占 raw suffix、labels、censor/EOL、private unit identity及真实split membership。
- 预测器不得挂载这些目录，不继承其 fd，不能通过 `/proc/$pid/{environ,fd,mem}`、ptrace、shared memory或临时目录访问。
- raw路径、最终长度和私有身份不能出现在 argv/env/IPC错误。
- root/operator仍可绕过隔离，因此论文只能声称“运行时harness-enforced causal access”，不能声称研究人员密码学不可见公开数据。

### B2. 推荐的信任结构

- `trusted supervisor`：持有ledger写权限、冻结policy和provider adapter，但不持有suffix。
- `forecast worker`：只接收一个canonical causal packet并返回typed response；无ledger/raw权限。
- `event evaluator`：持有完整stream和独立durable session state，只接受supervisor签发/自身提交的checkpoint capability。
- `post-seal scorer`：仅在全generation预测封存、forecast workers退出或权限撤销后获得labels并生成maturity/metrics。

仅把自洽 SHA ledger交给 evaluator 不够；任何写者都能整体重算 hash chain。checkpoint必须由 evaluator/supervisor拥有的不可伪造 capability/MAC签发，或由 evaluator自己原子写入。

### B3. IPC状态机

- strict canonical、长度受限、版本化协议；闭合错误码，不返回traceback、路径或event count。
- 请求必须绑定 `run/session/generation/fold/policy/origin/packet/checkpoint/request_nonce`。
- client不得提供 file path、label index、target truth、horizon maturity或任意event index。
- 唯一合法转换：bootstrap prefix → committed current-origin checkpoint → reveal `origin+1`。
- 同一checkpoint重复调用必须是幂等恢复：返回同一已提交结果，不能简单报错，也不能再次推进。
- stale、跨run、跨fold、跨generation、未来origin和乱序checkpoint全部拒绝且状态不变。

### B4. reveal前验证

当前 `_verify_checkpoint_for_reveal`（`replay.py:101-135`）只检查部分prediction/execution引用，不验证完整 attempt lineage及 committed prediction语义。production evaluator必须在每次reveal前验证：

- STARTED→FINISHED→prediction→per-key execution→checkpoint完整链
- policy、arm、packet、origin、attempt slot和deadline binding
- exact planned-key集合和whole-origin response
- `_validate_committed_prediction` 等价语义检查
- checkpoint是当前session唯一下一步
- commit已经durable并且早于event-service transition

### B5. 原子性、并发与恢复

- evaluator state transition和“哪个event被reveal”必须在返回响应前 fsync/transaction commit。
- crash-before-commit：重试可执行一次。
- crash-after-commit-before-reply：同nonce/checkpoint重试返回同一event，不再推进。
- 同checkpoint的多线程/多进程并发只产生一次transition。
- 每session仅允许一个active evaluator writer；origin N+1不能越过N。
- predictor在 STARTED、FINISHED、prediction、checkpoint或收包前任一点崩溃，恢复均不得重发API请求，也不得丢失已授权prefix。

### B6. 文件与TOCTOU

`read_verified_ledger_records()` 目前先verify再按路径重读（`ledger.py:756-765`），存在换文件TOCTOU。production evaluator必须：

- 用同一已验证fd/inode读取一次，或把artifact原子导入 evaluator-owned store。
- 使用固定directory fd + `openat/O_NOFOLLOW`，验证owner、mode、device/inode/link count。
- predictor不能在 evaluator verification期间替换、truncate或append被验证文件。
- 不允许client控制路径；symlink、hardlink、rename swap、mount swap全部fail closed。
- hash chain只算tamper evidence；没有 evaluator-owned authority/MAC时不能算真实性。

### B7. label与全局seal

- label只能由 evaluator根据真实dataset、冻结target derivation、`origin+horizon`和missingness生成；client输入一律无权影响。
- maturity必须覆盖所有planned executions；fallback仍保留，所有arms使用同一个matured denominator。
- 在全部outer folds/generation prediction seal前，任何 label、loss、排名、aggregate score查询都拒绝。
- maturity/label ledger写入 evaluator/scorer-owned目录；forecast worker无读取权限。
- score开放后任何policy/prompt/model改变必须进入新generation，旧outer结果降级development。

## 可执行 blocking adversarial tests

1. `test_prod_adapter_recomputes_every_policy_binding_before_transport`
   分别单bit修改prompt/schema/decode/model/provider/capability artifact；断言transport调用为0且slot闭合fallback。

2. `test_semantic_wire_request_equals_frozen_golden_bytes`
   spy transport捕获method/host/path/body；逐字节匹配golden，并验证没有tool/store/cache/default/random字段。

3. `test_arm_response_schema_swap_is_rejected_preflight`
   将D1 schema装到ACT1、IF1装到H1；断言零发送或closed binding failure。

4. `test_returned_model_missing_alias_or_mismatch_fails_closed`
   参数化missing、不同大小写、尾空格、未知alias、另一模型；均`MODEL_MISMATCH`，只有冻结exact ID成功。

5. `test_accuracy_transport_faults_make_exactly_one_send`
   参数化timeout、reset、429、500、invalid TLS、ambiguous-after-write；每个attempt send count恰为1，恢复后仍为1。

6. `test_local_deadline_discards_late_valid_payload`
   fake clock在deadline前后返回同一有效response；late分支不得执行response，commit common fallback。

7. `test_response_parser_rejects_duplicate_keys_nan_extra_missing_and_oversize`
   参数化outer/inner恶意payload；断言whole-origin fallback、无raw内容落盘。

8. `test_usage_parser_never_trusts_bool_string_negative_or_over_ceiling`
   非法usage不得成为REPORTED；缺失usage按冻结规则为UNKNOWN；超token ceiling触发protocol failure。

9. `test_binary_endpoint_redirect_and_capability_drift_are_pinned`
   PATH劫持、binary symlink/hash变化、host/path变化、redirect、snapshot不含模型；全部零合法发送。

10. `test_secret_packet_and_provider_canaries_never_escape`
    多个环境secret、response/reasoning/error canary；扫描argv、允许外的child env、temp、ledgers、seals、stdout/stderr，均不得命中。

11. `test_concurrent_same_attempt_has_one_started_and_one_physical_send`
    两个进程同时运行相同attempt；一个获得writer authority，最终一个STARTED/FINISHED/commit和一次传输。

12. `test_predictor_uid_has_no_raw_label_or_inherited_fd_authority`
    恶意worker尝试open/stat/list raw目录、继承fd、读取evaluator `/proc`；全部失败，正常IPC仍可用。

13. `test_cross_process_suffix_metamorphism`
    两个私有stream前缀相同、suffix/termination/final length不同；在合法reveal前所有packet bytes、public state和closed IPC输出一致。

14. `test_ipc_rejects_full_series_final_length_arbitrary_index_and_path_traversal`
    发送额外字段、负/超大index、label请求、路径和超大frame；closed error、state hash和revealed_count不变。

15. `test_self_consistent_rehashed_forged_checkpoint_is_not_authorized`
    恶意预测器重建完整自洽SHA ledgers但无supervisor/evaluator capability；必须拒绝，证明hash不是authority。

16. `test_checkpoint_cannot_cross_run_fold_generation_or_origin`
    复用另session的真实checkpoint及乱序future checkpoint；全部拒绝且无reveal。

17. `test_duplicate_and_concurrent_checkpoint_is_exactly_once_idempotent`
    N线程/进程提交同nonce；durable transition恰一次，每个成功恢复者获得同一event，不出现“客户端丢event后无法恢复”。

18. `test_evaluator_crash_failpoint_matrix`
    kill点覆盖 journal前、写中、fsync后、reply前、reply中；重启后为0或1次transition，绝不2次。

19. `test_predictor_crash_failpoint_matrix_never_resends_provider`
    覆盖STARTED后、FINISHED后、prediction后、checkpoint后、reveal reply前；恢复prefix正确且API send count不增加。

20. `test_two_evaluators_and_out_of_order_requests_are_serialized`
    同session启动两个evaluator、并发N/N+1；只允许一个writer及合法顺序。

21. `test_verified_fd_cannot_be_swapped_between_check_and_read`
    在verify/read钩子间rename替换为另一regular file、truncate或append；必须拒绝或继续使用原已验证inode，绝不reveal。

22. `test_symlink_hardlink_and_client_path_attacks_fail_closed`
    针对ledger、seal、socket和private store；不得读写根目录外对象。

23. `test_global_prediction_seal_blocks_all_label_and_score_access`
    单origin/fold封存后仍请求score；必须拒绝。全generation封存、worker退出后仅scorer可成熟一次。

24. `test_evaluator_ignores_client_supplied_label_and_preserves_common_denominator`
    注入错误label/horizon/maturity，并让不同arms成功/失败；真实label仍由dataset产生，各arm planned/matured key集合完全一致。

25. `test_ipc_error_and_log_canaries_do_not_leak_suffix_or_identity`
    suffix数值、unit ID、raw path和终止原因canary不得进入预测进程可见错误、日志、metrics-before-release。

## Nonblocking，但限制宣传范围的测试

- 10k–100k origin crash/concurrency soak：失败不必阻止最小论文实验，但阻止“operationally robust”。
- evaluator隔离额外CPU/latency/RSS benchmark：失败阻止“low-overhead”。
- IPC错误大小与响应时间的side-channel统计：未做只能声明内容隔离，不能声明side-channel hardened。
- local filesystem与容器环境支持矩阵；应主动拒绝语义不可靠的NFS/flock配置。未测不能称portable。
- SBOM、pinned container digest、service restart/upgrade兼容性测试。未做不能称deployment-ready。

## 会导致过度表述的边界

- 现有 adapter 复制全环境、从PATH执行CLI、把prompt放argv、默认retry，并在缺失returned model时伪装为requested model；只能称prototype。
- `api_hybrid` 只允许LLM输出convex weights（`schemas.py:1-6`），既不是formal direct LLM，也不是19-action controller。
- 其 hierarchy/debate/dynamic-route 与当前冻结论文core明确删除的架构冲突（`EXPERIMENT_PLAN.md:50, 164-168`），不能纳入confirmatory表。
- same-process Python私有属性不是隔离；同UID的两个进程通常也不是充分隔离。
- SHA ledger没有MAC、签名、WORM或外部时间戳，不能证明恶意writer未整体重写。
- 当前 split只检查两个opaque hash不相等（`contracts.py:232-244`），未机械证明whole-capacitor membership、LOCO或跨工况互斥。
- Ark请求参数可证明“客户端发送了什么”，不能证明服务端绝对没有内部cache/drift；只能结合authenticated snapshot和返回字段限定。
- 用户/系统管理员可直接打开公开raw dataset；隔离证明的是正式运行的访问纪律，不是人员绝对不知标签。
- 没有P1/P2/P3、真实held-out数值、calibration、RUL endpoint和外域结果前，任何“高精度”“可上线”“文章ready”都不成立。
- 即使以上blocking tests通过，也只能先称 `production-candidate harness`；还需获批P3真实synthetic capability probe及独立复审后，才能称 Ark transport qualified。