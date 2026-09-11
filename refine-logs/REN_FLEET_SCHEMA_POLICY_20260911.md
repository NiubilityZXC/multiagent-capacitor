# Ren 全量只读 schema 审计执行边界

承接原 P1-R1 的 R1D/R1E 范围。首文件试跑真实 exit 0，5 表、211256 存储行，固定 SUMMARY 哈希作为 sanity prerequisite。本版本只将同一已审查 Workbook-only 读者扩展到原静态清单的全部 233 个唯一文件；不把 schema 通过等同于完整 R1E/R1F 或模型数据资格。旧代码、seals、审查记录、试跑输出不修改。

执行前必须取得本版本 fresh pre-run PASS，release 绑定代码、测试、政策和 .gitignore；核对原批准、恢复 verifier、隔离环境、catalog/diagnostics/旧静态 manifests、首文件试跑 evidence。全部文件先通过旧 JSON 结构分类，之后按固定 member_path 字典序逐个读取。每个容器与 Workbook 流都再次匹配旧 SHA，只把单独 Workbook 字节提供给固定 xlrd；禁止公式/VBA/对象/外部链接执行。

每文件分别由原 schema_rows 与新增 rebuild 重建全部 schema 字段。后者不用前者输出，不调用其统计函数，用 row_types/row_values 独立累计类型、非有限数和文本提示；要求完整 JSON 的键、值、类型一致。两者共享 xlrd 和字节边界，所以这是独立统计重建，不是独立解析器或物理真实性验证。逐文件持久化后再核对 receipt；全部233文件完成后才产生汇总和 COMPLETE。失败保存已完成记录及 BLOCKED，不重试、不跳过文件、不自动修改策略。顺序执行、每表卸载，不宣称行级流式；每文件两个独立解析轮次。一个 CPU 审计任务，不涉及训练队列或 GPU。

原始 sheet 名、首八行文本提示均限 ignored staging；公开只发布文件路径、证据哈希、维度/类型派生的计数与禁止模型标志。数值单元格不发布、不生成预测或新目标。status/p2_eligible=false 保持显式。此版本不推断表头为有效单位，也不推断文件名为物理身份；mAh/F、时间归零、跨表完整性、缺失、重复、identity、target、censor、whole-unit split 仍由后续实证审计独立裁决。

预期运行规模为原容器合计 15,223,551,488 bytes，最大93,806,080 bytes。运行时间需依实际进度估计，不承诺固定完成时间。每完成一文件立即写只增不改的本地证据/公开 receipt 并输出进度；中断时不伪造 exit code/COMPLETE，不直接覆盖旧目录重跑。原始数据继续 ignored，不新增下载、不改环境、不调用 Ark/其他模型 API。
