# Ren 测量重叠与目标语义审计设计

2026-09-14。ARIS experiment-bridge 实现增量，不是运行放行。原 P1-R1 范围；旧 seals、reader、chronology 代码不改。

## 本轮已实现的纯内核

ren_overlap.py 不含真实数据读取、索引落盘、模型或自动 Gate。输入为验证后的五字段 key 与解码行，公共测量投影固定为 status、局部时间整数微秒、voltage(V)、current(mA)、capacity(mAh)。排除 cycle/step/record_number 以免重编号掩盖复制；两种表布局共有字段一致比较，energy 不参与候选筛选。负零归一，无舍入、容差或插值。

每连续 8 条投影构成 shingle，在连续 25 个 shingle 中选择最右最小指纹；因此完全相同且连续的 32 条投影片段必有共同筛选指纹，包括位置错位和原 sheet/文件边界。调用方必须为一个候选组提供连续迭代器，不得每表重置。短于 32 条、近似复制、变换时间/状态后的复制不在该保证内；32 是筛选分辨率，不是数据独立性的科学阈值。

指纹只是检索候选，不能当匹配结论。确认必须返回原始位置并逐值比较公共投影；若两端都有 energy，还需单独检查该字段才能称完整测量行相同。匹配静置片段也不能自动判为同一设备。若需要证明更短/近似重叠，应另行定义检验，不得声称当前覆盖。

内核使用 O(8+25) 有界状态，synthetic reference 可全量列表，仅用于小测试，不用于实际 fleet。确定性测试覆盖 300 个随机序列的独立 oracle、40 种平移的 32 行复制、重复值最右择优、跨 chunk 连续、短序列、数值校验、精确确认。纯内核通过不等于完整 caller 可执行。

实测仅为合成内核：100,000 条产生 7,667 个筛选指纹，tracemalloc 下约 1.14 秒、Python 跟踪峰值 7,454 bytes；不包含 XLS、磁盘索引、逐值回读或本机进程 RSS。全相同 shingle 在最右择优规则下可能每次滑动都产生新位置，最坏索引规模仍是 O(记录数)，不能用本组合成比例预估实际索引空间或宣称每 25 条只留 1 条。

## 下一集成必须完成

1. Workbook-only adapter 与固定 schema/chronology 回执覆盖核对，numeric cell 类型校验、逐组连续流、原始位置映射；不得仅凭值可转 float 接受 text cell。
2. ignored 磁盘索引保存指纹、组、位置；流式导出跨组候选，不将全库候选积入内存；完全恒定片段等高频匹配不得静默截断后宣称无重复。
3. 对候选定位回读与逐值确认，确认长度至少覆盖 32 条；两边有 energy 时记录 energy 是否一致。保留同组重复与跨组重复的不同解释。
4. 同一读取流程采集 step/cycle/record 的状态和端点对照、记录电流符号/变化、端点电压/时间一致性计数。只审计，不输出 F、SOH 或 RUL 数值目标。
5. 独立字段重建、持久化对账、故障后保留证据、完整合成 end-to-end 对抗测试，fresh pre-run review 后另建运行 release。当前没有这些 caller 工件，因此不读取真实测量值。

## 作者目标代码的关键语义

固定 preprocess.py 的构造函数调用 set_life(rated=True, set=True, ratio=0.903)。在 rated=True 分支，end_capacitance=ratio，直接与 discharge_capacitance(F) 比较；因此代码实际使用 0.903 F 数值阈值，不是自动乘初始电容的 90.3% SOH。且取低于阈值样本的第二个条目，异常时以 life=0 表示。该实现语义不能直接变成本项目的 EOL 定义，0 也不能当真实失效时刻。

作者 cal_cycle_capacitance 的默认路径使用 -20*t/(end_V-ini_V)/1000，对应固定电流假设；需先验证真实电流与端点，再讨论 eligibility。batch1 额外补零/重建端点、其他分支单位缩放等均不得照搬。仅阅读源码，不执行作者程序。

此轮不解决最终身份、ESR 可用性、终止原因或切分资格；这些须按证据分别裁决。没有模型/API 调用或预测实验。

## 本轮验证与审查

新增 21 项测试通过；隔离审计合跑 143 passed in 2.80s，无跳过；一般全项目回归 631 passed, 35 skipped in 39.85s，所需 xlrd 路径在隔离套件实际执行。fresh GPT-5.6-Sol xhigh 复审 PASS，无阻断，并以 5,000 组额外随机错位/重复片段合成案例验证共同指纹性质。此为 same-family provisional pure-kernel review，不是实际运行放行。

完整响应 ignored data/raw/ren_scs/overlap_kernel_review_response_20260914.md，SHA-256 900db2d504c6fa1f4a8f668355ff2e9cc701aae639debc95a2ce9c0d905ba153；完整请求/响应 ARIS trace 已保存。未创建真实测量审计 release。
