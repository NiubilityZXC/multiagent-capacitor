# Ren 记录连续性审计边界

原P1-R1内的只读行语义观察。全量schema审计233文件已经完成；本版本核验来源命名候选组中的全部record行，不生成capacitance、SOH、RUL、目标或预测，也不把候选组提升为物理身份或模型资格。先fresh pre-run review和hash-matched release，后执行。旧代码、测试、seals、schema输出保持字节不变。

来源分组规则对应已静态审查的作者commit 8a71f99d9e25adbd722708199438a89ff739d2a5；本地源码SHA固定，仅作为文本证据不执行。主文件含step/cycle，后续__1、__2仅含record表；匹配113候选组、53单文件/60三文件、233唯一文件。组内文件按分片数字顺序、sheet按原工作簿顺序、行按原顺序读取，不排序数据本身。

只检查record表的cycle、step、status、record_number和record_time五个元数据字段；记录时间严格识别为H:MM:SS及可选1至6位小数，内部精确换算整数微秒进行比较，不写回原数据、不构造全局时间。前四字段必须数字类型、有限、可精确表示的整数；无效行记为invalid并切断相邻比较，不能跳过后把两边拼接。负标识单独计数，status允许负整数以避免擅自重定义状态。

逐条统计编号非+1、相邻编号重复、回退、前向缺口、缺失编号数、cycle回退、工步/状态变化、时间下降、同一cycle/step/status内时间下降以及相邻五字段key重复。key重复不是完整测量行重复，编号缺口只说明编号序列缺口，不自行等同于丢失测量。单sheet统计由独立单元格访问和row_types/row_values路径重建；时间换算独立实现，统计使用不同算法。共享xlrd和BIFF边界，不宣称独立解析器。

跨sheet及文件边界用首尾key重建同样的比较计数，不跨候选组连接。边界key保留在ignored本地证据中；公开只输出命名候选组、数量、计数和证据SHA。每组完成即持久化。解析/表头/哈希/重建不一致fail closed并保存BLOCKED；发现合法可解析的语义异常仅作为观察计数保存，所有目标/身份/P2资格始终false。时间下降不自动视为错误，需结合工步变化解释。

记录表头只允许上轮真实观察且作者源码相符的8/9列布局；不读取capacity等数值作为输出或推导目标。原schema与容器/Workbook字节再次核对，仍只向xlrd提供单独Workbook流。单sheet最大65535条数据记录，reference只暂存一个sheet的key，逐sheet卸载；不在内存保留全fleet记录。批处理一个本地CPU任务，不用训练队列、不新增依赖、不调用模型/API。

完成只支持“全部来源候选组内记录key的连续性观察已对账”。跨组局部测量重叠、物理身份、工况、目标、电流/电压端点、删失和whole-unit split仍需后续证据；不能将本次COMPLETE当Data Gate PASS。运行外层只读subprocess日志将记录实际子进程returncode，以减少会话过期后的退出状态缺失，不改变已冻结审计逻辑。
