# Benchmark-L P1 Data Gate 合同 Amendment v1.1

**冻结时间**：2026-08-24 11:37:52 +0800  
**父合同**：`BENCHMARK_L_DATA_GATE_PROTOCOL_20260824_113327.md`，SHA-256 `ceec8f1d64d48958ffe5ec1172fc33fa2734b9920f925f33ce23dc8d6ec23b03`。  
**触发证据**：实现前的只读 raw-matrix 探针发现 canonical matrix 的频率列包含 acquisition preamble；尚未运行 P1 parser/Data Gate，也未运行模型或 RUL。

本 amendment 仅替换父合同 G02 的“全部 raw rows frequency positive”表述，其他规则不变：

1. 9,316 个 raw Header/Data cell slots 必须对账为 8,835 个非空 matrix pairs + 481 个 paired canonical empties。
2. canonical matrix 保留全部 58/59 个 raw rows，不删除、不插值、不重排。
3. 每行增加 `row_class`：
   - `acquisition_preamble`：`freq == 0`；
   - `positive_frequency_sweep`：`freq > 0`；
   - `invalid_frequency`：negative 或 nonfinite，G02=`FAIL`。
4. `positive_frequency_sweep` 必须是单一连续后缀，恰好 51 行，frequency finite、positive、strictly decreasing。
5. `acquisition_preamble` 必须是单一连续前缀；已冻结允许的长度集合为 `{7,8}`。除 frequency 为 0 外，其余 17 列仍纳入完整数值、hash 与 missingness 审计。
6. `n_frequency` 专指 positive sweep 行数；`n_raw_rows` 始终另行保留。任何 target proxy 仍为 `BLOCKED`，不得依据 preamble/sweep 观察事后选择频点。

该修订使 frequency gate 与实际文件结构一致，同时保留 raw data 的逐行可追溯性。
