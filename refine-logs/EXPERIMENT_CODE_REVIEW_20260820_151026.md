# AUDIT-Cap 修复后二次独立审查

**审查时间**：2026-08-20 15:10:26 +0800  
**审查方式**：新的 fresh、零上下文独立审查者；只读审查与根目录定向测试。  
**结论**：**BLOCKED；不授予 `PASS_TO_RUN_SANITY`。**

## 首轮 8 项逐项裁决

1. **CLOSED — external storage / VDS 隔离。** 布局只读元数据；numeric scan 在任何 `dataset[...]` 前跳过 external/VDS；ExternalLink 不解引用。测试覆盖已删除 external raw 与不存在的 VDS source，并断言扫描元素数为零。
2. **CLOSED — ZIP member 与提取 MAT 的 SHA-256 对档。** ZIP 解压字节流逐块计算 SHA-256，提取文件独立计算 SHA-256，以精确相等为主判据；size/CRC 仅作辅助。
3. **OPEN — 预测仍未在未来标签可访问前 durable commit。** runner 先加载完整标签表，prediction phase 把 held-out 的完整 11 点 C/ESR 序列装入内存，并在全部 origins 生成后才写入/seal。`SEALED_BEFORE_LABEL_ACCESS` 因此只是声明，不是访问屏障。后缀不敏感测试不能替代真正的 label-service barrier。
4. **OPEN — planned-key failure closure 仍有异常缝隙。** config/state/predict/maturity 的普通失败路径已能铺满 common keys 并严格令 aggregate 为 NA；但 `_select_config(...)` 本身与部分 config hash 构造仍可能在 try 外抛错，使公共生成函数直接中止而没有 planned FAIL rows。
5. **OPEN — lineage 基本补齐，但 train-set commitment 不完整。** protocol/code/raw/split/seed/training snapshot/prefix/config 已纳入 prediction ID；现有 `train_set_hash` 字段未纳入 ID，maturity lineage 也不验证。将其篡改为全零不会改变 prediction ID。
6. **CLOSED — 全 missing 不伪造首点。** 全缺失 unit 保留 NaN/失败；repeat 显式 `FAIL_NO_MATURE_ORIGIN`；planned denominator 不变。
7. **CLOSED — effect grid 已消歧。** B1.1 quick 精确为 15 cells；5%/15% 仅属于未来 formal；quick 永远不作 Gate 裁决。
8. **CLOSED（仅表述约束）— B0 不冒充完整 Data Gate。** 输出明确 `partial_integrity_only`，physical mapping、Benchmark L 与 RUL 继续阻断。

## 独立验证

- 根目录四个定向测试：`27 passed in 4.90s`。
- 7 个实现文件与 4 个测试文件 `py_compile`：PASS。
- 普通 `git diff --check`：PASS；目标当前为 untracked，另做逐文件检查，代码无 whitespace 问题。
- 未运行 200-repeat quick 或完整 Stress-2 数值 sanity。

## 资格判断

- Stress-2 sanity：**BLOCKED**，必须关闭第 3/4/5 项。
- Quick design simulation：相关数值逻辑通过静态与定向测试，但本轮不作组合放行。
- Benchmark L：独立 **BLOCKED**，不得由 harness 状态替代 Data/Design/Freeze-B Gate。
- RUL：独立 **BLOCKED/NA**，termination/outcome gate 未通过，Stress-2 也只有 column-surrogate identity。
