# Preseal Integrity Review

**Verdict: PASS**

**Reviewed at:** `2026-08-31T17:59:37+08:00`  
**Scope:** independent read-only integrity review only. No network/API call, download, archive extraction, parser/decoder/tool execution, fitting, training, scoring, SOH/RUL construction, or model prediction was performed.

This PASS means only that the current unapproved preseal bundle is internally hash-consistent and its offline contracts validate. It is **not** a data-science eligibility PASS, human approval, master seal, execution authority, or permission to cross the current gate.

## 1. Canonical pins

Both canonical files match the pinned SHA-256 values exactly:

- `refine-logs/EXPERIMENT_PLAN.md`: `df968d2e7ba33748043e547165143d9247358afca573946f3dde573c8c04b6d2`
- `refine-logs/round-3-refinement.md`: `d4d40b0a7e3f5c9030bfe80e5ede3d059673c3b3c96122c9cf050097aa54f110`

These hashes also match the corresponding entries in `PLAN_A_PRESEAL_BUNDLE_MANIFEST.json` and the canonical pins in `PLAN_A_HYPOTHESIS_REGISTRY.json`.

## 2. Preseal manifest and generation identity

- Current preseal-manifest SHA-256: `2799255cb44d0e50acc86771509b73b17595153c34f95f3b6566095b2edc397a`.
- All **19/19** files listed by `PLAN_A_PRESEAL_BUNDLE_MANIFEST.json` exist and match their listed SHA-256 values.
- Generation payload was read as exactly 115 UTF-8 bytes with no terminal newline:
  `{"arm_registry":"CANONICAL_11_PLUS_ARCH1","generation_label":"GENERATION_1","protocol_lineage":"dual_storyline_v1"}`
- Direct SHA-256 of those bytes is `9d27f1c89870c44542921622cf79199abdadf9e3cb718b0467f90665435c0947`, exactly matching `generation.generation_id`.
- The manifest records `formal_generation_created=false`, `approval.state=UNAPPROVED_HUMAN_GATE_REQUIRED`, `execution_authority=NONE`, null human-approval hash, and null master-seal hash.

## 3. P1 root and internal hash-list integrity

Both bundles passed direct root-hash comparison and full `sha256sum -c` traversal of their internal artifact hash lists.

### Patrizi HSC

- `COMPLETE.json`: `140387643564c8df17f4cd683595db778b7cee9e0af7bd5e79d7e39c3083b6ec`
- `ARTIFACT_MANIFEST.json`: `68fceef2b15ce5593c583afad3a3d64635f7861f075bbb758dc759adfaac065e`
- `ARTIFACT_HASHES.sha256`: `694c4b7890502dc7222772ee364cf213149c9a5d59b93e44242f69fcd53b8d1a`
- Internal entries: **14/14 OK**.
- Scientific state remains `ACQUISITION_INTEGRITY_PASS_ROW_LEVEL_BLOCKED`, `scientific_eligibility=BLOCKED`, `rul_status=NA`.

### Ren SCS

- `COMPLETE.json`: `2a5a25d9c8d92583aa6ff137010da0b0c16a13e4bbd5fc57861c0a20edec7f72`
- `ARTIFACT_MANIFEST.json`: `eef896f082a7b24f4cd1da7d213f90306045c99c3f66fa69ed92f94f6c231510`
- `ARTIFACT_HASHES.sha256`: `b5ba97584a2c7bff2c76b3a45d7d85282ea81f7e00e1de16ff4db492f7607877`
- Internal entries: **15/15 OK**.
- Scientific state remains `ACQUISITION_INTEGRITY_PASS_ARCHIVE_TEST_BLOCKED_NO_EXTRACTION`, `scientific_eligibility=BLOCKED`, `extraction=NOT_ATTEMPTED_STRONG_STOP`, `rul_status=NA`.

No blocked P1 state was promoted to a scientific PASS.

## 4. Hypothesis registry

Machine audit of `PLAN_A_HYPOTHESIS_REGISTRY.json` passed:

- Primary registry has exactly **7** records, slots exactly `[1,2,3,4,5,6,7]`, and 7 unique hypothesis IDs.
- There are 32 component references and exactly **20 unique component IDs**.
- The set of referenced component IDs equals the 20-entry `fixed_unique_component_ids` set; no missing or extra component ID was found.
- `simultaneous_component_bounds.fixed_unique_component_count=20` and uses `0.05/20`, with NA components retained and no alpha recycling.
- Holm is confined to the seven composite p-values.
- `PLAN_A_BASE` explicitly requires Holm rejections for `A-NI-N0`, `A-NI-CK`, and `A-OP-CK`, plus **12** explicit Bonferroni simultaneous component-bound crossings.
- `PLAN_A_AGGRESSIVE` inherits the base tier and additionally requires Holm rejections for `A-SUP-N0` and `A-SUP-CK`, plus **2** explicit Bonferroni simultaneous component-bound crossings.
- Both tiers identify their bound family as `BONFERRONI_SIMULTANEOUS_COMPONENT_BOUND_NOT_HOLM_CI`.

Therefore the tier machine mapping requires both Holm rejection outcomes and Bonferroni simultaneous component bounds; it does not substitute one for the other.

## 5. Architecture validator contract

All three pinned architecture-contract hashes match direct recomputation:

- Validator file `experiments/vfps_agent/architecture_registry.py`: `08e263690c59c83e54bdcc1b06e318e1acebe63d8b60109944ec8b6667f6a951`
- Test file `tests/test_vfps_architecture_registry.py`: `498f3a159cc898c35d6837a9a0e20ffec47336a9d6071109f1bf4c0860b0ede3`
- Canonical hash of the in-registry `artifact_schemas` resource: `9d3538544386698be7789ffe7e286288793a4e1a7fc5ae080c160e3f6a5c2288`

`validate_registry(load_registry())` completed without exception. The focused offline test command completed with **8 passed in 0.06s**:

```text
PYTHONDONTWRITEBYTECODE=1 .venv-audit-cap/bin/python -B -m pytest -q -p no:cacheprovider tests/test_vfps_architecture_registry.py
........                                                                 [100%]
8 passed in 0.06s
```

## 6. Current authority and prohibitions

The manifest, Plan A problem-anchor addendum, master joint-seal protocol, execution envelope, architecture human/machine specifications, hypothesis registry, and pending baseline decision are consistent on the current gate:

- Allowed scope is limited to read-only reverification of the existing Ren/Patrizi P1 evidence, already-existing static audit without extraction or repair, non-predictive document/code work, and offline tests/release review.
- Prohibited without new approval: new download; Ren extraction; new decoder/archive tool/parser/author script/repair; P2 fitting/training/scoring/power/SOH/RUL work; P3 authenticated discovery/probes; development API; P4/P5; formal outer evaluation; and real LLM capacitor prediction.
- Architecture registry says `PRESEAL_UNAPPROVED_NO_API` and `execution_authorized=false`.
- Hypothesis registry says `UNAPPROVED_P2_BLOCKED` and limits authority to offline protocol specification.
- Baseline decision remains `PENDING_HUMAN_DECISION`, has no selected option, no approval hash, and `execution_authority=NONE`.

No inspected artifact grants contradictory execution authority.

## Final determination

**PASS — preseal integrity and offline contract consistency.**

The operational/scientific project state remains **BLOCKED at the human gate and P1 Ren/Patrizi scientific gates**. This report does not authorize extraction, P2/P3, any API lane, modeling, RUL work, generation execution, unsealing, or paper performance claims.