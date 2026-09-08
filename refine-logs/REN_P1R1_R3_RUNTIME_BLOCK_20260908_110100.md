# Ren P1-R1 R3 解压 transcript 格式阻断

Run `p1r1_20260908_105705`：R1A PASS，R1B PASS（233 files + 4 directories，完整成员集合精确一致）。R1C 已实际提取，但末级 transcript 比较阻断，保持 quarantine，未运行 XLS 静态或行级解析。

R1C command exit=0、stderr=0、All OK=1、所有 danger markers=0。已扫描输出为 233 regular files + 4 directories，15,223,551,488 bytes；missing/unexpected/unsafe_or_mismatched 均空，所有逐文件 size/CRC/type 通过。

唯一失败字段为 `extracted_path_set_exact=false`。官方工具打印 `Extracting /absolute/quarantine_extracted/batchN/file.xls OK`，当前 code 把它与 `batchN/file.xls` 比较。原始 transcript SHA-256：`1dc2a3b5ba98bdbcdafa184536b35c6e63a9355eb26689cdecc5b56aaa303085`。

修复必须将 ledger 中相对 member path 与固定 quarantine destination 组合为精确预期绝对路径，再比较完整 sorted list；不采用任意 basename 匹配，不放过目录外路径、未知项或重复项。需要 generator、独立 verifier、完整 mock subprocess 与回归测试同时修改并重新 pre-run 复审。

当前 R3 的 `R1C_BLOCKED.json`、EXTRACTION_MANIFEST、quarantine 文件保持不变，R1C seal 缺失即禁止静态检查。已批准的同一 source、同一官方工具不变；修复后必须使用新的 append-only run。未执行模型/API、target、RUL、GPU，未产生科学精度结论。
