# AUDIT-Cap H0/H1 Final CPU Sanity Results — Truth-Blind Decision Revision

**Generated**: 2026-08-20 16:50 CST  
**Status**: implementation sanity complete; all accuracy/RUL/interval/Design-Gate/agent-topology claims remain blocked  
**Supersedes**: `EXPERIMENT_RESULTS_20260820_161949.md` for code/run lineage only; all scientific numbers remain identical

## Final canonical directories

- Primary Stress context=4: `results/audit_cap/stress2_context4_final2_20260820_164848`
- Stress context=3 sensitivity: `results/audit_cap/stress2_context3_final2_sensitivity_20260820_164848`
- Stress context=5 sensitivity: `results/audit_cap/stress2_context5_final2_sensitivity_20260820_164848`
- Stress context=4 reproduction: `results/audit_cap/stress2_context4_final2_repro_20260820_164848`
- Design quick: `results/audit_cap/design_quick_final2_20260820_164848`
- Design quick reproduction: `results/audit_cap/design_quick_final2_repro_20260820_164848`

All older directories are retained as immutable audit history.

## Final lineage

- Package code hash: `36f8a0af273cfbe606f08383a6ea8594d6bf93d5f96d7f6094d60e3e7f240e90`.
- Stress protocol hash: `3b1b447172466fecdab63b4595124d53d3d9f2a0becf73886affb25334d873dc`.
- Design protocol hash: `316c67f74d746102c52577e09bd2645934c753f9d91ea413ca6697707d2ca623`.
- Primary Stress manifest: `630529883af0c5ee5751df5aca7567834cf329a4e94eda996e69012a631cf459`.
- Primary Stress prediction ledger/seal: `d18599d0068074d784a89ce9aa16e5fcc2a4adc191dfe4dfbf30358d96f2984a` / `867470e36ccbfea8811e8c357b79336879419ccd94d134c908a3e74c9789dc28`.
- Primary design manifest: `70de02aa9afaf670ac5d17fe31b827d5c556091b002e038e6bdd526877aef21a`.
- Design repeat ledger/seal: `b3b2353f9253127b8be997dbe0d54a86ce37be80aa92f2e5a4597af5b0182609` / `d20a90445693717a668c2ce5aacadf47c058d6c7a77ccae17cddda130d0504d4`.
- Design cell ledger/seal: `c49e94d893c3c76885ae1dcc6df3c9fe4871a00329e5ae5cf563930cf21fcad1` / `f5d48e9b49c775d7482fb9325ffb00ee546fbb9185bde71eb9369237356b325d`.

Every final manifest entry, ledger chain, seal, and `COMPLETE` binding verifies. Current code hashes match all final artifacts.

## Protocol correction

The quick-design code now implements the protocol's literal truth boundary:

1. `decide_losses(incumbent, candidates, scenario)` receives only observed unit-loss arrays and the frozen scenario. It selects/promotes without access to `true_effect`.
2. `score_simulation_decision(decision, true_effect)` receives the already-frozen decision and attaches simulation-only bias, coverage, and correctness diagnostics.

Changing `true_effect` after decision does not change selected candidate, p-value, interval, or effect estimate; a dedicated test asserts this. The full suite is now 32 tests, all passing.

## Numerical and reproduction status

- Stress context=3/4/5 still contain 1,512 / 1,296 / 1,080 matured predictions, all with zero prediction/scoring failures. Context=3 retains 144 disclosed, unselected window=4 tuning failures.
- The final context=4 scientific aggregate table is identical to every earlier generation. The 36 raw rows and interpretation remain those reported in `EXPERIMENT_RESULTS_20260820_155512.md`.
- Design remains 15 cells × 200 planned repeats: 2,987 analyzable and 13 explicit failures. Every cell statistic is unchanged.
- All 2,987 analyzable design rows were reconstructed from archived raw unit losses through the new truth-blind decision and post-decision scoring interfaces with zero mismatches.
- Same-code context=4 reproduction has 11 byte-identical stable artifacts. Design reproduction has four byte-identical sealed scientific artifacts; metadata differs only by command path/time and derived hashes.

## Claim ceiling

These results support only deterministic parser/replay/simulation operation on a six-column surrogate harness and reproducible same-process causal bookkeeping. They do not support any model winner, independent physical-device inference, RUL accuracy, interval calibration, cross-condition robustness, deployment readiness, formal Design Gate, or multi-agent advantage.

Permanent limitations remain:

- physical identities and duplicate groups are unverified;
- the causal barrier is self-attested same-process software evidence, not externally anchored chronology;
- quick design uses two-sided diagnostic intervals and is not the future one-sided formal Gate implementation;
- Benchmark L target/time/outcome gates remain blocked.

No external LLM or Volcengine Ark model was used for numerical generation, selection, or scoring.
