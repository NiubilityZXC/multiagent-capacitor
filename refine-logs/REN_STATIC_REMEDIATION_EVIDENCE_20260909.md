# Ren 静态阻断修复：证据与执行边界

本轮承接用户“开始解决 / 继续”，只修复 Data Gate 前置问题，不启动 P2。归档恢复成功的 R4 与原 R1D 工件保持不变，不重新下载或解压数据。

## 已核验规范

- Microsoft [MS-XLS] revision 12.2 / 2025-08-19：[官方入口](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-xls/cd03cb5f-ca02-4934-a391-bb674cb8aa06)。DOCX 原件已从入口链接下载至 ignored `data/raw/ren_scs/specs_20260909/MS-XLS-250819.docx`，SHA-256 `66800e9bdfae1eec8e462c2e2d6411f56f2592f79a0b980de00df1e7bf2210b2`。只解读 ZIP 内文档 XML，没有打开 Office 或执行文档内容。
- 根据该规范 2.3 的两张枚举表交叉提取，实际 60 个 unknown ID 全部有对应名称。逐 ID、章节和涉及工作簿数见 `REN_BIFF_OBSERVED_CATALOG_20260909.json`。这个目录是待审工作清单，**不是新的安全白名单**。
- [Pls](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-xls/baf5f46f-0720-4cad-a4c5-51094868d90a) 与 [Common Productions](https://learn.microsoft.com/en-us/openspecs/office_file_formats/ms-xls/a1b3d8b4-7442-41fd-9c57-bbd2a6394082) 将 PLS/CONTINUE 放在打印设置上下文中。仍须核验本数据的真实前序/后序记录，不能仅凭 CONTINUE 的类型作通用放行。
- [早期 Microsoft XLS 规范](https://download.microsoft.com/download/5/0/1/501ED102-E53F-4CE0-AA6B-B0F93629DDC6/Office/Excel97-2007BinaryFileFormat%28xls%29Specification.pdf) 区分 CompObj 元数据与 VBA storage。旧代码把根 CompObj 标记为 embedded_object 是保守粗分类；是否存在实际嵌入容器需要更具体的目录诊断。
- [xlrd 官方文档](https://xlrd.readthedocs.io/en/latest/index.html) 说明宏/VBA/对象不被执行，但会读取公式缓存。因此库行为支持只读方案设计，却不能代替本项目的公式缓存与目标语义 Gate。

## 本轮实现与证据含义

`ren_static_context.py` 是新建的诊断工具，不编辑旧 scanner 或任何既有 seal。只对之前被 OLE 或 CONTINUE 标记的工作簿作定向检查：区分根 CompObj、VBA 项目树、其他宏名称标记和嵌入容器标记；只在需要 CONTINUE 上下文时打开 Workbook 流，遍历记录头并跳过全部 payload，不解码单元格、字符串、公式或打印设置内容。

运行前要求既有恢复 independent verifier、隔离环境验证、原静态 manifest 校验与新诊断 pre-run release。诊断输出始终 `p2_eligible=false`、`row_parse_authorized=false`。即使识别完成，也不解除旧 `BLOCKED_ROW_PARSE`。

新增 18 项合成测试通过；全项目 510 项回归通过（40.51 秒）。实际运行仍以独立 pre-run review 为前置条件，不以此文档冒充放行。

对已有 233 份结构 JSON 的只读汇总另显示：233 个 Workbook 流均完成 framing，未扫描余量为 0；在这些流中未观察到 FORMULA、EXTERNSHEET、NAME、EXTERNNAME、FILEPASS、OBJ、SUPBOOK、HLINK、ARRAY、SHRFMLA 的 record ID。53 个文件同时出现 ObProj 与 ObNoMacros。这里只描述旧扫描器的结构计数，不证明其他 OLE 流没有内容，也不据此确认数据值或无宏行为。

## 后续必须解决的实质问题

1. 对 60 个已命名 ID 建立有语义依据的处理策略，而非静默忽略未知记录；特别处理 VBA 项目标记、刷新策略与 Shared Features。
2. 对真实 CONTINUE 链落实只读打印设置隔离；对 VBA/对象流明确不读取、不执行、不给预测模型提供这些内容的边界。不得把目录名称标记升级为恶意判定，也不得把其存在当作真实目标已验证。
3. 新静态版本测试和独立复审通过后，才能运行 R1E schema/rows 审计；之后再核验 physical identity、时间、目标、重复及切分。P2 仍须具体冻结的执行清单。
