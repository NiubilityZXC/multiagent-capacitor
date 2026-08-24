# Public capacitor dataset expansion gate

**Frozen at:** 2026-08-24 14:15:04 CST  
**Scope:** Source-level evidence already verified for Ren et al. (Figshare 11522082), Patrizi et al. (Figshare 29153561), Warwick WRAP 195190, and the current near-miss set.  
**Execution status:** Metadata/landing-page audit only. The multi-GB payloads below have **not** been downloaded, extracted, parsed, or used for a model result in this run.

## 1. Decision semantics

- **PASS** means that a public landing page, a reproducible download route, and an explicit reuse licence have been identified, and that the source is eligible to enter a separately approved raw-data audit. It does **not** mean that every target (capacitance, ESR, SOH, or RUL) is native or valid.
- **AMBER** means that the source may support an auxiliary or restricted benchmark, but its target semantics, event provenance, cohort completeness, or domain match prevents use as a primary benchmark without an additional gate.
- **RED** means ineligible for the frozen benchmark at present. RED is a statement about current evidence, not a claim that the source can never become usable.

No paper description, author script, inferred threshold, or extrapolated endpoint is accepted as row-level ground truth until it agrees with the downloaded records and a frozen parser audit.

## 2. Source-level disposition

| Source | Current gate | Public and licence evidence | Cohort/workload known before download | Eligible role | Blocking limitation |
|---|---|---|---|---|---|
| Ren et al., **SCs**, Figshare item [11522082](https://figshare.com/articles/dataset/SCs/11522082) | **PASS — acquisition only** | Figshare API v1 reports CC BY 4.0 and DOI `10.6084/m9.figshare.11522082.v1`. Direct payload: [raw.rar](https://ndownloader.figshare.com/files/20691603), 2,114,703,017 bytes, published MD5 `26a7a663217c59377c83fb2a8274466b`. Author code: [GlimmerR/SCs](https://github.com/GlimmerR/SCs). | 113 real commercial Eaton HV 1 F/2.7 V carbon EDLCs in four batches, up to 10,000 cycles; 28 °C; 88 cells under constant 20 mA operation and 25 with stepped charging/20 mA discharge. Excel records are described as including voltage, current, time, mAh, and mWh. | Primary candidate for cross-capacitor capacitance/retention forecasting after Data Gate. | No native ESR/EIS; no audited physical-failure label; RUL requires a separately frozen threshold and censoring policy. Several papers reporting 60/84/88/113 cells appear to reuse subsets of this same fleet and cannot be counted as independent datasets. |
| Patrizi et al., accelerated ageing of hybrid supercapacitors, Figshare item [29153561](https://figshare.com/articles/dataset/Study_of_Accelerated_Ageing_Effects_on_Hybrid_Supercapacitors_Under_Different_Fast-Charging_Strategies/29153561) | **PASS — acquisition only; separate domain** | Figshare API v2 reports CC BY 4.0 and DOI `10.6084/m9.figshare.29153561.v2`. Direct payloads: [`Dataset_HSC.mat`](https://ndownloader.figshare.com/files/54852761), 225,986,697 bytes, MD5 `57e71c60cbae63142db44559edfa8ae0`; [information PDF](https://ndownloader.figshare.com/files/55269047), 397,625 bytes, MD5 `0189a89a72c73080cece2104ba834bce`. | Eight real 4.2 V hybrid supercapacitors, one unit for each fast-charge strategy; 20 °C, 40% RH, 4 A discharge. Described fields include time, cycle, current, voltage, `Cap_ch`, `Cap_dis`, IR, temperature, method, per-cycle summaries, and 61-point EIS sweeps from 100 mHz to 100 kHz every 25 cycles. Tests are described as terminating below 70% capacity. | Separate HSC external/domain benchmark; possible capacity-retention, IR, EIS-derived features, and protocol-EOL audit. | One unit per strategy makes device identity perfectly confounded with charging strategy. It cannot establish a causal strategy effect or within-condition generalization. `Cap_ch`/`Cap_dis` are Ah quantities, not electrostatic capacitance in farads. |
| Warwick supercapacitor energy-storage dataset, WRAP [195190](https://wrap.warwick.ac.uk/id/eprint/195190/) | **AMBER** | WRAP reports CC BY 4.0. Direct payload: [mjk-sc-ess-dataset.zip](https://wrap.warwick.ac.uk/id/eprint/195190/1/mjk-sc-ess-dataset.zip). Exact payload bytes and digest are not yet frozen in this run. | Twelve units are reported, but only six are described as having full trajectories of roughly 66k–100k points. | Auxiliary energy-trajectory, anomaly, or representation stress test only. | The native outcome is energy rather than capacitance or ESR. Multiple EOL values are described as extrapolated; extrapolated endpoints must not be treated as observed failures or primary RUL truth. Cohort completeness must be checked after download. |
| 2026 *Scientific Reports* aluminium-electrolytic-capacitor ageing source currently pointing to a three-unit Google Drive payload | **RED — current evidence** | A data route was encountered, but no explicit reusable data licence, immutable file manifest, digest, or frozen landing/direct URL has yet been established in this run. | Three units reported. Raw fields and endpoint provenance have not passed an independent source audit. | None in the frozen benchmark. May be reconsidered if provenance and licence are resolved. | Unclear data reuse rights, very small cohort, non-immutable delivery, and unverified schema/EOL semantics. It must not be represented as a public reproducible benchmark yet. |

**Domain rule:** EDLC, hybrid-supercapacitor, aluminium-electrolytic, and film-capacitor records are not pooled as exchangeable samples. Each chemistry/construction receives its own reference value, threshold policy, feature availability mask, and reported result. Cross-domain transfer, if attempted later, is an explicitly labelled stress test rather than ordinary test-set accuracy.

## 3. Native versus derived targets

| Quantity | Ren SCs | Patrizi HSC | Warwick | Frozen interpretation requirement |
|---|---|---|---|---|
| Voltage/current/time/cycle | Described as native row-level measurements; exact schema pending extraction | Described as native measurements and summaries; exact MAT structure pending extraction | Time/energy trajectory is the relevant native signal; exact schema pending extraction | Native status is accepted only after key/column/unit inspection and measurement chronology checks. |
| Capacitance in farads | **Not a listed native target.** May be derived from a qualifying constant-current segment, for example `C = |I| Δt / |ΔV|`, only after voltage bounds, IR-drop handling, sign, sampling, and aggregation are frozen. | `Cap_ch`/`Cap_dis` are reported in Ah and therefore are **not** capacitance in farads. A farad-valued target requires a defensible waveform derivation. | Not native. | Never rename charge capacity (Ah), stored energy (Wh/J), or a paper-level estimate as farad-valued capacitance. |
| ESR / internal resistance | No native ESR or EIS identified. ESR must be `NA`, not inferred from capacitance trends. | Native/summary IR and EIS are reported. IR is not automatically equivalent to ESR. An EIS-based ESR convention (for example, an audited high-frequency real-axis quantity) must be frozen with frequency selection and interpolation rules. | Not identified as native. | Measurement method and units are part of the target. IR, pulse resistance, DC resistance, and EIS ESR are not interchangeable labels. |
| SOH | Not native. Candidate `SOH_C(t)=C(t)/C_ref` is derived only after `C_ref`, stabilization period, and per-device normalization are frozen. | Capacity retention may be derived as an Ah ratio; it must be named capacity-SOH rather than farad-SOH unless a farad target is derived. IR-SOH, if used, is a separate endpoint. | Energy retention is a separate derived quantity, not capacitance-SOH. | Every SOH result must name its numerator, reference, unit, and whether larger or smaller is healthier. |
| EOL and RUL | No audited physical-failure field is known. A threshold crossing can define a **protocol EOL**, but not catastrophic physical failure. | The reported below-70%-capacity stop rule is a candidate protocol EOL, subject to row-level verification. It is not automatically a physical failure. | Extrapolated EOL values are not observed events. | `RUL(o)=τ_EOL-o` is defined only for a frozen time/cycle axis and EOL rule. Predictions at origin `o` use data available at or before `o`; unresolved or censored event time remains unavailable for ordinary point-error scoring. |

## 4. Event and right-censoring policy

1. **Observed physical failure** requires an explicit, auditable failure record. None of the newly identified sources is currently approved as providing that endpoint.
2. **Observed protocol EOL** is the first valid crossing of a predeclared threshold under a frozen smoothing, persistence, and missing-data rule. It must be reported as protocol-defined EOL, not physical failure.
3. **Right-censored unit:** if no qualifying crossing occurs before the final valid observation, record `(last_observation, event=0)`. Do not substitute the last cycle, an arbitrary maximum, an author-script default, or an extrapolated crossing as the true EOL.
4. **Ren script warning:** the associated workflow uses a 0.903 F crossing convention and has non-crossing behaviour that is unsuitable as benchmark truth. The project must reconstruct event/censor labels independently; the author script may be used only as a provenance reference.
5. **Patrizi stop-rule warning:** raw audit must distinguish “test stopped because the threshold was met” from “last recorded value happens to be near/below the threshold,” and must identify early truncation or missing terminal cycles.
6. **Warwick extrapolation warning:** extrapolated EOL may be evaluated only in a separately named weak-label sensitivity analysis. It is excluded from primary observed-RUL metrics.

Survival-aware or censor-aware metrics may later use censored units under a frozen estimand. Conventional RUL MAE/RMSE must not score a censored or extrapolated event time as exact truth.

## 5. Fleet identity and leakage controls

- The 113-cell Ren archive is one fleet. Publications or repositories using 60, 84, 88, or 113 of those cells are presumed overlapping until cell identifiers and raw hashes prove otherwise. They provide literature evidence, not additional independent test samples.
- Deduplication must operate on raw-file digest, device identity, batch, protocol, timestamp/cycle signatures, and waveform fingerprints before assigning folds.
- All windows/origins from one physical unit remain in a single outer fold. A sliding window does not create an independent capacitor.
- Preprocessing parameters, reference capacities, threshold tuning, feature selection, calibration, prompt/program search, routing policy selection, and ensemble weights must be fit inside training/inner-validation data only.
- For Ren, report leave-one-capacitor-out or a predeclared grouped alternative plus batch/protocol holdouts. The 25 stepped-charge devices must not leak into both train and a claimed held-out-condition test through overlapping identifiers or derived summaries.
- For Patrizi, leave-one-device-out is simultaneously leave-one-strategy-out. Results must be labelled confounded cross-strategy transfer; uncertainty across eight devices cannot be presented as replicated per-condition evidence.
- Dataset identity and future endpoint/censor status are forbidden prompt features during online replay unless the deployment scenario explicitly supplies them and the same information is available at inference time.

## 6. Proposed download and Data Gate (not yet approved or executed)

The next state-changing step requires a new human checkpoint. The previous authorization for another 5.04 GB package does not silently authorize these newly discovered files.

### Requested acquisition scope

1. Ren `raw.rar`: expected 2,114,703,017 bytes and MD5 `26a7a663217c59377c83fb2a8274466b`.
2. Patrizi `Dataset_HSC.mat`: expected 225,986,697 bytes and MD5 `57e71c60cbae63142db44559edfa8ae0`; information PDF: expected 397,625 bytes and MD5 `0189a89a72c73080cece2104ba834bce`.
3. Warwick ZIP only if the auxiliary energy benchmark is retained after primary-parser feasibility is established; first freeze its expected length and digest from authoritative metadata.

### Mandatory gates before any model or paid API call

- Save landing-page/licence snapshots and direct-URL provenance; verify byte length and published digest where available, then compute project SHA-256.
- Extract into ignored raw-data storage; produce a non-secret file manifest without committing the multi-GB payloads to Git.
- Run a reference-aware parser audit: exact device counts, identifiers, batch/protocol mapping, columns/keys, shapes, units, sampling/chronology, duplicates, missing/nonfinite values, and terminal-record integrity.
- Reconcile README/paper claims and author code with raw rows. Any disagreement is a blocking issue, not an inferred repair.
- Freeze farad/Ah/energy target definitions, reference values, EOL threshold/persistence rule, censor representation, eligible origins/horizons, and unavailable-target masks.
- Freeze grouped outer splits before feature, prompt, model, route, or AgentPolicy development. Preserve a final shadow fold that no agent, model selector, or human tuning loop may inspect.
- Run the numerical no-leakage baseline and deterministic replay checks before enabling direct-LLM or hybrid-agent forecasting. API availability does not waive the Data Gate.

## 7. Current decision

- **Admit to acquisition queue:** Ren SCs and Patrizi HSC, with separate schemas, targets, and result tables.
- **Retain as auxiliary AMBER:** Warwick energy trajectories; no primary capacitance/ESR/RUL claim.
- **Exclude for now:** the three-unit aluminium-electrolytic near-miss and any source without explicit licence, immutable provenance, and audited row-level endpoint semantics.
- **Do not claim yet:** downloaded data, parser success, usable RUL labels, cross-condition generalization, model accuracy, or API-agent benefit.

**Next human Gate:** approve or reject the bounded download/audit scope above. Until approval, no new payload is downloaded, no archive is extracted, and no numerical or LLM model is run on these sources.
