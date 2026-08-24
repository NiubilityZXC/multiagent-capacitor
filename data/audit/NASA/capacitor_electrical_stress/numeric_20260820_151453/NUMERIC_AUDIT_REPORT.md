# Numeric Scan Audit Report

- Audit directory: numeric_20260820_151453
- Inputs: HDF5_NUMERIC_SCAN.csv and AUDIT_SUMMARY.json
- Scan mode: numeric_scan; chunk size 16,777,216 bytes
- Verdict: partial numeric integrity only

> This scan does not pass the full Data Gate. Benchmark L and SOH/RUL remain blocked, and the ES12 off-by-4 alignment remains unresolved.

## 1. Exact scan scope

HDF5_NUMERIC_SCAN.csv contains exactly **23,932 dataset rows**, matching the audited dataset count. Statuses are:

- passed: **20,353** datasets;
- skipped_reference_dtype: **3,579** datasets;
- read_error: **0**;
- external-storage datasets: **0**;
- virtual datasets: **0**.

The passed datasets contain **1,465,967,459 scanned elements**:

- finite: 943,403,434 (64.353641%);
- NaN: **522,564,025 (35.646359%)**;
- +Inf / -Inf / total Inf: **0 / 0 / 0**.

For every one of the 20,353 passed datasets, scanned_element_count equals element_count. The 3,579 skipped reference arrays contain 24,764 reference elements that were not interpreted as numeric payload.

## 2. By source file

| Source | Rows | Passed | Ref skipped | Scanned elements | Finite | NaN | NaN ratio | Datasets with NaN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ES10.mat | 8,048 | 6,855 | 1,193 | 442,399,245 | 235,224,717 | 207,174,528 | 46.829765% | 14 |
| ES12.mat | 7,930 | 6,737 | 1,193 | 511,735,370 | 348,883,207 | 162,852,163 | 31.823511% | 16 |
| ES14.mat | 7,954 | 6,761 | 1,193 | 511,832,844 | 359,295,510 | 152,537,334 | 29.802178% | 16 |

Every dataset with at least one NaN is a named transient VL or VO dataset. No other passed dataset contains a NaN, and no passed dataset contains an infinity.

## 3. By path class

| Path class | Rows | Passed | Ref skipped | Scanned elements | Finite | NaN | NaN ratio |
|---|---:|---:|---:|---:|---:|---:|---:|
| Named transient VL/VO | 46 | 46 | 0 | 1,413,284,800 | 890,720,775 | 522,564,025 | 36.975139% |
| Named Serial_Date | 3 | 3 | 0 | 230,308 | 230,308 | 0 | 0.000000% |
| Named Initial_Date | 3 | 3 | 0 | 66 | 66 | 0 | 0.000000% |
| Independent numeric/char objects under /#refs# | 20,301 | 20,301 | 0 | 52,452,285 | 52,452,285 | 0 | 0.000000% |
| Reference arrays under /#refs# | 3,504 | 0 | 3,504 | 0 | 0 | 0 | n/a |
| Named reference arrays | 75 | 0 | 75 | 0 | 0 | 0 | n/a |

The named reference arrays are 25 per source file: EIS_Reference_Table plus Header, Data and ColumNames for eight provisional labels. Their links were skipped rather than numerically coerced.

## 4. Named transient NaN concentration

All **46 = 23 × 2** named transient VL/VO datasets contain NaN. Together they contain 522,564,025 NaNs, and every NaN found by the scan occurs in this class.

| Source / signal | Datasets | Elements | NaN | NaN ratio | Min–max NaN per dataset |
|---|---:|---:|---:|---:|---:|
| ES10 VL | 7 | 212,312,800 | 142,360,282 | 67.052143% | 13,389,797–27,520,273 |
| ES10 VO | 7 | 212,312,800 | 64,814,246 | 30.527715% | 9,258,933–9,259,349 |
| ES12 VL | 8 | 247,158,400 | 87,074,705 | 35.230324% | 9,635,254–11,775,215 |
| ES12 VO | 8 | 247,158,400 | 75,777,458 | 30.659471% | 9,472,035–9,472,346 |
| ES14 VL | 8 | 247,171,200 | 76,755,926 | 31.053750% | 9,472,421–10,447,029 |
| ES14 VO | 8 | 247,171,200 | 75,781,408 | 30.659481% | 9,472,574–9,472,753 |

The scan counts NaNs but does not classify their geometry. They may represent waveform padding, missing samples, acquisition loss or a mixture. No imputation, trimming or valid-length rule is justified yet. ES10 VL is especially heterogeneous and must not share a blind global mask with other conditions.

