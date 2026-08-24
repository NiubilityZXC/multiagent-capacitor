# Large Pack Schema Probe

- 审计时间：2026-08-20 14:53:41 Asia/Shanghai
- 数据范围：`ES10.mat`、`ES12.mat`、`ES14.mat`
- 数据格式：MATLAB v7.3 / HDF5
- 方法：只读、metadata-first；读取对象树、shape、dtype、MATLAB 属性、对象引用、小型字符数据和少量预先指定的标量。
- 明确限制：未遍历或统计大型数值 payload，未完成内容级重复检测、全量 NaN/gap 扫描或失效标签核验。

本报告是 schema 探查工件，不表示 Data Gate 已通过。完整 RUL 评测当前仍被结果标签与终止语义阻断。

## 1. Proven：由文件内部结构直接证明

### 1.1 根结构与单元标签

每个文件根组均包含：

- `/{ESx}/Transient_Data`
- `/{ESx}/EIS_Data`
- `/{ESx}/Initial_Date`

EIS 中每个文件均包含 `C1..C8`，因此共有 24 个 EIS 轨迹标签。瞬态数据中：

- ES10：`C1..C7`，无 `C8`；
- ES12：`C1..C8`；
- ES14：`C1..C8`。

因此共有 23 个瞬态轨迹标签，且 `ES10C8` 是 EIS-only 标签。这里证明的是数据标签和路径数量，不是 24 个独立物理器件。

### 1.2 瞬态数组与时间长度

| 文件 | `Serial_Date` shape | 电容槽位 | 每个 `VL` / `VO` shape | 结论 |
|---|---:|---:|---:|---|
| ES10 | `(75826, 1)` | C1–C7 | `(75826, 400)` | 时间与 7 个通道长度一致；C8 缺失 |
| ES12 | `(77241, 1)` | C1–C8 | `(77237, 400)` | 时间比所有通道多 4 行，off-by-4 |
| ES14 | `(77241, 1)` | C1–C8 | `(77241, 400)` | 时间与 8 个通道长度一致 |

ES12 的 4 行差异必须触发显式 quarantine/error；在确定额外时间位于头部还是尾部以及对齐语义前，不得用 `min(length)` 静默截断。

### 1.3 EIS 引用层级

每个 EIS 电容标签的路径为：

```text
/{ESx}/EIS_Data/{ESxCk}/EIS_Measurement/
    Header       shape=(73, 1), reference array
    Data         shape=(73, 1), reference array
    ColumNames   shape=(73, 1), reference array
```

对事件 `e`：

```text
Header[e,0]     -> replicate cell -> header char matrix
Data[e,0]       -> replicate cell -> numeric EIS matrix
ColumNames[e,0] -> uint16 char matrix, shape=(12,20)
```

全部 `3 × 8 × 73 = 1752` 个 capacitor-event 中，Header 与 Data 指向的内层 cell shape 完全一致。因此同一 replicate index 的 Header/Data 可以结构性配对，但配对后仍需按 header 时间排序。

### 1.4 EIS 事件数、重复数与对象复用

每个电容标签有 73 个 EIS 事件，每个事件至少有一个非空数值矩阵。非空 replicate 数分布为：

| 文件 | `{每事件 replicate 数: 事件数}` | 非空数值矩阵总数 |
|---|---|---:|
| ES10 | `{4:1, 5:566, 6:10, 7:3, 10:2, 20:1, 26:1}` | 2981 |
| ES12 | `{4:2, 5:580, 6:1, 7:1}` | 2921 |
| ES14 | `{3:1, 5:575, 6:7, 13:1}` | 2933 |
| 合计 | 1752 个事件 | **8835** |

重复测量数不固定，解析器必须保留 `condition -> capacitor -> event -> replicate` 层级，不能在审计前先验平均。

文件内按 HDF5 target path 检查非空 Data 引用，2981、2921、2933 个数值对象均未被多个槽位指向。这只排除同一文件内的引用级复用；不排除数值内容重复或跨文件重复。

### 1.5 EIS 数值矩阵和列 token

对每个事件的首个非空矩阵进行 metadata 检查：除 ES10C5 的一个矩阵为 `(18,58)` 外，其余为 `(18,59)`；未扫描其他 replicate 的完整 shape 分布。

`ColumNames` 中可解码出 20 个原始 token：

