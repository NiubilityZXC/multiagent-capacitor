# P1 Ren / Patrizi Decision and Hash Index

**Status**: `HUMAN_GATE_REQUIRED`  
**Scope**: acquisition and static Data Gate only; no model, API, SOH/RUL construction, row repair, or Ren extraction

The authoritative machine-readable index is
`data/audit/P1_REN_PATRIZI_DECISION_INDEX.json`. Both 2026-08-27 bundles are
retained as legacy evidence. They remain internally hash-consistent for their
listed artifacts, but their completion decision was not part of the old hash
graph. The append-only 2026-08-28 reruns correct that packaging defect by
writing `COMPLETE.json` before, and binding it through, both
`ARTIFACT_MANIFEST.json` and `ARTIFACT_HASHES.sha256`.

## Current decisions

| Source | Current bundle | Acquisition | Scientific eligibility | SOH / RUL / ESR | Required next gate |
|---|---|---|---|---|---|
| Patrizi HSC | `data/audit/patrizi_hsc/p1_20260828_180200` | exact payload bytes pass | `BLOCKED` | `BLOCKED / NA / NA` | resolve unit identity, raw/document conflicts, target semantics, event/censor rules |
| Ren SCs | `data/audit/ren_scs/p1_20260828_180210` | exact payload bytes and metadata listing pass | `BLOCKED` | `BLOCKED / NA / NA` | approve a new archive tool/parser plan |

Patrizi remains `ACQUISITION_INTEGRITY_PASS_ROW_LEVEL_BLOCKED`. Ren remains
`ACQUISITION_INTEGRITY_PASS_ARCHIVE_TEST_BLOCKED_NO_EXTRACTION`; the archive
test reports an unsupported RAR method, so extraction was deliberately not
attempted. These outcomes do not authorize P2, P3, development API, P4/P5,
outer evaluation, or result-bearing paper claims.

## Sealed bundle roots

| Source | `COMPLETE.json` SHA-256 | `ARTIFACT_MANIFEST.json` SHA-256 | `ARTIFACT_HASHES.sha256` SHA-256 |
|---|---|---|---|
| Patrizi | `140387643564c8df17f4cd683595db778b7cee9e0af7bd5e79d7e39c3083b6ec` | `68fceef2b15ce5593c583afad3a3d64635f7861f075bbb758dc759adfaac065e` | `694c4b7890502dc7222772ee364cf213149c9a5d59b93e44242f69fcd53b8d1a` |
| Ren | `2a5a25d9c8d92583aa6ff137010da0b0c16a13e4bbd5fc57861c0a20edec7f72` | `eef896f082a7b24f4cd1da7d213f90306045c99c3f66fa69ed92f94f6c231510` | `b5ba97584a2c7bff2c76b3a45d7d85282ea81f7e00e1de16ff4db492f7607877` |

Canonical protocol files remain byte-identical at their frozen SHA-256 values:

- `EXPERIMENT_PLAN.md`: `df968d2e7ba33748043e547165143d9247358afca573946f3dde573c8c04b6d2`
- `round-3-refinement.md`: `d4d40b0a7e3f5c9030bfe80e5ede3d059673c3b3c96122c9cf050097aa54f110`
