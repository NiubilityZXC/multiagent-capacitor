# M3 未提交工作树保护快照

- 时间：2026-08-27T11:17:21+08:00
- 主仓库 HEAD：`7f48fe48f3fc8dae471eb21d576145dd6101896f`
- `origin/main`：`7f48fe48f3fc8dae471eb21d576145dd6101896f`
- 快照性质：在新双 storyline/P1 指令之后、任何新写入或数据获取之前生成。
- 既有测试证据边界：提交 `7f48fe4` 的 canonical suite 为 204 passed；新增三个离线模块合并后曾得到 245 passed，但随后 provider/evaluator/runner 集成继续变化，245 passed **不覆盖本快照**。本快照最近一次聚焦测试为 103 passed、1 failed（正式 attested Ark durable-path 的 runner evidence binding 尚待定位）。

## Canonical 文件不变性

| 文件 | 要求 SHA-256 | 快照 SHA-256 | 状态 |
|---|---|---|---|
| `refine-logs/EXPERIMENT_PLAN.md` | `df968d2e7ba33748043e547165143d9247358afca573946f3dde573c8c04b6d2` | `df968d2e7ba33748043e547165143d9247358afca573946f3dde573c8c04b6d2` | MATCH；禁止修改 |
| `refine-logs/round-3-refinement.md` | `d4d40b0a7e3f5c9030bfe80e5ede3d059673c3b3c96122c9cf050097aa54f110` | `d4d40b0a7e3f5c9030bfe80e5ede3d059673c3b3c96122c9cf050097aa54f110` | MATCH；禁止修改 |

## 已跟踪但未提交

| 路径 | 快照 SHA-256 / 状态 | 保护说明 |
|---|---|---|
| `Auto-claude-code-research-in-sleep` | gitlink `53562a7c...` → `9cbb6aab...`；子仓库内部 clean | ARIS 上游指针变化；不得误覆盖 |
| `experiments/vfps_agent/ark_provider.py` | `44b804a1cf5d20c75ff8c14d97584207fadbfd25d8ab125ac435775cd7cfb94f` | canonical schema、transport receipt、slot/wire-call 审计集成中 |
| `experiments/vfps_agent/evaluator_service.py` | `376b2cf0eb22f5c0aa216907a7821b4509ad59f61497f0871a5108f0552cca58` | generation-wide barrier/finalize authorization 集成中 |
| `experiments/vfps_agent/runner.py` | `187fd6f91df844e46ed4ce72aafea96f4221e519b8f0583aa193f2ba0292c307` | canonical response spec 重建校验 |
| `tests/test_capact_m2_runner.py` | `c46bb2088190f06d75e6748dbddd5f4baf8fd047e583323861fc1a0708f9e9a9` | 正式 durable path 集成测试与临时诊断 |
| `tests/test_vfps_ark_provider.py` | `99044fba50104b7857fc9b2ed3c33a510eba9adf3da4ee034b4e6be22c872cad` | mock-only 明示豁免与 schema gate 测试 |

## 未跟踪保护文件

| 路径 | 快照 SHA-256 | 作用 |
|---|---|---|
| `experiments/vfps_agent/ark_https_transport.py` | `6d4ec636b8bf98996573a2048905726c8bda49a61daf2c067d4d309889062624` | 固定 Ark Plan origin 的单次 stdlib HTTPS transport |
| `experiments/vfps_agent/generation_barrier.py` | `81c20a022687df8468c50a934c979cfe987d3092ccd7fbaee52ecceb911e6699` | generation Cartesian plan、preflight、permit、score-input seal |
| `experiments/vfps_agent/response_schema.py` | `37ebd7dfad7678e373173a33cb963d8905bf2150a4d5893f305b099ef2b3bd15` | 全 arm canonical response schema registry |
| `tests/__init__.py` | `0012ba1f78aa90e379a162ea0388fe6a3a7d887b94bbbbdcd60bb5f1de8cfd35` | 避免外部 `tests` 包遮蔽 |
| `tests/test_vfps_ark_https_transport.py` | `e6a19a23856400afc75aae8389ccd52f816be873f50a05c66549b220e4d79830` | transport 离线 fake-I/O 测试 |
| `tests/test_vfps_generation_barrier.py` | `9c1488aaabae41ae678badf8d0b36703bf2899089b2f176b8e075ef8090f5fa2` | generation barrier 测试 |
| `tests/test_vfps_response_schema.py` | `3a1dd372efc946199312016ce079ddd56a9b573b82b6a56aa1ed35cfef765b25` | arm/schema/action 权限测试 |

## 继续执行约束

1. 先修复当前正式 attested path 与 evaluator formal path，移除临时测试诊断。
2. 对本快照之后的完整树重新运行 canonical full tests、`py_compile`、`git diff --check`、secret path-only scan 与逐文件 diff review。
3. fresh independent release review 必须读取稳定后的文件；此前 204/245 passed 均不得替代。
4. P1 只可下载、校验、静态/行级审计；不得运行作者脚本、训练、RUL scoring、P3、development API、P4/P5 或真实 LLM 预测。