```text
freq/Hz
Re(Z)/Ohm
-Im(Z)/Ohm
|Z|/Ohm
Phase(Z)/deg
time/s
<Ewe>/V
<I>/mA
Cs/µF
Cp/µF
cycle
number
I
Range
|Ewe|/V
|I|/A
Re(Y)/Ohm-1
Im(Y)/Ohm-1
|Y|/Ohm-1
Phase(Y)/deg
```

文件中明确存在 `Cs/µF`、`Cp/µF` 与 `Re(Z)/Ohm`，但不存在命名为 ESR 的直接字段。

### 1.6 时间与排序

`/{ESx}/EIS_Data/EIS_Reference_Table` 的 h5py shape 为 `(4,73)`。三个文件的该小型表逐 token 完全相同：日期覆盖 2014-09-29 至 2015-05-13；第四行从 `0, 0, 2, 23, ...` 到 `5105.5`。前三行可观察为 date/start/end token，第四行没有显式字段名或单位。

`Initial_Date` 在三个文件中均为 `10/01/2014 10:00:00 AM`。

事件内引用顺序不是时间顺序。例：

```text
/ES10/EIS_Data/ES10C1/EIS_Measurement/Header[0,0]
```

其 cell 先列出 Test 10–15（11:21–11:26），随后才列出 Test 1–9（11:09–11:21）。因此必须先保持 Header/Data replicate 成对，再按 header 中的 `Acquisition started on` 排序。原始 cell index 或文件名字典序不能作为在线时间顺序。

### 1.7 命名 schema 中缺少结果标签

对三个文件的对象 path 与 `MATLAB_fields` 做 metadata 搜索：除 Initial/Serial date 外，未发现命名的 failure、termination、status、SOH、RUL、capacity 或 ESR 字段。该结论仅针对命名 schema；未穷举所有 header comment 字符串。

文件只提供观测结束位置，没有显式证明最后一次观测是失效。因此不能把序列末端当作 EOL，也不能据此生成普通点值 RUL 标签。

## 2. Inferred：有内部证据，但不是显式元数据

### 2.1 ES10 / ES12 / ES14 是名义电压工况

没有仅凭路径 token 下结论。额外读取每个可用瞬态通道的单个标量 `VO[0,100]`：

| 文件 | 通道数 | 标量范围 |
|---|---:|---:|
| ES10 | 7 | 9.983981–9.986950 |
| ES12 | 8 | 12.009285–12.014182 |
| ES14 | 8 | 13.993496–14.000000 |

这些数值跨通道一致，并与 header 目录中的 ES10/12/14 标签相符，强支持 `condition_nominal_vo = 10/12/14`。但 `VO` 无显式单位属性且这里只做稀疏标量核验，证据等级为 high-confidence inferred，而不是 explicit-metadata proven。

### 2.2 18 列 EIS 映射

典型数值矩阵第一维为 18，而列名有 20 个 token。高置信解析是：

- 合并 `cycle` + `number` 为 `cycle number`；
- 合并 `I` + `Range` 为 `I Range`。

这样得到 18 个语义列，与数值矩阵维度一致。该规则必须作为冻结 schema test，通过数值/协议 sanity check 后才能提升为 proven parser behavior。

### 2.3 h5py 方向与时间解释

- EIS `(18,59)` 很可能是 MATLAB 原始 `(59,18)` 的 HDF5 维度反转，解析后宜转为 `[frequency_row, feature_col]`。
- 瞬态 `(n,400)` 可在 h5py 中按 `[event, waveform_sample]` 使用。
- `Serial_Date` 的数值按 MATLAB datenum 解释，可得到约 2014-11-17 至 2015-05-12/13；首、中、末三个相邻位置的稀疏检查均约为 120 秒间隔。未全量证明所有位置规则或无 gap。
- Reference Table 第四行的量级看似累计应力时间，但字段名和单位未知，不能直接命名为 `elapsed_hours`。

### 2.4 物理电容身份

每个条件的 header 路径分别出现 `Cap #1..#8`，支持每个 `(condition, Ck)` 是一条电容轨迹。但没有器件序列号、替换记录或跨条件映射，故“24 个不同物理电容”以及 `C1` 跨条件的关系都只能保持未证实。

## 3. Unknown：本次探查无法确定

