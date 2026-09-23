# 来源边界与持久化证据独立重建

2026-09-23。ARIS experiment-bridge；P1 观察证据实现，不是 fleet release、真实目标生成或 Data Gate PASS。

## 本轮实现

- `ren_target_source.py` 复用现有命名分组、顺序、路径、单链接文件、大小、容器 SHA 与 Workbook SHA 检查；调用者仍必须提供既有批准 preflight 的完整 reports/schema。该模块不自行授权任意源集合，也没有启动 CLI。
- `ren_target_verify.py` 从已审 Workbook event 解码边界重新计算全部组级字段；不调用生产侧 collect_group、step reducer 或 summary join。重新统计连续工步、计数/极值/变化、原始位置/energy、summary 对照、周期全部成员/符号分桶、未验证求和假设和所有禁止标志。
- 对持久化 JSON 做严格字段集合、列表长度、类型与数值比对，拒绝额外/遗漏字段、bool/int 混淆和非有限数。独立性限于派生字段重建；底层 Workbook 解码器共享，其内部已有 row/cell 双路径检查。不是完全不同 XLS 解析器的交叉验证。
- verifier 重新读取源容器，因此规划中的完整运行是生产与验证两次源遍历；后续 fleet 时间/空间预算必须显式计入，不能按单遍耗时报告。

## 测试与保留的失败

1. 09-22 第一轮新增测试：3 failed、24 passed。两项测试错误地要求叶子字段超过 140（实际两种布局分别为 108/112）；断号测试误同时偏移两片的记录号，仍然连续。09-23 修正断言及仅更改末片记录号，27 passed。
2. 第一版真实 OLE 合成集成：2 failed。旧 `.venv-ren-p1r1` 有 olefile/xlrd，但新包式导入触发既有 `audit_cap.__init__ -> stress2`，环境缺 numpy；失败发生在导入阶段，不是数据/解析成功。
3. 依据已有依赖安装授权，仅在 `.venv-audit-cap` 补装与旧环境相同的 `olefile==0.47`；未修改旧生产环境或冻结包入口。使用当前审计解释器完成两种布局的合成 OLE → Workbook → JSON 落盘 → 独立重建，并验证落盘篡改被拒绝。
4. 当前新增测试 31 passed / 0.76s；包括逐叶子字段变异、增删字段、生产 reducer 故障注入、跨片事件缺失/多出/错位/断号、保留异常时释放资源、源容器变化及缺失/链接、命名/顺序/schema 变化、多正电流工步求和、全零电流。
5. 最终专用回归：`tests/test_ren_*.py tests/test_durable_local_job.py`，500 passed、无跳过 / 21.07s。一般全项目最终回归：721 passed、152 skipped / 88.06s；新增 31 项在专用环境全部实际运行，没有以跳过替代通过。

所有输入都是合成夹具，没有新读真实电容 XLS、运行模型/API/GPU、生成 F/SOH/RUL 或授予 P2 资格。sources 的单元测试使用明确标注的模拟 OLE 隔离；另一个 `test_ren_target_source_ole.py` 才是真实 olefile 解析器的端到端测试。

## 可复现环境

项目 cwd；`.venv-audit-cap/bin/python` 3.12.3；numpy 1.26.4、pandas 2.2.2、scipy 1.11.4、xlrd 2.0.2、olefile 0.47、pytest 8.3.2。复现：

```bash
.venv-audit-cap/bin/python -m pytest -q tests/test_ren_target_verify.py tests/test_ren_target_source.py tests/test_ren_target_source_ole.py
.venv-audit-cap/bin/python -m pytest -q tests/test_ren_*.py tests/test_durable_local_job.py
```

## 尚需完成

独立组件 review 已收尾：PASS，无 blocking / non-blocking 缺陷；配置 gpt-5.6-sol xhigh、same-family provisional。reviewer 独立运行 31 项测试通过 / 2.76s。完整报告在 ignored `data/raw/ren_scs/target_source_verify_review_20260923.md`，SHA-256 `7ca60fdb82f812509e42db170f44e0db3fa0c7503388d2eabfee8e92817e6ca5`；原始 trace 在 ignored `.aris/traces/experiment-bridge/2026-09-23_run01/`。这不是整体 pre-run 通过。

下一步接入固定覆盖的 fleet 持久化/失败回执/启动入口、冻结预算和整体 release，进行完整入口对抗测试及整体 pre-run review。通过后才运行批准边界内的真实 sanity 与容量资格审计。数据重复对、容量可推导性、终止/删失与 whole-unit 切分仍须基于真实证据裁决。
