# Ren 来源与评测口径复核

2026-09-20。ARIS research-lit；只读一手来源检索，不运行模型，不修改正在运行的 R2 或冻结实验计划。

## 检索记录

本地 papers/、literature/ 未找到 PDF。arXiv helper 查询 `all:supercapacitors AND all:Ren` 返回 HTTP 406；网页回退未找到可确认的相应 arXiv 版本。出版方网页贡献证据；不声称阅读了 2020 论文完整正文或附件。按 DOI 去重，两项论文均为期刊论文，不是两套独立数据。

| 论文 | 一手入口 | 本轮核实与用途 |
|---|---|---|
| Ren et al. (2020), Engineering early prediction of supercapacitors’ cycle life using neural networks, Materials Today Energy 18, 100537 | https://www.sciencedirect.com/science/article/pii/S2468606920301568 ; DOI 10.1016/j.mtener.2020.100537 | 可见 Data generation 段报告测试 113 个 Eaton HV 1 F/2.7 V 碳基器件、1–2.7 V、28°C，并提到从 113 选择 88 个；Methods 摘录为 3:1 train/test。可见摘要报告 ANN 早期寿命预测，不等同本项目滚动 LOCO。 |
| Ren, Cai & Li (2021), High precision implicit function learning for forecasting supercapacitor state of health based on Gaussian process regression, Scientific Reports 11, 12112 | https://www.nature.com/articles/s41598-021-91241-z ; DOI 10.1038/s41598-021-91241-z | Eq.1 使用 C_i/C_R（额定量）；实验段描述 88 个器件，20 mA 放电、两种充电政策，28°C。隐式 GPR 的先验来自 66 个器件，测试 22 个；Data availability 指回同一 Figshare 11522082。 |

2020 出版方明确链接作者 GitHub 与 Figshare，与已归档固定 commit README 指向一致；原始队列包含 113 个设备的声明因此有出版方与作者两类来源支持。但本轮未取得完整设备选择清单，不能据此推出文件到训练/测试子集的一一映射。88 与 113 的差别须保留，不可把文献子集另计为独立测试集。

2021 论文对 5% 前缀实验在摘要给出平均 MAPE 0.6%，结论段写 0.06%；本轮记录其文本不一致，不自行择优或改写成复现实验结果。两种 SOH 分母（额定值与初始观测值）不能互换；本项目最终采用哪个分母仍须在目标审计与协议中明确。

## 对当前研究的具体影响（项目推论，不是来源结论）

1. 来源层面已有正面身份与工况证据，不再额外要求来源未承诺的制造商序列号。最终身份仍须结合已完成组内时序与进行中的跨组重叠证据裁决。
2. 论文中的“88 个”不能直接充当某一工况的文件清单。既有 88 恒流/25 阶梯充电说法须与原始行和批次逐一对应，不能仅按数量匹配；本轮不撤改冻结历史记录，也不声明实际工况已验证。
3. 隐式 GPR 是必须在后续强基线审议中明确讨论的专用模型候选。若采用，其均值与协方差只能从 outer-training 设备形成，禁止用 held-out 设备的未来轨迹建立先验。本记录只是文献候选登记，不将它悄悄加入已冻结的六专家/五融合方案，不启动 P2。
4. 原论文的 3:1 或 66/22 评测不能替代本项目的 whole-unit 外层切分、工况留出和逐时回放，也不能把文献误差直接用于本项目方法胜负比较。
5. 下一次目标审计仍需对照 record 与 step/cycle 的状态、实际电流、时间端点和电压端点；只判可推导性，不执行作者预处理或产生 F/SOH/RUL 标签。ESR 保持 NA，RUL 资格独立处理。

## 范围与未解问题

未取得 2020 选择子集附件、完整原论文训练代码或每器件工况映射。作者仓库的读取/预处理代码不能被称为全部训练流程开源。本轮不是新颖性通过、模型性能通过或 Data Gate PASS。

固定 MANIFEST/tracker 的 apply_patch Update File 当前仍受 bwrap 读取故障影响；本带日期文件保留本轮检索路径、失败来源与结论边界，待环境恢复再补充固定索引。
