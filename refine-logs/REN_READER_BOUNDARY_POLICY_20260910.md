# Ren 首文件只读行审计边界（候选，需独立 pre-run PASS）

范围：承接用户要求尽快解决 Data Gate，使用原 P1-R1 已授权的静态/行级审计范围；不运行模型、API、RUL、整电容切分或 P2。仅试跑按冻结 member_path 字典序选择的首个文件。不得依据预测结果选择文件，不代表全数据集通过。

60 个已出现记录的处理策略：采用已冻结 Microsoft [MS-XLS] 枚举目录，只认可列明的 ID；计算、打印、格式、保护、刷新及 VBA 项目关联记录均为不执行的工作簿元数据，不以名称映射推断数值或目标。读者不启动 Office、不调用计算/刷新、不解码 VBA/对象流。数据单元格、表头、日期类型由固定 xlrd 2.0.2 只读解析；不使用公式缓存或生成新目标。

核心边界：olefile 0.47 仅打开唯一根 Workbook/Book 流；确认它与原静态扫描的流哈希一致，只将这一段原始、未改写字节传给 xlrd 的 file_contents，不把 OLE 容器、VBA、CompObj、对象流或文件路径交给 xlrd。VBA 的存在不被说成无宏；它被隔离在读者输入之外。根 CompObj 与 PLS/CONTINUE 需已有精确上下文证据，其他结构阻断不得忽略。

解析前重新遍历实际流的每个记录头：必须 BIFF8，只允许 globals 和 worksheet 子流，拒绝未知 ID、加密、公式、名称、外部引用、对象等显式禁止的记录。CONTINUE 只允许 PLS → CONTINUE → SETUP。严格检查长度、8224 字节上限、BOF/EOF，禁用 corruption bypass。xlrd on_demand 逐 sheet 读取并卸载；不声称 xlrd 是行级流式解析。

原始数据不转换、不裁剪、不改写、不删除宏。实际只读 schema/rows 是本次动作，不是旧 R1D 结果的回写。输出 cell type/nonfinite/维度统计；首八行的文本提示只在 ignored staging 保留，属于待解释的 schema 提示，不自动认定为列名、物理身份或单位。数值单元格不输出为 target/预测。单个文件即使成功也保持 p2_eligible=false，后续仍需全量行级及身份/时间/单位/目标/重复/切分证据。

依据：固定本地 xlrd 2.0.2 的 book.py biff2_8_load 支持非 OLE 的 Workbook 原始字节；官方文档说明忽略 VBA/宏但会读取公式缓存，因此增加显式公式拒绝边界。既有恢复、环境、静态 manifests 与新代码/测试/本政策的 release 都必须通过。任何失败写 BLOCKED，保留旧结果，不自动改策略重试。
