from __future__ import annotations

from dataclasses import FrozenInstanceError

import numpy as np
import pytest

from experiments.n0_plus.registry import build_n0_plus_registry
from experiments.n0_plus import sn1_synthetic_models
from experiments.n0_plus.sn1_synthetic_models import (
    IMPLEMENTED_CANDIDATES,
    QUANTILE_LEVELS,
    SN1_AUTHORITY,
    SN1ModelError,
    SyntheticCandidateState,
    fit_synthetic_candidate,
    predict_synthetic_candidate,
)


def _fleet() -> dict[str, np.ndarray]:
    time = np.arange(36, dtype=np.float64)
    return {
        "train-a": 1.00 - 0.0030 * time - 0.00004 * time * time,
        "train-b": 1.02 - 0.0025 * time - 0.00005 * time * time,
        "train-c": 0.98 - 0.0034 * time - 0.00003 * time * time,
    }


def _evaluation() -> np.ndarray:
    time = np.arange(36, dtype=np.float64)
    return 1.015 - 0.0027 * time - 0.000037 * time * time


def _fit(candidate_id: str, units: dict[str, np.ndarray] | None = None):
    return fit_synthetic_candidate(
        candidate_id,
        _fleet() if units is None else units,
        (1, 3, 5),
        seed=17,
        authority=SN1_AUTHORITY,
    )


@pytest.mark.parametrize(
    "candidate_id",
    (
        "online_ssm_rls_rels_trend",
        "online_ssm_robust_local_trend_pf",
        "small_ml_elastic_net_direct",
        "small_ml_hist_gradient_boosting_direct",
    ),
)
def test_nonclassical_candidates_return_complete_nested_forecasts(candidate_id: str) -> None:
    state = _fit(candidate_id)
    forecast = predict_synthetic_candidate(
        state,
        _evaluation()[:20],
        authority=SN1_AUTHORITY,
    )
    assert forecast.horizons == (1, 3, 5)
    assert len(forecast.points) == 3
    assert tuple(forecast.quantile_map) == QUANTILE_LEVELS
    assert np.all(np.diff(np.asarray(tuple(forecast.quantile_map.values())), axis=0) >= -1e-12)


@pytest.mark.parametrize("candidate_id", tuple(sorted(IMPLEMENTED_CANDIDATES)))
def test_prediction_is_invariant_to_hidden_suffix(candidate_id: str) -> None:
    if candidate_id.startswith("classical_"):
        pytest.importorskip("statsforecast")
    state = _fit(candidate_id)
    visible = _evaluation()[:18]
    suffix_a = np.linspace(visible[-1], 0.1, 12)
    suffix_b = np.linspace(visible[-1], 2.0, 12)
    full_a = np.concatenate([visible, suffix_a])
    full_b = np.concatenate([visible, suffix_b])
    first = predict_synthetic_candidate(state, full_a[:18], authority=SN1_AUTHORITY)
    second = predict_synthetic_candidate(state, full_b[:18], authority=SN1_AUTHORITY)
    assert first == second


@pytest.mark.parametrize("candidate_id", tuple(sorted(IMPLEMENTED_CANDIDATES)))
def test_training_unit_mapping_order_does_not_change_any_candidate(candidate_id: str) -> None:
    if candidate_id.startswith("classical_"):
        pytest.importorskip("statsforecast")
    units = _fleet()
    reversed_units = dict(reversed(tuple(units.items())))
    first = _fit(candidate_id, units)
    second = _fit(candidate_id, reversed_units)
    prefix = _evaluation()[:20]
    assert predict_synthetic_candidate(first, prefix, authority=SN1_AUTHORITY) == predict_synthetic_candidate(
        second,
        prefix,
        authority=SN1_AUTHORITY,
    )


def test_particle_filter_respects_decreasing_direction() -> None:
    state = _fit("online_ssm_robust_local_trend_pf")
    prefix = _evaluation()[:20]
    forecast = predict_synthetic_candidate(
        state,
        prefix,
        direction="decreasing",
        authority=SN1_AUTHORITY,
    )
    assert all(point <= prefix[-1] for point in forecast.points)
    assert np.all(np.diff(np.asarray(forecast.points)) <= 0.0)
    assert np.all(np.diff(np.asarray(tuple(forecast.quantile_map.values())), axis=1) <= 0.0)
    assert forecast.diagnostics[0] == ("particle_count", 512)


