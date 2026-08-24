# NASA Capacitor Electrical Stress: Partial Integrity and Schema Audit

- Audit directory: metadata_20260820_150856
- Automated schema: audit-cap.b0.v2
- Scope: ES10.mat, ES12.mat, ES14.mat from the 5,038,942,729-byte official archive
- Mode: metadata_only; numeric_scan_requested=false; numeric_scan_row_count=0
- Verdict: partial integrity + schema audit only

> This audit does not pass the full Data Gate. Benchmark L and every SOH/RUL evaluation remain blocked.

## 1. Evidence inputs

- AUDIT_SUMMARY.json: automated integrity and HDF5 inventory.
- DATA_MANIFEST.json: source URL, archive/member sizes, CRC32 and SHA256.
- HDF5_OBJECTS.csv: one row per audited HDF5 object, including shape, dtype, attributes and semantic quarantine.
- QUARANTINE.csv: 127 physically unmapped evaluation-relevant paths.
- refine-logs/LARGE_PACK_SCHEMA_PROBE.md: independent read-only metadata/reference probe with small-string and sparse-scalar checks.

Automated outputs and the schema probe have different scopes. Automated counts below come from the JSON/CSV audit. The 8,835-replicate and same-object-reference results come from the separate reference probe. Neither performed a full numerical payload validation.

## 2. Byte integrity

| Target | Extracted bytes | CRC32 | SHA256 | Archive-member match | HDF5 open |
|---|---:|---|---|---|---|
| ES10.mat | 1,209,388,987 | e8da00c5 | dc6d527433c6ce1ec5388b1a6a6c66b5601bbf695ba7ecefd80029b98dfa18db | exact size + CRC32 + streamed SHA256 | passed |
| ES12.mat | 1,863,271,598 | 2e07ccad | 18109558c6df7cafcba50a71b774367c887b331a09cf8b99ddcef2ddeb3e0a4a | exact size + CRC32 + streamed SHA256 | passed |
| ES14.mat | 2,094,950,842 | cb72c72a | 2d926d4eb7e01e16a8711b98517a69eb98a53b811df5c65db36da584f9f40a90 | exact size + CRC32 + streamed SHA256 | passed |

The ZIP member CRC check passed, all three extracted files exactly match their streamed archive-member SHA256, and all three open as HDF5. The archive SHA256 is 2e998398a956604c39b4a83146455282886b9d2e80edecd94fe90e565638ad98. Byte integrity passed; semantic correctness did not thereby pass.

## 3. Automated HDF5 inventory

| File | Objects | Datasets | Groups including root | Reference-dtype datasets | Semantic quarantine |
|---|---:|---:|---:|---:|---:|
| ES10.mat | 8,076 | 8,048 | 28 | 1,193 | 41 |
| ES12.mat | 7,959 | 7,930 | 29 | 1,193 | 43 |
| ES14.mat | 7,983 | 7,954 | 29 | 1,193 | 43 |
| Total | **24,018** | **23,932** | **86** | **3,579** | **127** |

MATLAB classes counted by the audit are 3 canonical-empty, 3,507 cell, 11,466 char, 8,884 double and 80 struct objects. No external-storage or virtual datasets were found. All 127 quarantine entries have reason unknown_semantics: path tokens were deliberately not accepted as frozen physical-field mappings.

The object inventory proves readability and structure. It does not prove finite values, unit correctness, monotonicity, frequency-grid consistency, sensor calibration or target validity because zero numeric rows were scanned.

## 4. Unit and modality findings

The internal paths encode 24 provisional EIS trajectory labels: ES10C1–C8, ES12C1–C8 and ES14C1–C8. Only 23 have transient data because ES10C8 is absent from Transient_Data.

These are provisional labels, not proven independent physical capacitors. Headers contain Cap #1..#8-style paths, but the files expose no frozen device serial, board, batch or replacement mapping. The unit ledger therefore marks identity as inferred label-only and physical independence as unknown.

Transient shapes are:

| Condition | Serial_Date | VL/VO availability and shape | Status |
|---|---:|---|---|
| ES10 | [75826,1] | C1–C7 each [75826,400]; C8 absent | aligned by shape for present channels; numeric quality unscanned |
| ES12 | [77241,1] | C1–C8 each [77237,400] | **blocked: Serial_Date is longer by 4** |
| ES14 | [77241,1] | C1–C8 each [77241,400] | aligned by shape; numeric quality unscanned |

ES12 must not be silently repaired by taking the minimum length. The extra four timestamps require explicit location and alignment evidence, followed by a frozen repair rule and quarantine record.

A sparse scalar check of VO[0,100] across all available transient channels clustered around 10, 12 and 14 for ES10, ES12 and ES14. This is high-confidence evidence for nominal voltage conditions, but it remains inferred because VO has no explicit unit attribute and the payload was not fully scanned.

## 5. EIS hierarchy, columns and ordering

Every provisional unit has Header, Data and ColumNames outer reference arrays of shape [73,1]. Header and Data inner cell shapes match for all 1,752 unit-event combinations. Across those events the reference probe counted 2,981 + 2,921 + 2,933 = **8,835 nonempty EIS replicate matrices**. Replicate counts vary from event to event, so event-to-replicate nesting must be retained.