- `VL`、`VO` 的完整物理定义、单位、传感器校准与电路拓扑；
- 24 个标签对应的独立物理器件数，是否存在替换、复用或跨工况同一器件；
- board、batch、材料型号、温度、制造批次和工况顺序；
- Reference Table 第四列的正式名称和单位；
- 全量 `Serial_Date` gap、重复 timestamp、NaN/padding 分布；
- ES12 多出的 4 个 timestamp 应从头部还是尾部隔离；
- EIS 所有 replicate 的完整矩阵 shape、频率网格一致性和数值质量；
- 文件间或数值内容级重复；
- 单个 event 的 Cs/Cp 如何归约为容量 target；
- ESR 的正式测量/拟合定义；
- SOH 基准、失效阈值、终止原因、失效事件、右删失和区间删失标签；
- 观测结束是否源于失效、试验计划结束、采集故障或其他原因。

## 4. Data Gate 初判

| Gate | 状态 | 原因 |
|---|---|---|
| 文件可读与根 schema | AMBER | HDF5 可读且层级清晰，但尚未做完整 payload 质量扫描 |
| 单元身份 | AMBER | 有 24 个标签，无物理序列号/替换记录 |
| 时间与因果成熟度 | AMBER | 有 header 时间；顺序需重排，ES12 off-by-4，elapsed 单位未知 |
| EIS C/Cp/Cs 轨迹 | AMBER / conditional | 字段存在，但频点、拟合和重复归约规则未冻结 |
| ESR target | RED / blocked until defined | 无直接 ESR 字段，派生规则未冻结 |
| SOH/RUL/outcome | **RED / blocked** | 无失效、终止、SOH、RUL 或删失标签 |
| 跨工况 | AMBER | 名义 10/12/14 V 有高置信内部证据，但身份/批次混杂未知 |
| 重复与缺失 | AMBER | 引用级无复用；内容级重复未知，且存在缺失模态与长度异常 |

因此不得声称 Data Gate 已通过。当前最多可在明确标注条件限制的情况下开发 EIS 轨迹解析和预测最小基线；RUL 数值评测继续阻断。

## 5. Parser contract

```python
condition_label = stem                       # raw: ES10 / ES12 / ES14
condition_nominal_vo = evidence_map[stem]    # inferred, evidence retained
unit_label = f"{stem}C{k}"                  # provisional trajectory label

transient_event = {
    "serial_date": Serial_Date[i],
    "VL": VL[i, :],
    "VO": VO[i, :],
}

schedule_tokens = EIS_Reference_Table[:, event_index]

header_cell = Header[event_index, 0]
data_cell = Data[event_index, 0]
assert header_cell.shape == data_cell.shape

replicate = pair(header_cell[r], data_cell[r])
replicate.acquisition_time = parse_header(
    "Acquisition started on : ..."
)

# Pair first, then sort paired replicates by acquisition_time.
eis_matrix = numeric_reference.T
columns = merge_tokens(
    raw_20_tokens,
    merges=[("cycle", "number"), ("I", "Range")],
)
assert eis_matrix.shape[1] == len(columns) == 18
```

强制策略：

1. ES12 长度异常必须进入 quarantine ledger，禁止静默修复。
2. ES10C8 必须标记 `transient_missing=True`；多模态模型需显式 mask。
3. 原始 header 含 ES10/12/14、Cap 编号、目录和文件名；只允许白名单提取时间和测量协议，禁止把原始字符串、HDF5 `#refs#` 名或 unit label 输入模型。
4. LOCO 暂以 `(condition_label, Ck)` 为 provisional group，并在结果中披露 physical-ID uncertainty。
5. 跨工况测试必须整条件 holdout。
6. 频点选择、EIS 拟合超参、replicate 聚合和异常剔除阈值只能在训练电容上确定。
7. RUL 路径在 failure/censor label 可证且协议冻结前保持 blocked。

## 6. 主要证据路径

```text
/{ESx}/Initial_Date
/{ESx}/Transient_Data/Serial_Date
/{ESx}/Transient_Data/{ESxCk}/VL
/{ESx}/Transient_Data/{ESxCk}/VO
/{ESx}/EIS_Data/EIS_Reference_Table
/{ESx}/EIS_Data/{ESxCk}/EIS_Measurement/Header
/{ESx}/EIS_Data/{ESxCk}/EIS_Measurement/Data
/{ESx}/EIS_Data/{ESxCk}/EIS_Measurement/ColumNames
```
