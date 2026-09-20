# 工步证据纯函数实现与独立审查

2026-09-20。ARIS experiment-bridge。范围仅 `ren_step_evidence.py` 纯函数及合成测试，不是完整 XLS caller 或真实运行 release。

实现按连续 native `(cycle, step, status)` 归组，保留首末记录、时间、电压、电流、mAh，以及符号/变化计数。跨 chunk 保持状态；非连续重复 key 分别保留，不用字典覆盖。工作内存 O(1)，不排序、不插值、不补零、不推导 F/SOH/RUL、不决定资格。未知 status 保留原值；非有限或错误 canonical 类型直接失败。

调用方仍须独立证明源文件/表/行覆盖并完整耗尽迭代器：已收到部分工步输出不能当完整成功。后续 summary join、真实数据适配器、目标资格、终止与 split 仍未实现/放行。

## 真实验证结果

- 新纯函数测试：19 passed；固定随机种子，独立 groupby/list 参考路径，以及全部 121 个切片边界。
- 新组件加旧审计必测：237 passed、0 skipped，3.95 秒。
- 一般回归 `.venv-n0-plus-sn0/bin/python -m pytest -q tests`：702 passed、58 skipped，51.73 秒；必需 XLS 路径另由隔离审计环境覆盖。
- fresh GPT-5.6-Sol xhigh 独立审查 PASS，无阻断；reviewer 自行运行 19 passed in 0.41s。类别 same-family provisional，不是跨模型家族科学结论。

## 精确工件

- implementation SHA-256：`358fc76e69f2300e49d2154e6ea8f50c2d36eb7d82d3da52b585345cb7c61f07`。
- tests SHA-256：`4d624ffd6d1a45cb500f8ced336a209ab859e7f898f774c1b050df32f601c9c4`。
- 完整 reviewer 响应在 ignored `data/raw/ren_scs/step_evidence_review_20260920.md`，SHA-256 `240c19994196046fa544c39f1af3f24b5d79ce499e8db000163c1dc3908e88ce`。

本轮没有更改已冻结 R2 文件，没有新增真实数据读取、模型/API、GPU、数值 target 或 P2 授权。R2 独立 post-run 审查另行执行，本纯函数 PASS 不能替代它。