Typical first-nonempty matrix metadata is [18,59] in h5py; one inspected ES10C5 first matrix is [18,58]. The probe did not inspect every replicate matrix shape or numerical content.

ColumNames decodes to 20 raw tokens including Cs/µF, Cp/µF and Re(Z)/Ohm. Merging cycle + number and I + Range yields an inferred 18-column map consistent with the numeric matrix dimension. This merge is not yet a frozen proven mapping and requires a parser schema test.

The cell order is not chronological. In ES10C1 event 0, Test 10–15 timestamps precede Test 1–9 in the reference order even though the latter were acquired earlier. A compliant parser must:

1. pair Header and Data by replicate index;
2. parse Acquisition started on from the paired header;
3. derive causal availability conservatively;
4. sort paired replicates by parsed time;
5. never feed raw path, filename, condition label, capacitor label or HDF5 reference name into a model.

The three small EIS Reference Tables are token-for-token equal and span 73 scheduled events. This proves a shared schedule, not duplicated trajectories or shared physical devices. The unnamed fourth row is elapsed-like but its unit is unknown.

## 6. Duplicate-audit boundary

Within each file, the probe resolved nonempty EIS Data references to HDF5 target paths. It found no target-object reuse among 2,981 ES10, 2,921 ES12 and 2,933 ES14 inspected references. This excludes only the narrow case where multiple inspected slots point to the same HDF5 object.

Not assessed:

- equal-valued matrices stored as different objects;
- tolerance-level near duplicates;
- copied or overlapping trajectories across files;
- transient content duplication;
- reuse or replacement of physical capacitors;
- duplicate groups suitable for split enforcement.

Accordingly DUPLICATE_AUDIT_LEDGER.csv deliberately assigns no duplicate_group_id. No independence claim may be based on the internal reference result alone.

## 7. Termination, censoring and target definitions

No named failure, termination, status, SOH, RUL, capacity-target or ESR-target path was found in the audited schema. Sequence end is not evidence of EOL. It may reflect failure, planned termination, acquisition loss or an administrative endpoint; the files do not decide among them.

For all 24 provisional labels:

- termination event: unknown;
- termination reason: unknown;
- censoring class: unknown; even right-censoring is not yet proven;
- capacity and ESR failure thresholds: not frozen;
- SOH definition: not frozen;
- RUL label: not identifiable from sequence end;
- Benchmark L / RUL status: blocked.

TERMINATION_LEDGER.csv records this separately for every provisional trajectory so that no downstream code can silently promote a last observation to failure.

## 8. Data Gate by target

| Target or use | Gate | What is proven | Missing before release |
|---|---|---|---|
| Byte integrity | PASS | CRC32, size, streamed SHA256 and HDF5 readability | none for byte identity |
| Schema/parser development | CONDITIONAL | object hierarchy, shapes, references and provisional labels | frozen semantic mapping; parser tests; numeric scan |
| Transient VL/VO forecasting | AMBER / not released | 23 labeled trajectories and shapes | physical semantics, units, NaN/gap scan; ES12 alignment |
| EIS Cs/Cp capacity candidate | AMBER / not released | column tokens and longitudinal event structure | frozen frequency/fit rule, replicate aggregation, units and numeric validation |
| ESR | RED / blocked | Re(Z) token exists | direct ESR absent; freeze intercept or circuit-fit definition and failure handling |
| SOH | RED / blocked | none | baseline, formula, threshold and physical validation |
| RUL / Benchmark L | **RED / blocked** | none | defensible failure/censor labels, termination reason, threshold and interval construction |
| LOCO claim | AMBER / provisional only | 24 path labels | physical identity and duplicate audit |
| Cross-condition claim | AMBER / provisional only | high-confidence inferred nominal 10/12/14 condition | batch/identity confounds and cross-file content audit |

Overall status remains partial_integrity_only. Benchmark L and all RUL claims are not released.

## 9. Required next steps

1. Freeze the parser contract and 18-column merge test without using path tokens as physical proof.
2. Run bounded chunked numeric audit for finite values, shape grid, frequency consistency, time gaps and NaN padding.
3. Resolve ES12 off-by-4 with explicit alignment evidence and a versioned repair ledger.
4. Run content-level within-file and cross-file duplicate signatures plus tolerance-aware trajectory checks.
5. Obtain or defensibly derive physical-unit identity and replacement information.
6. Freeze a capacity extraction rule using training units only; separately freeze ESR if scientifically justified.
7. Keep SOH/RUL disabled until failure/termination/censor labels are independently supported.
8. Only after these gates pass may a frozen rolling replay and LOCO/cross-condition evaluation be instantiated.

## 10. Companion ledgers

- UNIT_LEDGER.csv: 24 provisional labels and modality availability.
- MODALITY_SCHEMA_LEDGER.csv: structural versus semantic status by modality.
- TERMINATION_LEDGER.csv: per-trajectory termination and RUL blockage.
- DUPLICATE_AUDIT_LEDGER.csv: exact scope of completed and uncompleted duplicate checks.

This report intentionally makes no accuracy claim, no failure-time claim and no assertion that 24 labels are 24 independent physical devices.
