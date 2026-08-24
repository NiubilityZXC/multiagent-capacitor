# 公开电容退化证据账本

**冻结版本**：2026-07-29  
**用途**：为多智能体在线电容剩余寿命预测研究提供可复核的数据、论文、代码与定义依据。  
**证据原则**：官方数据页/原始文件/论文正文优先；第三方镜像和代码仓库只能补充，不能覆盖原始语义。任何尚未完整下载或未在原始文件中核对的字段均标记为“待核验”。

## 1. 数据集核验

| 数据资源 | 可获得内容 | 已核验事实 | 可用于什么 | 关键限制 | 结论 |
|---|---|---|---|---|---|
| [NASA: Towards Prognostics of Electrolytic Capacitors](https://data.nasa.gov/dataset/towards-prognostics-of-electrolytic-capacitors) | 论文 PDF | 数据页资源实际只有 `2011_AIAATowardsCapacitors.pdf`，没有原始退化数据 | 文献、定义和实验背景 | 不能当作可下载数据集 | 论文资源，不计作数据集 |
| [NASA: Capacitor Electrical Stress-2](https://data.nasa.gov/dataset/capacitor-electrical-stress-2) | `EOS_DataSet.zip` → `EOS_DataSet.mat` | ZIP 1,648 B，SHA-256 `944cd2284cd01925088e97e5f5e2f337ee8b37800346fd2610d1bbaa6accacfb`；MAT 1,090 B，SHA-256 `9db651a10f92d2046a477838c08fe1cdbaf27d7bc4062a856a373721400cb4a3`；`aging_time` 为 11×1，取值 0,24,47,71,94,116,139,149,161,171,194；`C`、`ESR` 均为 11×6 | 六只 10 V 电容的稀疏 LOCO、小样本统计/滤波基线、泄漏哨兵 | 总计仅 66 个“器件×时点”观测；单工况；`C` 是相对电容量损失百分比，`ESR` 是相对增幅百分比，不是 µF/Ω 原值 | 可复现但极小；不能支撑大模型微调或跨工况结论 |
| [PHM Society NASA mirror: Capacitor Electrical Stress](https://data.phmsociety.org/nasa/) | 10/12/14 V 原始 ZIP | 远程 HEAD：5,038,942,729 B；ZIP 中只有 `ES10.mat`、`ES12.mat`、`ES14.mat` 和一个目录项；三文件均为 MATLAB 7.3/HDF5。中央目录给出的未压缩大小分别为 1,209,388,987、1,863,271,598、2,094,950,842 B | 多工况原始 EIS、充放电瞬态、跨器件/跨电压测试 | 包内没有 README；尚未完成 5.04 GB 全量下载和 HDF5 对象树审计，具体器件数、事件映射、终止原因不得只凭第三方代码断言 | 主基准候选；在完整审计前不能冻结最终样本数 |
| [Kaggle: Capacitor Aging Analysis Under Electrical Stress](https://www.kaggle.com/datasets/sellerans/capacitor-aging-analysis-under-electrical-stress) | 5.1 MB ZIP | 内容是同一个 1,090 B `EOS_DataSet.mat`、绘图脚本和图片；脚本把 `C(:,1)` 错当 `aging_time`，又把相对损失标成 µF | 只能作为复现陷阱案例 | 不是独立数据；语义解析错误 | 排除出独立基准，纳入数据审计故障注入 |
| [Wang et al. 2015 DC film capacitor humidity study](https://doi.org/10.1016/j.microrel.2015.06.011) | 论文中的 30 只薄膜电容退化/失效曲线 | 1100 V、40 µF；85 °C 下 85/70/55% RH 分组；总试验约 8,700 h；论文报告 C/ESR | 跨器件类型的外部文献比较 | 未找到公开原始逐点数据下载 | 原始数据未核验，不进入冻结数值基准 |
| [Gao et al. 2025 film-capacitor adaptive RUL](https://doi.org/10.1109/TPEL.2025.3621772) | 论文、预印本和在线工具入口 | 混合效应退化模型 + 比例风险 + Bayesian 在线更新；论文使用湿热薄膜电容数据 | 退化—生存联合模型最近邻 | 未找到可公开下载的原始逐点数据；在线工具在核验时重定向到认证 | 作为强基线/最近邻，不作公开数据集 |

### 1.1 大包在全量下载前必须完成的硬审计

1. 记录原始 ZIP 与三个 MAT 文件的 SHA-256、HTTP 元数据和下载时间。
2. 导出 HDF5 完整对象树、字段类型、维度、压缩、对象引用和器件映射。
3. 逐器件重建 EIS 与瞬态事件：真实时间/aging time、工况电压、采集模式、波形长度、频率轴。
4. 核对同名器件是否在 Stress-2 小表与大包中重复；在身份未证明前禁止同时出现在训练和 Eval。
5. 对每个实验终止点记录“阈值失效 / 实验停止 / 文件截断 / 原因未知”。未知不能被改写为精确 EOL。

### 1.2 Stress-2 阈值事件可识别性

直接读取 `EOS_DataSet.mat` 后，按相对电容量损失达到 20% 统计：

| 电容 | 首次观测越界时间 | 上一观测 | 终点电容量损失 | 标签性质 |
|---|---:|---:|---:|---|
| C1 | 未越界 | — | 17.45% @ 194 h | 右删失 |
| C2 | 194 h（21.68%） | 19.642% @ 171 h | 21.68% | 区间删失 (171,194] h |
| C3 | 194 h（21.045%） | 19.054% @ 171 h | 21.045% | 区间删失 (171,194] h |
| C4 | 171 h（20.04%） | 14.75% @ 161 h | 22.675% | 区间删失 (161,171] h |
| C5 | 194 h（20.797%） | 18.23% @ 171 h | 20.797% | 区间删失 (171,194] h |
| C6 | 194 h（22.04%） | 17.23% @ 171 h | 22.04% | 区间删失 (171,194] h |

ESR 的最大相对增幅为 53.54%；没有一只达到 \(R/R_0=2\)，即相对增幅 100% 的阈值。由此可知：

- 小表只有 5 个区间删失的 C-EOL 事件，且 4 个只在最后一个观测点被发现。
- 它不足以单独支撑稳定的精确点 RUL 回归或 ESR-EOL 学习。
- 主分析应采用 interval/right-censored likelihood；把首次越界观测时间当精确 EOL 只能作为敏感性分析。

## 2. 原始实验与定义证据

### 2.1 NASA 2011/2012 电气过应力研究

- [Celaya et al., Towards Prognostics of Electrolytic Capacitors](https://c3.ndc.nasa.gov/dashlink/static/media/publication/2011_AIAATowardsCapacitors.pdf)：六只 2,200 µF、10 V 电容；跟踪电容量损失与 ESR；经验退化模型结合 Kalman filter；EOL 采用电容量下降 20%；RUL 为预测 EOL 时间减当前时间。
- [NASA model-based methodology](https://ntrs.nasa.gov/api/citations/20140010627/downloads/20140010627.pdf)：把退化状态更新与未来阈值穿越连接起来；属于模型驱动的早期基线。
- [Accelerated Aging in Electrolytic Capacitors for Prognostics](https://c3.ndc.nasa.gov/dashlink/resources/792/)：明确报告过小样本下采用 leave-one-out 验证，并指出现有模型不能表示末期行为改变和休息后的电容量恢复。

这些工作意味着：

- LOCO/leave-one-unit-out 不是本项目的新颖点，而是必须复现的最低基线。
- 20% 电容量损失是该 NASA 任务的论文阈值，不应无条件外推到所有电容类型。
- 加速时间不能自动映射为真实服役时间；只能报告在该加速协议内的小时/事件 RUL，除非另有物理加速映射证据。

### 2.2 三电压 EIS/瞬态研究

[Renwick, Kulkarni, Celaya, 2015](https://www.papers.phmsociety.org/index.php/phmconf/article/view/2713) 的正文支持以下事实：

- 试验覆盖 10/12/14 V；论文重点分析 10 V 板。
- 10 V 板为一批七只 2,200 µF 电容；约每 10 分钟采集一组十次充放电波形。
- 离线 EIS 需要移除器件；C 和 ESR 由系统辨识得到。
- 在线瞬态时间常数与离线 EIS 时间常数趋势相近但量级不同；温度、硬件、校准和电路状态都会造成偏差。
- 在线瞬态在约 1,100 h 后才开始，早期在线历史缺失。
- 电容量在约 400 h 后可能出现回升；论文提出氧化层/并联电容量变化解释，并警告简单 C+ESR 集总模型在后期可能失效。

因此，“C 永远单调下降、ESR 永远单调上升”只能作为候选先验和消融，不能作为无条件硬约束。

## 3. 相关方法与最近邻

| 方法族 | 代表工作 | 与拟议系统的关系 | 不可冒充的新意 |
|---|---|---|---|
| 经验退化 + KF | [Celaya et al.](https://ntrs.nasa.gov/api/citations/20140010627/downloads/20140010627.pdf) | NASA 电容 RUL 经典基线 | 状态空间和在线更新 |
| UKF/PF/PSO | [Qin et al. 2018](https://doi.org/10.1016/j.microrel.2018.05.020) | Verhulst+指数、UKF proposal、PF、PSO resampling | “更复杂 PF 用于电容” |
| 两阶段 Wiener + 自适应模型选择 | [Chen, Miao, Yin 2024](https://doi.org/10.1016/j.microrel.2024.115509) | NASA 六电容；三种退化模型；历史 RUL 相似度在线选最优模型 | 电容 RUL 的两阶段建模和动态模型选择 |
| Wiener + 相似性 + LSTM 残差 | [Zhao et al. 2023](https://doi.org/10.1016/j.microrel.2023.114928) | 长期退化模型与学习型残差的直接近邻 | “长期统计模型 + 短期学习残差”本身 |
| 退化 + 生存 + Bayesian 更新 | [Gao et al. 2025](https://doi.org/10.1109/TPEL.2025.3621772) | 薄膜电容；混合效应、比例风险、在线个体化 | 电容的联合退化—生存框架 |
| 同时估计 C/ESR | [Ou et al. 2024](https://arxiv.org/abs/2404.13399) | MMC 波形 + PSO 同时估计 C/ESR；指出单指标会漏掉更早 EOL | “同时监测 C 和 ESR” |
| 多应力 LSTM 预测 C/ESR | [Liu et al.](https://doi.org/10.1109/TIM.2021.3076837) | 由早期老化与应力预测未来 C/ESR | “LSTM 多任务预测” |
| 多步在线共形 | [Wang & Hyndman 2024](https://arxiv.org/abs/2410.13115) | AcMCP 处理多步预测误差自相关 | 在线多步共形校准 |
| RUL 共形区间 | [Javanmardi & Hüllermeier 2023](https://doi.org/10.36001/ijphm.2023.v14i2.3417) | 将点 RUL 预测器共形化 | 给 RUL 加 conformal interval |
| TS foundation models | [Chronos](https://arxiv.org/abs/2403.07815)、[TimesFM](https://arxiv.org/abs/2310.10688)、[Moirai](https://arxiv.org/abs/2402.02592) | 可作为冻结零样本/少量适配专家 | 把基础模型用于一个小领域并不自动构成创新 |
| RUL 评测指标 | [NASA prognostic metrics](https://ntrs.nasa.gov/citations/20100023445) | Prognostic Horizon、α–λ、RA/CRA；可含不确定性 | PH/α–λ 指标 |
| Agent ML 工程 | [MLE-bench](https://arxiv.org/abs/2410.07095)、[MLE-STAR](https://arxiv.org/abs/2506.15692) | 说明代码搜索/定向改进必须靠可执行 Eval 衡量 | LLM 自主 ML 工程 |
| 多 Agent 架构比较 | [Automated Research MAS study](https://arxiv.org/abs/2603.29632)、[agent scaling study](https://research.google/blog/towards-a-science-of-scaling-agent-systems-when-and-why-agent-systems-work/) | 单 Agent、并行子 Agent、团队/动态拓扑已有一般比较 | “多 Agent 比单 Agent”作为先验结论 |

## 4. 开源代码核验

### 4.1 `kino-6/capacitor-rul-prediction`

- 仓库：[GitHub](https://github.com/kino-6/capacitor-rul-prediction)
- 审计提交：`35461698cfdbf8a61eda119a05fd6e0da12382b8`，提交时间 2026-02-10。
- 顶层 README 为空，`main.py` 只打印问候语；主要内容位于 `eda_kiro/rul_modeling/`。
- 仓库文本声称 MIT，但审计提交中没有 LICENSE/COPYING 文件；复用前必须按“无明确代码许可证”处理。
- 其标签生成器明确实现：
  - `is_abnormal = cycle > 100`
  - `rul = 200 - cycle`
- 已提交特征 CSV 含八只 ES12 电容，每只恰好 200 行，RUL 从 199 线性倒数至 0。
- 数据切分固定为 C1–C5 训练、C6 验证、C7–C8 测试，不是全 LOCO，也不是滚动原点 Eval。
- 报告宣称 v2 在 C7/C8 上 RUL MAE 1.95 cycles、R² 0.9753、异常 F1 0.9975；这些数字衡量的是“恢复固定周期倒计时/后半程标签”，不是由 C 或 ESR 首次越过物理阈值得到的真实 RUL。

**裁决**：可借鉴解析和波形特征代码，但其 RUL/异常结果不得进入可信 SOTA 对比；先要替换标签、切分和回放协议。

### 4.2 官方时序模型代码

- [Amazon Chronos](https://github.com/amazon-science/chronos-forecasting)：Apache-2.0；支持概率/分位数多步预测。
- [Google TimesFM](https://github.com/google-research/timesfm)：Apache-2.0；当前仓库提供连续分位数头和长上下文版本。
- [Salesforce Uni2TS/Moirai](https://github.com/SalesforceAIResearch/uni2ts)：Apache-2.0；示例包含 rolling evaluation。
- [Lag-Llama](https://github.com/time-series-foundation-models/lag-llama)：概率时序基础模型。

这些模型只进入统一专家池；绝不因“参数更多”获得优先权。

## 5. 冻结术语

### 5.1 电容量、ESR 与 SOH

- 本项目中文“容量”一律指 **电容量** \(C\)，单位通常为 µF；不是电池的 Ah 容量。
- ESR 是给定测量频率、温度、仪器和电路状态下的等效串联电阻。任何 ESR 数值必须携带这些测量条件或明确标记未知。
- 若有原值：
  \[
  SOH_C(t)=C(t)/C_0,\qquad SOH_R(t)=R_0/R(t).
  \]
- 为表达“距阈值余量”，另报告：
  \[
  m_C(t)=\frac{C(t)/C_0-\rho_C}{1-\rho_C},\qquad
  m_R(t)=\frac{\rho_R-R(t)/R_0}{\rho_R-1}.
  \]
  其中 \(\rho_C,\rho_R\) 由数据集协议冻结。复合 SOH 可取
  \(\operatorname{clip}(\min(m_C,m_R),0,1)\)，但必须同时保留两个分量，不能只报复合值。
- Stress-2 小表已经给出相对百分比变化；不得再次把第一列当基准或标成 µF/Ω。

### 5.2 EOL 与 RUL

- 对 NASA 电气过应力主任务，主定义为 \(C(t)\le0.8C_0\)；敏感性定义加入 \(R(t)\ge2R_0\) 和二者任一触发。
- 薄膜电容论文中使用的 95% 电容量阈值只属于相应薄膜数据，不能与电解电容阈值混用。
- 阈值只在离散测量点观察到时，真实 EOL 位于上一个未越界点与第一个越界点之间，是**区间删失**。
- 实验结束仍未越界是**右删失**，不是 `RUL=0`。
- 对可识别事件：
  \[
  RUL(t)=T_{\text{first valid EOL}}-t.
  \]
  同时报告小时和事件/循环数；不能用 `max_cycle-current_cycle` 代替。

## 6. 当前证据边界

1. 已完成 Stress-2 小文件的字节级下载、哈希和数组级核验。
2. 已完成三电压大 ZIP 的远程大小、中央目录和文件格式核验，但尚未全量下载；任何详细 schema 仍是待核验。
3. 没有找到一个同时具备“大样本、真实运行工况、公开逐点 C/ESR、明确终止原因”的电解电容公开基准。
4. 三电压数据来自加速电气应力；跨电压测试衡量应力迁移，不等同于跨真实应用工况。
5. 公开样本量极小，深度模型/基础模型出现高方差和记忆型拟合是主要风险；简单统计模型必须始终保留。
6. 当前没有可信公开 leaderboard 或统一电容 RUL 评测协议；本项目的主要可发表贡献之一可能是严格、可执行的协议和负结果，而非必然的新模型胜出。
