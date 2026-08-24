# TRACE-Cap 零上下文对抗审查

**日期**：2026-07-29  
**review independence**：same-family  
**acceptance status**：provisional  
**裁决**：`PROCEED_WITH_MAJOR_REDESIGN`

## 拒稿摘要

计划把尚未完成 schema、器件身份和终止原因审计、独立器件极少的加速过压数据，扩张为测量桥、切换状态、动态专家、共形校准与多 Agent 全栈。主 RUL 可能因区间/右删失而不可识别，三电压也只支持应力电压迁移；RUL 校准的标签时钟原先没有闭合，核心机制又都有强近邻。

在完成数据审计、缩成单一机制并锁定可识别 estimand 之前，研究最多支持严谨基准、测量研究或可信负结果，不能支持通用在线 PHM 系统。

## 关键发现与决定性修复

| ID | 严重度 | 发现 | 最小修复/决定性测试 |
|---|---|---|---|
| F01 | CRITICAL | Benchmark L 的独立器件、模态配对、事件和终止结局未知 | 从 raw MAT 独立重建逐器件审计清单；映射不稳定则停止 C1/C3/RUL |
| F02 | CRITICAL | 有效样本量按电容计；6 个单位不能支撑全栈 | 按真实结构做零效应/最小效应设计仿真；无法区分则不作优越性排序 |
| F03 | CRITICAL | 物理 EOL、点 RUL 和生存分布可能不可识别 | 冻结结局表、C0/R0、持续越界规则；做区间端点与删失机制敏感性 |
| F04 | CRITICAL | RUL 标签到 EOL/删失才成熟，原在线校准时钟未闭合 | C/ESR、风险、RUL 分账；LOCO 测试期 RUL 校准器固定；做时间戳不变量测试 |
| F05 | MAJOR | LOVO 只检验加速应力电压迁移 | 全文改称 leave-one accelerated-stress voltage transfer |
| F06 | MAJOR | “因果桥”目前只是观测映射，且瞬态晚启动 | 改称 measurement-error mapping；加入时间趋势、置换、板卡/仪器负控 |
| F07 | MAJOR | C1 组件太多，收益无法归因 | 一个固定骨干、一个主机制、锁定 add-one/remove-one |
| F08 | MAJOR | 六候选均有强近邻 | 逐机制 novelty table；唯一机制无稳定增量则删除方法创新主张 |
| F09 | MAJOR | Agent 不直接预测，拓扑到精度的因果链不清 | 拆成随机化 meta-eval；主要结局为阻断、修复、误拒、恢复和成本 |
| F10 | MAJOR | Pareto+词典序仍有分析者自由度 | Freeze B 固定唯一 endpoint/comparison/bounds/tie rule；锁定程序可输出无冠军 |
| F11 | MAJOR | 解封后修改没有新的独立最终集 | 首次解封前封存容器，由隔离执行者一次运行；后续仅探索性 |
| F12 | MAJOR | 数据/代码复用许可尚未闭合 | 记录来源条款；对无许可证代码 clean-room；独立全新环境重建 |

## 最小可发表包

1. 完成 Benchmark L 的字节、HDF5、器件、板卡/批次、模态、时间和终止原因审计。
2. 发布逐器件事件/删失清单、重复身份裁决和可复建标签脚本。
3. 用实际结构做设计与可识别性仿真，不通过时自动降级。
4. 主要问题只保留一个：简约领域观测机制能否改善留出器件的 C/ESR 概率预测；RUL 只在结局门通过时作为次要结果。
5. 模型集限制为 last-value/drift、一个统计/KF、GPR/传统 ML、最强直接近邻和一个唯一新机制。
6. 一次性冻结 LOCO；LOVO 只称应力电压迁移；固定一个 endpoint、一个主要对比和一个分析脚本。
7. 发布哈希、下载/解析器、字段字典、标签构建器、时间回放测试、环境锁、许可证清单和 clean-room 最小复现。

## 审查后候选排序

该排序来自同一位 reviewer，只是证据先验，不是额外独立投票或性能预测：

1. **C2 Censored-Joint**：正确标签/删失的必要强基线；事件不足时停用。
2. **C3 EC-Bridge**：唯一较领域特定的条件挑战者；配对与协变量不足即停。
3. **C5 Agent-FE**：可用隐藏故障形成独立 meta-eval；必须避免自建故障与验证器同构。
4. **C4 Reject-TSFM**：低成本后置正/负结果；先证明上下文与数据量足够。
5. **C1 TRACE-Cap**：长期集成路线；当前自由度过多、不能作为首个实验。
6. **C6 Physics-CDE**：数据量与协变量未证明足够，最后评估。

## Agent 架构排序

`single → fixed → hierarchical → executable debate → dynamic`

- 第一实现：`single Agent + deterministic validator`。
- 第一多 Agent 挑战者：fixed typed DAG。
- fixed 在隐藏任务同成本不优于 single，则停止更复杂拓扑。
- hierarchical 只有 fixed 暴露跨故障域恢复问题后进入。
- debate 只允许提交可执行反例，禁止多数票。
- dynamic 必须在按数据集和故障家族完整留出的 meta-test 上超过最佳静态质量—成本前沿，并可靠 OOD 回退。

公平 meta-eval 的实验单位是独立数据审计、代码修复或植入故障任务；所有架构共享基础 LLM、权限、候选库和多档 token/GPU/wall-clock 预算，并由隐藏真值和确定性测试裁决。

## 允许与禁止

- 允许：严格时间戳的离线 prequential replay；禁止：未经真实影子期称部署验证。
- 允许：概率观测映射；禁止：无干预/同步设计时称因果桥。
- 允许：留一加速应力电压迁移；禁止：跨真实工况或真实服役寿命。
- 允许：已审计、可识别范围内的区间/右删失 RUL；禁止：文件末尾等于 RUL=0。
- 允许：隐藏任务下的 Agent 质量—成本结果；禁止：未经随机化 meta-eval 声称多 Agent 提高物理预测精度。
