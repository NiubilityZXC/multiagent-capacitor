# Benchmark-L P1 Data Gate Report

- Overall: `FAIL`
- EIS events: 1752
- Raw inner slots: 9316 = 8835 eligible + 0 quarantined + 481 structural empty
- Nonempty matrices: 8835
- Raw-order nonchronological unit-events: {"ES10":16,"ES12":13,"ES14":10}
- Transient time: {"ES10":"FAIL","ES12":"BLOCKED","ES14":"PASS"}
- Duplicate candidates: 1; every candidate remains unresolved and creates no split group.

All 58/59 EIS rows are retained. Zero-frequency acquisition preambles are classified, not removed. Header/Data were paired by raw replicate index before stable acquisition-time sorting.

`finish_candidate_inferred` is start plus maximum raw `time/s`; it is not a measured save/finish time. Causal availability therefore remains BLOCKED.

ES12 timestamp/signal candidates are reported without trimming, interpolation, sorting, or applied repair. Sequence end is not treated as EOL.

No capacity, ESR, SOH, or RUL numeric target and no model result is emitted in P1.