def test_particle_filter_horizon_alignment_matches_linear_oracle() -> None:
    prefix = 1.0 - 0.01 * np.arange(8, dtype=np.float64)
    state = SyntheticCandidateState(
        candidate_id="online_ssm_robust_local_trend_pf",
        horizons=(1,),
        train_scale=1e-8,
        seed=7,
        fitted={},
        residuals={},
    )
    forecast = predict_synthetic_candidate(state, prefix, authority=SN1_AUTHORITY)
    assert forecast.points[0] == pytest.approx(0.92, abs=1e-5)


@pytest.mark.parametrize("candidate_id", tuple(sorted(IMPLEMENTED_CANDIDATES)))
def test_repeated_prediction_is_deterministic(candidate_id: str) -> None:
    if candidate_id.startswith("classical_"):
        pytest.importorskip("statsforecast")
    state = _fit(candidate_id)
    prefix = _evaluation()[:20]
    first = predict_synthetic_candidate(state, prefix, authority=SN1_AUTHORITY)
    second = predict_synthetic_candidate(state, prefix, authority=SN1_AUTHORITY)
    assert first == second


def test_synthetic_authority_is_mandatory() -> None:
    with pytest.raises(SN1ModelError, match="synthetic-only"):
        fit_synthetic_candidate(
            "online_ssm_rls_rels_trend",
            _fleet(),
            (1,),
            authority="REAL_DATA",
        )


@pytest.mark.parametrize(
    "candidate_id",
    tuple(
        sorted(
            set(build_n0_plus_registry().by_id)
            - IMPLEMENTED_CANDIDATES
        )
    ),
)
def test_gated_candidates_cannot_be_run_by_sn1(candidate_id: str) -> None:
    with pytest.raises(SN1ModelError, match="not implemented"):
        fit_synthetic_candidate(candidate_id, _fleet(), (1,), authority=SN1_AUTHORITY)


def test_nonfinite_prefix_fails_closed() -> None:
    state = _fit("online_ssm_rls_rels_trend")
    prefix = _fleet()["train-a"][:20].copy()
    prefix[-1] = np.nan
    with pytest.raises(SN1ModelError, match="finite vector"):
        predict_synthetic_candidate(state, prefix, authority=SN1_AUTHORITY)


def test_prediction_authority_is_mandatory() -> None:
    state = _fit("online_ssm_rls_rels_trend")
    with pytest.raises(SN1ModelError, match="synthetic-only"):
        predict_synthetic_candidate(state, _evaluation()[:20], authority="REAL_DATA")


def test_state_is_frozen_and_residuals_are_read_only() -> None:
    state = _fit("small_ml_elastic_net_direct")
    with pytest.raises(FrozenInstanceError):
        state.candidate_id = "online_ssm_robust_local_trend_pf"  # type: ignore[misc]
    with pytest.raises(TypeError):
        state.fitted[1] = object()  # type: ignore[index]
    with pytest.raises(ValueError, match="read-only"):
        state.residuals[1][0] = 0.0


def test_candidate_specific_state_keys_fail_closed() -> None:
    with pytest.raises(SN1ModelError, match="state keys"):
        SyntheticCandidateState(
            candidate_id="online_ssm_rls_rels_trend",
            horizons=(1,),
            train_scale=0.01,
            seed=7,
            fitted={1: object()},
            residuals={},
        )


def test_classical_forecast_failure_is_attempted_once(monkeypatch: pytest.MonkeyPatch) -> None:
    state = _fit("classical_autoarima")
    calls = 0

    def fail_once(*args, **kwargs):
        nonlocal calls
        calls += 1
        raise SN1ModelError("injected forecast failure")

    monkeypatch.setattr(sn1_synthetic_models, "_classical_forecast", fail_once)
    with pytest.raises(SN1ModelError, match="injected forecast failure"):
        predict_synthetic_candidate(state, _evaluation()[:20], authority=SN1_AUTHORITY)
    assert calls == 1


def test_small_ml_fit_failure_is_attempted_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def fail_once(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        raise RuntimeError("injected fit failure")

    monkeypatch.setattr(sn1_synthetic_models.ElasticNet, "fit", fail_once)
    with pytest.raises(RuntimeError, match="injected fit failure"):
        _fit("small_ml_elastic_net_direct")
    assert calls == 1
