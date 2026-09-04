# N0+ SN1 合成资格代码审查

**时间**：2026-09-04 14:42:33 +08:00
**ARIS workflow**：`experiment-bridge`
**审查路线**：fresh `gpt-5.6-sol`、`xhigh`、same-family provisional
**最终裁决**：`PASS_SYNTHETIC_CONTRACT_ONLY`

## 审查边界

本审查只覆盖 7 个 Tier-A CPU 原型在确定性合成夹具上的行为契约。没有读取真实电容数据，没有计算 accuracy、calibration、RUL 或模型排名，没有调用 Ark/API，也没有运行 GPU。

## 首轮阻断与修复

首轮审查为 `BLOCKED`，发现四类实质问题：

1. PF 在同化首个观测前错误前进一步，导致预测 horizon 偏一格；现改为首点只同化、从第二点起 transition，并增加近无噪声线性 oracle。
2. 原 suffix 测试使用了参与拟合的目标 unit；现新增完全不进入训练映射的 held-out synthetic evaluation unit，并机械检查不与训练序列重复。
3. fitted state 可变且只校验 candidate ID；现冻结 state，绑定 registry/proposal identity、horizons、scale、seed 和候选特定 key/type，mapping 只读、residual array 只读。
4. 无重试语义与候选 gate 覆盖不足；现注入 fit/forecast failure 并断言各只调用一次，覆盖 registry 中全部 8 个非 SN1 候选和全部 7 条路径的 unit-order invariance。

此外，small-ML 的区间只是训练内 signed-residual quantile。代码和资格输出均明确标记 `SHAPE_ONLY_NOT_CALIBRATED`；它不能迁移为 P2 校准证据，P2 必须另行采用冻结的 held-out/LOCO、unit-balanced calibration。

## 二审证据

二审逐项确认：

- PF horizon alignment 由线性 oracle 覆盖；
- training/evaluation unit 分离；
- state identity 与 candidate-specific fitted keys fail-closed；
- authority、全 registry 排除、fit/forecast one-attempt failure 均有测试；
- 7 个候选均覆盖 hidden-suffix invariance、重复运行确定性、unit-order invariance；
- runner 明示 `PASS_CONTRACT_ONLY_NO_SCIENTIFIC_RESULT`、区间非校准、真实数据/API/GPU/outer labels 全为零。

最终 reviewer verdict：`PASS`，但只作为 same-family provisional gate。

## 验证命令

```bash
PYTHONDONTWRITEBYTECODE=1 .venv-n0-plus-sn0/bin/python -m pytest -q -p no:cacheprovider \
  tests/test_n0_plus_sn1_synthetic_models.py tests/test_n0_plus_sn1_runner.py
# 44 passed

PYTHONDONTWRITEBYTECODE=1 .venv-n0-plus-sn0/bin/python -m pytest -q -p no:cacheprovider tests
# 361 passed
```

裸 `pytest` 会继续递归收集 vendored `Auto-claude-code-research-in-sleep/tests`，与项目 `tests` 包同名，因而不是本项目回归入口；项目 README 冻结的入口为显式 `pytest tests`。

## 允许的唯一主张

> Seven CPU candidate prototypes pass synthetic-only checks for prefix input, held-out-unit isolation, fixed quantile completeness/nesting, within-environment repeatability, unit-order invariance, gated-candidate rejection, state identity and one-attempt failure behavior.

## 禁止外推

本 PASS 不支持 accuracy、calibration、superiority、real-data validity、nested-selection validity、cross-platform determinism 或 P2 readiness。进入真实数据前仍必须独立冻结 unit/origin/target/cutoff identity、irregular-grid 和 domain gate、direction、failure ledger/fallback、nested LOCO selection、held-out calibration、dependency artifact hashes，并重新人工批准。

完整 reviewer trace 保存在 `.aris/traces/experiment-bridge/2026-09-04_run01/`，按 ARIS 隐私规则仅本地保留、不提交 Git。
