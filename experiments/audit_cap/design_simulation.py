#!/usr/bin/env python3
"""Frozen trajectory-comparison design simulation for AUDIT-Cap B1.

This executable is the quick trajectory slice only.  It validates the
unit-level paired decision machinery; it cannot pass the Design Gate and it
does not simulate RUL when the termination/outcome gate is unresolved.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import scipy
from scipy.stats import beta, t

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from experiments.audit_cap.ledger import sha256_file, write_sealed_ledger
from experiments.audit_cap.replay import package_code_hash

ALPHA_FAMILY = 0.04
CI_LEVEL = 0.95
MIN_CONFIRMATORY_UNITS = 12
TARGET_EFFECT = 0.10
GLOBAL_SEED = 20260813


@dataclass(frozen=True)
class TrajectoryScenario:
    scenario_id: str
    n_units: int
    mean_origins: int
    icc: float
    phi: float
    residual_paired_correlation: float
    availability: float
    length_cv: float
    n_candidates: int
    role: str


def quick_scenarios() -> list[TrajectoryScenario]:
    common = dict(icc=0.4, phi=0.6, residual_paired_correlation=0.8, availability=0.9, length_cv=0.5)
    return [
        TrajectoryScenario("QT0_h1", 6, 7, 0.4, 0.6, 0.8, 1.0, 0.0, 1, "stress2_h1"),
        TrajectoryScenario("QT0_h2", 6, 6, 0.4, 0.6, 0.8, 1.0, 0.0, 1, "stress2_h2"),
        TrajectoryScenario("QT0_h3", 6, 5, 0.4, 0.6, 0.8, 1.0, 0.0, 1, "stress2_h3"),
        TrajectoryScenario("QT1", 12, 25, n_candidates=1, role="reference", **common),
        TrajectoryScenario("QT2", 6, 7, 0.7, 0.9, 0.3, 0.7, 0.5, 1, "hard_small_n"),
        TrajectoryScenario("QT3", 12, 25, n_candidates=5, role="multiple_candidates", **common),
    ]


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def loss_array_json(value: np.ndarray) -> str:
    """Canonical raw-loss record with non-finite values represented as null."""

    array = np.asarray(value, dtype=np.float64)
    payload = np.where(np.isfinite(array), array, None).tolist()
    return canonical_json(payload)


def seed_for(global_seed: int, cell: dict[str, object], repeat: int) -> int:
    payload = canonical_json({"global_seed": global_seed, "cell": cell, "repeat": repeat}).encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big", signed=False)


def clopper_pearson(successes: int, trials: int, level: float = CI_LEVEL) -> tuple[float, float]:
    if trials <= 0 or successes < 0 or successes > trials:
        raise ValueError("invalid binomial counts")
    alpha = 1.0 - level
    lower = 0.0 if successes == 0 else float(beta.ppf(alpha / 2.0, successes, trials - successes + 1))
    upper = 1.0 if successes == trials else float(beta.ppf(1.0 - alpha / 2.0, successes + 1, trials - successes))
    return lower, upper


def paired_t_summary(differences: np.ndarray) -> tuple[float, float, float, float]:
    values = np.asarray(differences, dtype=np.float64)
    if values.ndim != 1 or values.size < 2 or not np.all(np.isfinite(values)):
        raise ValueError("paired differences must be finite with at least two units")
    mean = float(np.mean(values))
    standard_error = float(np.std(values, ddof=1) / math.sqrt(values.size))
    if standard_error == 0.0:
        p_one_sided = 0.0 if mean > 0.0 else 1.0
        return mean, p_one_sided, mean, mean
    statistic = mean / standard_error
    p_one_sided = float(t.sf(statistic, df=values.size - 1))
    half_width = float(t.ppf(0.5 + CI_LEVEL / 2.0, df=values.size - 1) * standard_error)
    return mean, p_one_sided, mean - half_width, mean + half_width


def holm_rejections(p_values: Iterable[float], alpha: float = ALPHA_FAMILY) -> np.ndarray:
    p = np.asarray(list(p_values), dtype=np.float64)
    order = np.argsort(p, kind="stable")
    rejected = np.zeros(p.size, dtype=bool)
    for rank, index in enumerate(order):
        threshold = alpha / (p.size - rank)
        if p[index] <= threshold:
            rejected[index] = True
        else:
            break
    return rejected


def _unit_lengths(rng: np.random.Generator, scenario: TrajectoryScenario) -> np.ndarray:
    if scenario.length_cv == 0.0:
        return np.full(scenario.n_units, scenario.mean_origins, dtype=int)
    sigma = math.sqrt(math.log1p(scenario.length_cv**2))
    mean_log = math.log(scenario.mean_origins) - 0.5 * sigma**2
    lengths = np.rint(rng.lognormal(mean_log, sigma, size=scenario.n_units)).astype(int)
    return np.clip(lengths, 2, 200)


def generate_unit_losses(
    rng: np.random.Generator,
    scenario: TrajectoryScenario,
    primary_effect: float,
) -> tuple[np.ndarray, np.ndarray, int]:
    """Return incumbent loss N-vector and K candidate loss matrix.

    Candidate zero is assigned ``primary_effect``; all remaining candidates
    are null.  Every model shares the same unit/time difficulty and mask.
    """

    if not (-0.5 < primary_effect < 1.0):
        raise ValueError("effect outside supported range")
    if not (0.0 <= scenario.icc < 1.0 and abs(scenario.phi) < 1.0):
        raise ValueError("invalid correlation parameters")
    if not (0.0 <= scenario.residual_paired_correlation <= 1.0 and 0.0 < scenario.availability <= 1.0):
        raise ValueError("invalid pairing or availability")

    tau_b = math.sqrt(scenario.icc)
    remainder = 1.0 - scenario.icc
    tau_u = math.sqrt(remainder / 2.0)
    sigma = math.sqrt(remainder / 2.0)
    rho = scenario.residual_paired_correlation
    effects = np.zeros(scenario.n_candidates, dtype=np.float64)
    effects[0] = primary_effect
    deltas = -np.log1p(-effects)
    lengths = _unit_lengths(rng, scenario)
    incumbent = np.empty(scenario.n_units, dtype=np.float64)
    candidates = np.empty((scenario.n_units, scenario.n_candidates), dtype=np.float64)
    availability_failures = 0

    for unit, length in enumerate(lengths):
        b = tau_b * rng.normal()
        innovations = rng.normal(size=length)
        ar = np.empty(length, dtype=np.float64)
        ar[0] = innovations[0]
        innovation_scale = math.sqrt(1.0 - scenario.phi**2)
        for index in range(1, length):
            ar[index] = scenario.phi * ar[index - 1] + innovation_scale * innovations[index]
        shared_log = b + tau_u * ar
        common = rng.normal(size=length)
        incumbent_noise = math.sqrt(rho) * common + math.sqrt(1.0 - rho) * rng.normal(size=length)
        incumbent_errors = np.exp(shared_log + sigma * incumbent_noise)
        candidate_errors = np.empty((scenario.n_candidates, length), dtype=np.float64)
        for candidate in range(scenario.n_candidates):
            candidate_noise = math.sqrt(rho) * common + math.sqrt(1.0 - rho) * rng.normal(size=length)
            candidate_errors[candidate] = np.exp(shared_log - deltas[candidate] + sigma * candidate_noise)
        observed = rng.random(length) < scenario.availability
        if not np.any(observed):
            incumbent[unit] = np.nan
            candidates[unit] = np.nan
            availability_failures += 1
        else:
            incumbent[unit] = float(np.mean(incumbent_errors[observed]))
            candidates[unit] = np.mean(candidate_errors[:, observed], axis=1)
    return incumbent, candidates, availability_failures


def decide_losses(
    incumbent: np.ndarray,
    candidates: np.ndarray,
    scenario: TrajectoryScenario,
) -> dict[str, object]:
    """Truth-blind candidate decision from unit-level loss arrays only."""

    if candidates.shape != (incumbent.size, scenario.n_candidates):
        raise ValueError("candidate loss shape mismatch")
    if not np.all(np.isfinite(incumbent)) or not np.all(np.isfinite(candidates)):
        return {
            "analysis_status": "FAIL_NO_MATURE_ORIGIN",
            "effect_estimate": np.nan,
            "primary_difference_mean": np.nan,
            "primary_difference_ci_lower": np.nan,
            "primary_difference_ci_upper": np.nan,
            "primary_p_one_sided": np.nan,
            "realized_unit_loss_correlation": np.nan,
            "selected_candidate": None,
            "promoted_any": False,
            "unit_count_meets_minimum_only": scenario.n_units >= MIN_CONFIRMATORY_UNITS,
        }
    p_values: list[float] = []
    means: list[float] = []
    intervals: list[tuple[float, float]] = []
    for candidate in range(scenario.n_candidates):
        mean, p_value, lower, upper = paired_t_summary(incumbent - candidates[:, candidate])
        means.append(mean)
        p_values.append(p_value)
        intervals.append((lower, upper))
    rejected = holm_rejections(p_values)
    mean_candidate_losses = np.mean(candidates, axis=0)
    passing = np.flatnonzero(rejected)
    selected: int | None = None
    if passing.size == 1:
        selected = int(passing[0])
    elif passing.size > 1:
        winner = int(passing[np.argmin(mean_candidate_losses[passing])])
        runner_pool = [int(index) for index in passing if int(index) != winner]
        runner = min(runner_pool, key=lambda index: mean_candidate_losses[index])
        _, runner_p, _, _ = paired_t_summary(candidates[:, runner] - candidates[:, winner])
        if runner_p <= ALPHA_FAMILY:
            selected = winner
    estimate = 1.0 - float(mean_candidate_losses[0] / np.mean(incumbent))
    if float(np.std(incumbent)) == 0.0 or float(np.std(candidates[:, 0])) == 0.0:
        realized_correlation = np.nan
    else:
        realized_correlation = float(np.corrcoef(incumbent, candidates[:, 0])[0, 1])
    lower, upper = intervals[0]
    return {
        "analysis_status": "OK",
        "effect_estimate": estimate,
        "primary_difference_mean": means[0],
        "primary_difference_ci_lower": lower,
        "primary_difference_ci_upper": upper,
        "primary_p_one_sided": p_values[0],
        "realized_unit_loss_correlation": realized_correlation,
        "selected_candidate": selected,
        "promoted_any": selected is not None,
        "unit_count_meets_minimum_only": scenario.n_units >= MIN_CONFIRMATORY_UNITS,
    }


def score_simulation_decision(
    decision: dict[str, object], true_effect: float
) -> dict[str, object]:
    """Attach truth-aware simulation diagnostics after the decision is frozen."""

    if decision["analysis_status"] != "OK":
        return {
            "analysis_status": decision["analysis_status"],
            "effect_estimate": decision["effect_estimate"],
            "effect_bias": np.nan,
            "primary_difference_mean": decision["primary_difference_mean"],
            "primary_difference_ci_lower": decision["primary_difference_ci_lower"],
            "primary_difference_ci_upper": decision["primary_difference_ci_upper"],
            "primary_difference_ci_covers_truth": False,
            "primary_p_one_sided": decision["primary_p_one_sided"],
            "realized_unit_loss_correlation": decision["realized_unit_loss_correlation"],
            "selected_candidate": decision["selected_candidate"],
            "promoted_any": decision["promoted_any"],
            "correct_champion": False,
            "no_champion": False,
            "unit_count_meets_minimum_only": decision["unit_count_meets_minimum_only"],
        }
    expected_incumbent_mean = math.exp(0.5)
    true_difference = true_effect * expected_incumbent_mean
    selected = decision["selected_candidate"]
    estimate = float(decision["effect_estimate"])
    lower = float(decision["primary_difference_ci_lower"])
    upper = float(decision["primary_difference_ci_upper"])
    return {
        "analysis_status": decision["analysis_status"],
        "effect_estimate": estimate,
        "effect_bias": estimate - true_effect,
        "primary_difference_mean": decision["primary_difference_mean"],
        "primary_difference_ci_lower": lower,
        "primary_difference_ci_upper": upper,
        "primary_difference_ci_covers_truth": lower <= true_difference <= upper,
        "primary_p_one_sided": decision["primary_p_one_sided"],
        "realized_unit_loss_correlation": decision["realized_unit_loss_correlation"],
        "selected_candidate": selected,
        "promoted_any": decision["promoted_any"],
        "correct_champion": selected == 0 if true_effect > 0.0 else selected is None,
        "no_champion": selected is None,
        "unit_count_meets_minimum_only": decision["unit_count_meets_minimum_only"],
    }


def quick_cells(repeats: int) -> list[dict[str, object]]:
    cells: list[dict[str, object]] = []
    for scenario in quick_scenarios():
        for effect in (0.0, TARGET_EFFECT):
            cells.append({"scenario": asdict(scenario), "effect": effect, "repeats": repeats})
        if scenario.scenario_id.startswith("QT0_"):
            cells.append({"scenario": asdict(scenario), "effect": -0.05, "repeats": repeats})
    return cells


def run_quick(repeats: int, global_seed: int = GLOBAL_SEED) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    repeat_rows: list[dict[str, object]] = []
    cell_rows: list[dict[str, object]] = []
    cells = quick_cells(repeats)
    for cell in cells:
        scenario = TrajectoryScenario(**cell["scenario"])
        effect = float(cell["effect"])
        seed_key = {"scenario": cell["scenario"], "effect": effect}
        cell_manifest = {**seed_key, "repeats": repeats}
        cell_hash = hashlib.sha256(canonical_json(cell_manifest).encode()).hexdigest()
        local_rows: list[dict[str, object]] = []
        for repeat in range(repeats):
            seed = seed_for(global_seed, seed_key, repeat)
            rng = np.random.default_rng(seed)
            incumbent, candidates, availability_failures = generate_unit_losses(rng, scenario, effect)
            decision = decide_losses(incumbent, candidates, scenario)
            analysis = score_simulation_decision(decision, effect)
            row = {
                "cell_hash": cell_hash,
                "scenario_id": scenario.scenario_id,
                "effect": effect,
                "repeat": repeat,
                "seed": seed,
                "availability_failure_units": availability_failures,
                "incumbent_unit_losses_json": loss_array_json(incumbent),
                "candidate_unit_losses_json": loss_array_json(candidates),
                **analysis,
            }
            local_rows.append(row)
            repeat_rows.append(row)
        local = pd.DataFrame(local_rows)
        failed = int((local.analysis_status != "OK").sum())
        promoted = int(local.promoted_any.sum())
        correct = int(local.correct_champion.sum())
        no_champion = int(local.no_champion.sum())
        coverage = int(local.primary_difference_ci_covers_truth.sum())
        promoted_ci = clopper_pearson(promoted, repeats)
        correct_ci = clopper_pearson(correct, repeats)
        no_champion_ci = clopper_pearson(no_champion, repeats)
        coverage_ci = clopper_pearson(coverage, repeats)
        cell_rows.append(
            {
                "cell_hash": cell_hash,
                "scenario_id": scenario.scenario_id,
                "scenario_json": canonical_json(asdict(scenario)),
                "effect": effect,
                "repeats": repeats,
                "unit_count_meets_minimum_only": scenario.n_units >= MIN_CONFIRMATORY_UNITS,
                "analyzable_repeats": repeats - failed,
                "failed_repeats": failed,
                "promotion_rate": promoted / repeats,
                "promotion_ci_lower": promoted_ci[0],
                "promotion_ci_upper": promoted_ci[1],
                "correct_champion_rate": correct / repeats,
                "correct_champion_ci_lower": correct_ci[0],
                "correct_champion_ci_upper": correct_ci[1],
                "no_champion_rate": no_champion / repeats,
                "no_champion_ci_lower": no_champion_ci[0],
                "no_champion_ci_upper": no_champion_ci[1],
                "comparison_ci_coverage": coverage / repeats,
                "comparison_ci_coverage_cp_lower": coverage_ci[0],
                "comparison_ci_coverage_cp_upper": coverage_ci[1],
                "mean_effect_estimate_analyzable_only": float(local.effect_estimate.mean(skipna=True)),
                "mean_effect_bias_analyzable_only": float(local.effect_bias.mean(skipna=True)),
                "mean_realized_unit_loss_correlation_analyzable_only": float(
                    local.realized_unit_loss_correlation.mean(skipna=True)
                ),
                "cell_execution_status": "OK" if failed == 0 else "FAIL_EXPLICIT_MISSINGNESS",
                "gate_status": "NOT_ELIGIBLE_QUICK_SANITY",
            }
        )
    summary = {
        "schema_version": "audit-cap.design-trajectory.v1",
        "mode": "quick_trajectory_only",
        "global_seed": global_seed,
        "alpha_family": ALPHA_FAMILY,
        "ci_level": CI_LEVEL,
        "target_effect": TARGET_EFFECT,
        "minimum_confirmatory_units": MIN_CONFIRMATORY_UNITS,
        "cell_count": len(cells),
        "repeat_count": int(len(repeat_rows)),
        "failed_repeat_count": int(sum(row["analysis_status"] != "OK" for row in repeat_rows)),
        "design_gate": "NOT_EVALUATED_QUICK_SANITY",
        "rul_module": "NA_outcome_and_termination_gate_unresolved",
        "interpretation": "Implementation sanity only; no superiority or Design Gate claim is permitted.",
    }
    return pd.DataFrame(repeat_rows), pd.DataFrame(cell_rows), summary


def _write_csv(path: Path, frame: pd.DataFrame) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(temporary, index=False, float_format="%.17g", lineterminator="\n")
    os.replace(temporary, path)


def _write_json(path: Path, payload: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=200)
    parser.add_argument("--seed", type=int, default=GLOBAL_SEED)
    args = parser.parse_args()
    if args.repeats < 1:
        raise SystemExit("--repeats must be positive")
    if args.output_dir.exists() or args.output_dir.is_symlink():
        raise SystemExit(f"append-only output directory must not already exist: {args.output_dir}")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    protocol_hash = sha256_file(args.protocol)
    code_hash = package_code_hash(Path(__file__).resolve().parent)
    run_lineage = {
        "schema_version": "audit-cap.design-trajectory.v2",
        "code_hash": code_hash,
        "protocol_path": str(args.protocol.resolve()),
        "protocol_hash": protocol_hash,
        "global_seed": args.seed,
        "repeats_per_cell": args.repeats,
        "mode": "quick_trajectory_only",
        "labels": "synthetic_ground_truth",
    }
    repeats, cells, summary = run_quick(args.repeats, args.seed)
    _, repeat_seal = write_sealed_ledger(
        args.output_dir / "DESIGN_REPEAT_LEDGER.csv",
        repeats,
        args.output_dir / "DESIGN_REPEAT_SEAL.json",
        run_lineage,
        seal_status="SEALED_AFTER_SYNTHETIC_ANALYSIS_BEFORE_REPORTING",
    )
    _, cell_seal = write_sealed_ledger(
        args.output_dir / "DESIGN_CELL_SUMMARY.csv",
        cells,
        args.output_dir / "DESIGN_CELL_SEAL.json",
        {**run_lineage, "repeat_ledger_sha256": repeat_seal["ledger_sha256"]},
        seal_status="SEALED_AFTER_SYNTHETIC_ANALYSIS_BEFORE_REPORTING",
    )
    summary["schema_version"] = run_lineage["schema_version"]
    summary["code_hash"] = code_hash
    summary["protocol_path"] = run_lineage["protocol_path"]
    summary["protocol_hash"] = protocol_hash
    summary["command"] = " ".join(sys.argv)
    summary["python"] = sys.version
    summary["platform"] = platform.platform()
    summary["dependencies"] = {
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "scipy": scipy.__version__,
    }
    summary["thread_environment"] = {
        key: os.environ.get(key)
        for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")
    }
    summary["repeat_ledger_seal"] = repeat_seal
    summary["cell_ledger_seal"] = cell_seal
    _write_json(args.output_dir / "DESIGN_SIM_SUMMARY.json", summary)
    artifact_manifest = {
        path.name: {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
        for path in sorted(args.output_dir.iterdir())
        if path.is_file()
    }
    manifest_path = args.output_dir / "RUN_MANIFEST.json"
    _write_json(
        manifest_path,
        {
            "artifacts": artifact_manifest,
            "lineage": run_lineage,
            "command": summary["command"],
            "dependencies": summary["dependencies"],
            "platform": summary["platform"],
            "python": summary["python"],
            "thread_environment": summary["thread_environment"],
        },
    )
    _write_json(
        args.output_dir / "COMPLETE",
        {
            "status": "COMPLETE",
            "run_manifest_sha256": sha256_file(manifest_path),
            "repeat_seal_sha256": sha256_file(args.output_dir / "DESIGN_REPEAT_SEAL.json"),
            "cell_seal_sha256": sha256_file(args.output_dir / "DESIGN_CELL_SEAL.json"),
            "code_hash": code_hash,
            "protocol_hash": protocol_hash,
            "completed_utc": datetime.now(timezone.utc).isoformat(),
            "design_gate": summary["design_gate"],
        },
    )
    print(canonical_json(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