## 5. Top affected paths by NaN count

| Rank | Source | Path | Elements | NaN | NaN ratio |
|---:|---|---|---:|---:|---:|
| 1 | ES10.mat | /ES10/Transient_Data/ES10C4/VL | 30,330,400 | 27,520,273 | 90.734949% |
| 2 | ES10.mat | /ES10/Transient_Data/ES10C5/VL | 30,330,400 | 22,193,070 | 73.171043% |
| 3 | ES10.mat | /ES10/Transient_Data/ES10C3/VL | 30,330,400 | 21,520,065 | 70.952131% |
| 4 | ES10.mat | /ES10/Transient_Data/ES10C7/VL | 30,330,400 | 20,875,935 | 68.828420% |
| 5 | ES10.mat | /ES10/Transient_Data/ES10C6/VL | 30,330,400 | 18,885,733 | 62.266680% |
| 6 | ES10.mat | /ES10/Transient_Data/ES10C1/VL | 30,330,400 | 17,975,409 | 59.265321% |
| 7 | ES10.mat | /ES10/Transient_Data/ES10C2/VL | 30,330,400 | 13,389,797 | 44.146457% |
| 8 | ES12.mat | /ES12/Transient_Data/ES12C4/VL | 30,894,800 | 11,775,215 | 38.113906% |
| 9 | ES12.mat | /ES12/Transient_Data/ES12C2/VL | 30,894,800 | 11,577,263 | 37.473177% |
| 10 | ES12.mat | /ES12/Transient_Data/ES12C8/VL | 30,894,800 | 11,354,346 | 36.751641% |

The top seven paths are every ES10 VL channel; ES10C4/VL alone is 90.734949% NaN. Before any sliding-window model, a row-wise and waveform-position-wise missingness audit must determine causal valid masks and whether target points themselves are observable.

## 6. Reference-dtype boundary

The scan intentionally skipped 75 named and 3,504 internal reference arrays, totaling 24,764 reference elements.

Separately, 20,301 numeric or char datasets stored under /#refs# were scanned as independent objects, covering 52,452,285 elements; all passed and contained no NaN or Inf.

This does **not** prove:

- which outer Header/Data/ColumNames event reference maps to which scanned target object;
- that Header and Data linkage semantics are correct;
- that the inferred 20-token to 18-column EIS mapping is correct;
- that replicate ordering, event timing or physical units are correct;
- that every scanned /#refs# numeric object is an evaluation-eligible EIS matrix.

Those require an explicit reference-aware parser plus frozen schema tests. The numeric scan must not be described as a full matrix-mapping audit.

## 7. ES12 off-by-4 remains

Serial_Date itself scanned completely and contains no NaN, but its ES12 shape is still [77241,1] while every ES12 VL/VO array is [77237,400]. A finite timestamp is not evidence of correct alignment. The four-row discrepancy remains quarantined and no silent head/tail trim is permitted.

## 8. Data Gate impact

| Target or use | Status after numeric scan | Reason |
|---|---|---|
| Non-reference dataset readability | PASS for scanned scope | all 20,353 passed datasets fully scanned; no read errors or Inf |
| Named transient VL/VO | AMBER / not released | all 46 contain NaN; missingness geometry and valid masks unknown |
| ES12 transient | RED / alignment blocked | off-by-4 unresolved |
| EIS internal numeric objects | AMBER / semantic mapping blocked | independent targets scanned with no NaN/Inf, but reference linkage and column mapping unverified |
| Capacity Cs/Cp target | AMBER / not released | extraction frequency, fit and replicate aggregation still unfrozen |
| ESR | RED / blocked | no direct ESR target or frozen derivation |
| SOH and RUL / Benchmark L | **RED / blocked** | termination, censoring, failure thresholds and labels remain absent |

Overall status remains **partial_integrity_only**. Numeric finiteness does not supply physical semantics, independent unit identity, failure labels or RUL ground truth.

## 9. Required follow-up

1. Build a reference-aware parser and test event-to-replicate-to-matrix linkage without exposing path labels as model features.
2. Validate the inferred 18-column EIS mapping and frequency grids.
3. Audit transient NaN masks by row and waveform position; freeze exclusion or masking rules using training units only.
4. Resolve ES12 off-by-4 with explicit alignment evidence and a versioned repair ledger.
5. Re-run prefix-invariance and rolling-replay tests after masking/alignment rules are frozen.
6. Keep Benchmark L/RUL disabled until termination and censoring evidence exists.

Machine-readable mechanical aggregates are in NUMERIC_SCAN_SUMMARY.json.
