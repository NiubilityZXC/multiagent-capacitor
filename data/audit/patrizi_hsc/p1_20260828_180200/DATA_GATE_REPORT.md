# Patrizi HSC P1 Static Data Gate

- Overall decision: `ACQUISITION_INTEGRITY_PASS_ROW_LEVEL_BLOCKED`
- Scope: byte integrity and aggregate row-level static audit only.
- No model, forecast, SOH/RUL label, RUL score, LLM, Agent, or external API was run.
- MAT allowlist: only `HSC`; `__function_workspace__` was inventoried but not loaded.
- `Time`, `Method`, duration objects, and EIS tables remain `BLOCKED_STATIC_OPAQUE`.

## Gate decisions

- acquisition_integrity: `PASS_EXACT_BYTES_MD5_SHA256`
- container_safety: `PASS_HSC_ONLY_AUTHOR_WORKSPACE_EXCLUDED`
- identity: `BLOCKED_IDENTITY`
- schema_unit: `BLOCKED_DOCUMENTATION_CONFLICT_AND_STATIC_OPAQUE_FIELDS`
- chronology: `BLOCKED_ABSOLUTE_TIME_STATIC_OPAQUE_CYCLE_AXIS_PARTIAL_PASS`
- duplicate_overlap: `BLOCKED_IDENTITY_EXACT_NUMERIC_SCREEN_PASS`
- target: `BLOCKED_MODELING_ELIGIBILITY_RUL_NA_ESR_NA_SOH_BLOCKED`
- terminal_event_censor: `BLOCKED_NO_AUDITABLE_EVENT_RUL_NA`
- split_leakage: `BLOCKED_IDENTITY`

## Material findings

- The raw hierarchy exposes `ch1`-`ch8`, but no row-auditable physical serial/device IDs; Identity and LOCO are `BLOCKED_IDENTITY`.
- `Cap_ch` and `Cap_dis` are Ah capacity fields, not farad capacitance.
- Native `IR` is not automatically ESR; EIS-derived ESR is unavailable because MCOS tables were not decoded.
- SOH is blocked because `C_ref`, stabilization, normalization, and train-only rules are not frozen.
- RUL is `NA`; no event/censor truth was generated or scored.
- PDF/raw schema conflicts (top-field count, Cycle dtype, and duration-field descriptions) trigger a scientific schema/unit block.
- Summary cycle gaps within observed ranges: ch4:101, ch6:36;49;99, ch8:83.
- Exact numeric-trajectory hashing found no cross-channel duplicate, but physical overlap remains unresolved while identity is blocked.

## Downstream lock

All modeling, prediction, RUL, split generation, API, and P4/P5 actions remain blocked. The only positive conclusion is exact acquisition integrity.
