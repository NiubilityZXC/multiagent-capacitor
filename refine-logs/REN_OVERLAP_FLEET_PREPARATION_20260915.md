# 全量重叠审计下一执行单元（尚未放行）

沿用 Ren P1-R1 授权，仅做来源测量投影重叠审计。现有 first-two release 不能用于全量运行；保留其26项绑定文件不变，新增 full-fleet caller 与测试、政策和运行 release。

## 固定输入与复用边界

使用已完成的 recovery/schema/chronology，不重做解压与 archive test。由现有 chronology preflight 重建全部113来源命名候选组、233文件与1,633 record 表；新增入口必须显式检查104,190,778行且不能保留 pilot 的 `groups[:2]`。复用已测试的 measurement stream、磁盘索引和 append-only pipeline；不能 monkeypatch pilot 的全局常量来扩大其授权。

pilot 的运行后独立复核通过及公共 SUMMARY/COMPLETE 是全量放行前置证据。全量结果仍为 overlap observations，不自动把 `physical_identity_verified`、`target_verified` 或 `p2_eligible` 置 true。

## 资源与失败纪律

49字节记录的全量 spool 负载精确为5,105,348,122字节，不含SQLite、元数据和文件系统开销。2026-09-15本地只读磁盘检查显示约720GiB空闲；该数不是启动时保证，入口须重新检查。

pilot 的指纹稀疏率不能作为全量最坏情况上界：选中指纹数可为 O(N)，跨组同指纹对可呈二次增长。全量版本建议预检至少40GiB可用空间并保留1,000,000候选对上限；上限触发必须 BLOCKED、无 COMPLETE，不能按截断结果宣称无重叠。该预算尚待整体 pre-run review，不是当前运行授权。

## 必测项与后续衔接

全量入口测试覆盖：缺少或错误 release 时不读取真实来源；pilot prerequisite 错误；组/文件/表/行覆盖差异；资源不足；全组与多分片顺序；成功结果保持所有禁止标志 false。沿用 pipeline 的晚失败、遗漏指纹、持久化篡改和预算超限对抗测试，不重复修改已冻结版本。

全量完成后再结合作者来源证据、设备身份、容量/ESR物理定义、终止/删失和 whole-unit 切分作最终 Data Gate 裁决。不能把目前两组零候选用于提前放行模型、LLM Agent 或 RUL。
