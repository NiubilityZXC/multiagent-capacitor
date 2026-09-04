"""SN1-only numerical candidates for causal synthetic qualification.

The public entry points require the literal ``SN1_SYNTHETIC_ONLY`` authority
token.  This module is not a Ren/Patrizi adapter and does not compute scientific
scores.  Its purpose is to qualify prefix-only behavior, deterministic failure
semantics, quantile shape, and train-unit isolation before a real-data preseal.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from statistics import NormalDist
from types import MappingProxyType
from typing import Any, Mapping, Sequence

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import ElasticNet
from sklearn.preprocessing import StandardScaler

from experiments.n0_plus.registry import PROPOSAL_SHA256, build_n0_plus_registry


SN1_AUTHORITY = "SN1_SYNTHETIC_ONLY"
QUANTILE_LEVELS = (0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95)
IMPLEMENTED_CANDIDATES = frozenset(
    {
        "classical_autoarima",
        "classical_autoets",
        "classical_dynamic_optimized_theta",
        "online_ssm_rls_rels_trend",
        "online_ssm_robust_local_trend_pf",
        "small_ml_elastic_net_direct",
        "small_ml_hist_gradient_boosting_direct",
    }
)
REGISTRY_HASH = build_n0_plus_registry().registry_hash


class SN1ModelError(ValueError):
    """An SN1 synthetic candidate request violates the frozen toy contract."""


@dataclass(frozen=True, slots=True)
class ForecastVector:
    horizons: tuple[int, ...]
    points: tuple[float, ...]
    quantiles: tuple[tuple[float, tuple[float, ...]], ...]
    diagnostics: tuple[tuple[str, float | int | str], ...] = ()

    def __post_init__(self) -> None:
        horizons = tuple(self.horizons)
        points = tuple(float(value) for value in self.points)
        quantiles = tuple((float(level), tuple(float(value) for value in values)) for level, values in self.quantiles)
        diagnostics = tuple(self.diagnostics)
        object.__setattr__(self, "horizons", horizons)
        object.__setattr__(self, "points", points)
        object.__setattr__(self, "quantiles", quantiles)
        object.__setattr__(self, "diagnostics", diagnostics)
        if not horizons or any(value < 1 for value in horizons):
            raise SN1ModelError("horizons must be positive")
        if horizons != tuple(sorted(set(horizons))):
            raise SN1ModelError("horizons must be unique and sorted")
        if len(points) != len(horizons) or not np.all(np.isfinite(points)):
            raise SN1ModelError("points must be finite and cover every horizon")
        levels = tuple(level for level, _ in quantiles)
        if levels != QUANTILE_LEVELS:
            raise SN1ModelError("quantile levels differ from the SN1 contract")
        matrix = np.asarray([values for _, values in quantiles], dtype=np.float64)
        if matrix.shape != (len(QUANTILE_LEVELS), len(horizons)) or not np.all(np.isfinite(matrix)):
            raise SN1ModelError("quantiles must be finite and cover every horizon")
        if np.any(np.diff(matrix, axis=0) < -1e-12):
            raise SN1ModelError("quantiles must be nested")
        names = tuple(name for name, _ in diagnostics)
        if names != tuple(sorted(set(names))):
            raise SN1ModelError("diagnostic names must be unique and sorted")

    @property
    def quantile_map(self) -> Mapping[float, tuple[float, ...]]:
        return MappingProxyType(dict(self.quantiles))


@dataclass(frozen=True, slots=True)
class SyntheticCandidateState:
    candidate_id: str
    horizons: tuple[int, ...]
    train_scale: float
    seed: int
    fitted: Mapping[int, Any]
    residuals: Mapping[int, np.ndarray]
    registry_hash: str = REGISTRY_HASH
    proposal_sha256: str = PROPOSAL_SHA256

    def __post_init__(self) -> None:
        if self.candidate_id not in IMPLEMENTED_CANDIDATES:
            raise SN1ModelError("state candidate is outside the SN1 allowlist")
        horizons = _validate_horizons(self.horizons)
        if isinstance(self.train_scale, bool) or not isinstance(
            self.train_scale, (int, float, np.integer, np.floating)
        ):
            raise SN1ModelError("state train scale must be numeric")
        scale = float(self.train_scale)
        if not np.isfinite(scale) or scale <= 0.0:
            raise SN1ModelError("state train scale must be finite and positive")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int) or self.seed < 0:
            raise SN1ModelError("state seed must be a non-negative integer")
        if self.registry_hash != REGISTRY_HASH or self.proposal_sha256 != PROPOSAL_SHA256:
            raise SN1ModelError("state registry or proposal identity differs")
        if not isinstance(self.fitted, Mapping) or not isinstance(self.residuals, Mapping):
            raise SN1ModelError("state fitted values and residuals must be mappings")
        fitted = dict(self.fitted)
        residuals: dict[int, np.ndarray] = {}
        for horizon, values in self.residuals.items():
            array = np.array(values, dtype=np.float64, copy=True)
            if array.ndim != 1 or array.size < 1 or not np.all(np.isfinite(array)):
                raise SN1ModelError("state residuals must be non-empty finite vectors")
            array.setflags(write=False)
            residuals[horizon] = array
        expected_keys = set(horizons) if self.candidate_id.startswith("small_ml_") else set()
        if set(fitted) != expected_keys or set(residuals) != expected_keys:
            raise SN1ModelError("state keys are incompatible with the candidate family")
        for horizon in expected_keys:
            if self.candidate_id == "small_ml_elastic_net_direct":
                value = fitted[horizon]
                if (
                    not isinstance(value, tuple)
                    or len(value) != 2
                    or not isinstance(value[0], StandardScaler)
                    or not isinstance(value[1], ElasticNet)
                ):
                    raise SN1ModelError("elastic-net state has incompatible fitted values")
            elif not isinstance(fitted[horizon], HistGradientBoostingRegressor):
                raise SN1ModelError("histogram-gradient-boosting state has incompatible fitted values")
        object.__setattr__(self, "horizons", horizons)
        object.__setattr__(self, "train_scale", scale)
        object.__setattr__(self, "fitted", MappingProxyType(fitted))
        object.__setattr__(self, "residuals", MappingProxyType(residuals))


def _require_authority(authority: str) -> None:
    if authority != SN1_AUTHORITY:
        raise SN1ModelError("SN1 models require synthetic-only authority")


def _validate_horizons(horizons: Sequence[int]) -> tuple[int, ...]:
    values = tuple(horizons)
    if not values or any(isinstance(item, bool) or not isinstance(item, int) or item < 1 for item in values):
        raise SN1ModelError("horizons must be positive integers")
    if values != tuple(sorted(set(values))):
        raise SN1ModelError("horizons must be unique and sorted")
    return values


def _validate_series(values: Sequence[float] | np.ndarray, *, minimum: int = 2) -> np.ndarray:
    series = np.asarray(values, dtype=np.float64)
    if series.ndim != 1 or series.size < minimum or not np.all(np.isfinite(series)):
        raise SN1ModelError(f"series must be a finite vector with at least {minimum} observations")
    return series


def _validate_training_units(training_units: Mapping[str, Sequence[float] | np.ndarray]) -> dict[str, np.ndarray]:
    if not isinstance(training_units, Mapping) or len(training_units) < 2:
        raise SN1ModelError("SN1 requires at least two synthetic training units")
    result: dict[str, np.ndarray] = {}
    for unit in sorted(training_units):
        if not isinstance(unit, str) or not unit or unit.strip() != unit:
            raise SN1ModelError("synthetic unit keys must be canonical tokens")
        result[unit] = _validate_series(training_units[unit], minimum=8)
    return result


def _train_scale(training_units: Mapping[str, np.ndarray]) -> float:
    differences = np.concatenate([np.diff(values) for values in training_units.values()])
    center = float(np.median(differences))
    scale = 1.4826 * float(np.median(np.abs(differences - center)))
    if not np.isfinite(scale) or scale <= 1e-8:
        scale = max(float(np.median(np.abs(differences))), 1e-8)
    return scale


def _features(prefix: np.ndarray) -> np.ndarray:
    if prefix.size < 5:
        raise SN1ModelError("small-ML features require at least five prefix observations")
    all_x = np.arange(prefix.size, dtype=np.float64)
    local = prefix[-5:]
    local_x = np.arange(local.size, dtype=np.float64)
    global_slope = float(np.polyfit(all_x, prefix, 1)[0])
    local_slope = float(np.polyfit(local_x, local, 1)[0])
    differences = np.diff(prefix)
    curvature = float(differences[-1] - differences[-2])
    robust_step = float(np.median(np.abs(differences - np.median(differences))))
    return np.asarray(
        [
            prefix[-1],
            global_slope,
            local_slope,
            curvature,
            robust_step,
            float(prefix.size),
            float(np.min(local)),
            float(np.max(local)),
        ],
        dtype=np.float64,
    )


def _training_matrix(
    training_units: Mapping[str, np.ndarray],
    horizon: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    features: list[np.ndarray] = []
    responses: list[float] = []
    weights: list[float] = []
    for unit in sorted(training_units):
        series = training_units[unit]
        origins = tuple(range(4, series.size - horizon))
        if not origins:
            raise SN1ModelError(f"training unit {unit} has no origins for horizon {horizon}")
        unit_weight = 1.0 / len(origins)
        for origin in origins:
            prefix = series[: origin + 1]
            features.append(_features(prefix))
            responses.append(float(series[origin + horizon] - series[origin]))
            weights.append(unit_weight)
    return np.vstack(features), np.asarray(responses), np.asarray(weights)


def fit_synthetic_candidate(
    candidate_id: str,
    training_units: Mapping[str, Sequence[float] | np.ndarray],
    horizons: Sequence[int],
    *,
    seed: int = 20260904,
    authority: str,
) -> SyntheticCandidateState:
    _require_authority(authority)
    if candidate_id not in IMPLEMENTED_CANDIDATES:
        raise SN1ModelError("candidate is not implemented for SN1 synthetic qualification")
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 0:
        raise SN1ModelError("seed must be a non-negative integer")
    horizon_values = _validate_horizons(horizons)
    units = _validate_training_units(training_units)
    scale = _train_scale(units)
    fitted: dict[int, Any] = {}
    residuals: dict[int, np.ndarray] = {}
    if candidate_id.startswith("small_ml_"):
        for horizon in horizon_values:
            x, y, weights = _training_matrix(units, horizon)
            if candidate_id == "small_ml_elastic_net_direct":
                scaler = StandardScaler().fit(x, sample_weight=weights)
                estimator = ElasticNet(
                    alpha=1e-3,
                    l1_ratio=0.5,
                    fit_intercept=True,
                    max_iter=10000,
                    selection="cyclic",
                )
                transformed = scaler.transform(x)
                estimator.fit(transformed, y, sample_weight=weights)
                predicted = estimator.predict(transformed)
                fitted[horizon] = (scaler, estimator)
            else:
                estimator = HistGradientBoostingRegressor(
                    learning_rate=0.05,
                    max_iter=100,
                    max_leaf_nodes=7,
                    l2_regularization=1.0,
                    random_state=seed,
                )
                estimator.fit(x, y, sample_weight=weights)
                predicted = estimator.predict(x)
                fitted[horizon] = estimator
            residuals[horizon] = np.asarray(y - predicted, dtype=np.float64)
    return SyntheticCandidateState(candidate_id, horizon_values, scale, seed, fitted, residuals)


def _normal_quantiles(points: np.ndarray, scale: np.ndarray) -> np.ndarray:
    rows = []
    normal = NormalDist()
    for level in QUANTILE_LEVELS:
        rows.append(points + normal.inv_cdf(level) * scale)
    return np.asarray(rows, dtype=np.float64)


def _classical_forecast(candidate_id: str, prefix: np.ndarray, maximum_horizon: int) -> Mapping[str, Any]:
    try:
        from statsforecast.models import AutoARIMA, AutoETS, DynamicOptimizedTheta
    except ImportError as exc:
        raise SN1ModelError("StatsForecast is required by classical SN1 candidates") from exc
    model_class = {
        "classical_autoarima": AutoARIMA,
        "classical_autoets": AutoETS,
        "classical_dynamic_optimized_theta": DynamicOptimizedTheta,
    }[candidate_id]
    model = model_class(season_length=1)
    try:
        output = model.forecast(y=prefix, h=maximum_horizon, level=[50, 80, 90])
    except Exception as exc:
        raise SN1ModelError(f"classical forecast failed: {type(exc).__name__}") from exc
    return output


def _predict_classical(state: SyntheticCandidateState, prefix: np.ndarray) -> ForecastVector:
    output = _classical_forecast(state.candidate_id, prefix, max(state.horizons))
    indexes = np.asarray([horizon - 1 for horizon in state.horizons], dtype=np.int64)
    points = np.asarray(output["mean"], dtype=np.float64)[indexes]
    quantile_keys = (
        (0.05, "lo-90"),
        (0.10, "lo-80"),
        (0.25, "lo-50"),
        (0.50, "mean"),
        (0.75, "hi-50"),
        (0.90, "hi-80"),
        (0.95, "hi-90"),
    )
    quantiles = tuple(
        (level, tuple(np.asarray(output[key], dtype=np.float64)[indexes]))
        for level, key in quantile_keys
    )
    return ForecastVector(state.horizons, tuple(points), quantiles)


def _rls_point(prefix: np.ndarray, horizons: tuple[int, ...], forgetting: float = 0.98) -> np.ndarray:
    theta = np.asarray([prefix[0], prefix[1] - prefix[0]], dtype=np.float64)
    covariance = np.eye(2, dtype=np.float64) * 1e4
    for index, observation in enumerate(prefix):
        design = np.asarray([1.0, float(index)], dtype=np.float64)
        denominator = forgetting + float(design @ covariance @ design)
        gain = covariance @ design / denominator
        theta = theta + gain * (observation - float(design @ theta))
        covariance = (covariance - np.outer(gain, design) @ covariance) / forgetting
    return np.asarray(
        [theta[0] + theta[1] * (prefix.size - 1 + horizon) for horizon in horizons],
        dtype=np.float64,
    )


def _systematic_resample(weights: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    positions = (rng.random() + np.arange(weights.size)) / weights.size
    cumulative = np.cumsum(weights)
    cumulative[-1] = 1.0
    return np.searchsorted(cumulative, positions, side="right")


def _pf_forecast(
    prefix: np.ndarray,
    horizons: tuple[int, ...],
    train_scale: float,
    seed: int,
    direction: str,
) -> tuple[np.ndarray, np.ndarray, int]:
    if direction not in {"decreasing", "increasing", "unconstrained"}:
        raise SN1ModelError("unknown degradation direction")
    particle_count = 512
    rng = np.random.default_rng(seed)
    initial_slope = float(np.median(np.diff(prefix[: min(prefix.size, 5)])))
    levels = np.full(particle_count, prefix[0]) + rng.normal(0.0, train_scale, particle_count)
    slopes = np.full(particle_count, initial_slope) + rng.normal(0.0, train_scale * 0.25, particle_count)
    weights = np.full(particle_count, 1.0 / particle_count)
    resample_count = 0
    for index, observation in enumerate(prefix):
        if index > 0:
            previous_levels = levels
            levels = levels + slopes + rng.normal(0.0, train_scale * 0.20, particle_count)
            slopes = slopes + rng.normal(0.0, train_scale * 0.05, particle_count)
            if direction == "decreasing":
                slopes = np.minimum(slopes, 0.0)
                levels = np.minimum(levels, previous_levels)
            elif direction == "increasing":
                slopes = np.maximum(slopes, 0.0)
                levels = np.maximum(levels, previous_levels)
        standardized = (observation - levels) / max(train_scale, 1e-8)
        log_weights = np.log(np.maximum(weights, np.finfo(np.float64).tiny))
        log_weights -= 2.5 * np.log1p((standardized * standardized) / 4.0)
        log_weights -= np.max(log_weights)
        weights = np.exp(log_weights)
        total = float(np.sum(weights))
        if not np.isfinite(total) or total <= 0.0:
            raise SN1ModelError("particle filter weights degenerated")
        weights /= total
        effective = 1.0 / float(np.sum(weights * weights))
        if effective < particle_count / 2:
            indexes = _systematic_resample(weights, rng)
            levels = levels[indexes]
            slopes = slopes[indexes]
            weights.fill(1.0 / particle_count)
            resample_count += 1
    if not np.allclose(weights, weights[0]):
        indexes = _systematic_resample(weights, rng)
        levels = levels[indexes]
        slopes = slopes[indexes]
        weights.fill(1.0 / particle_count)
        resample_count += 1
    samples_by_horizon: dict[int, np.ndarray] = {}
    for step in range(1, max(horizons) + 1):
        previous_levels = levels
        levels = levels + slopes + rng.normal(0.0, train_scale * 0.20, particle_count)
        slopes = slopes + rng.normal(0.0, train_scale * 0.05, particle_count)
        if direction == "decreasing":
            slopes = np.minimum(slopes, 0.0)
            levels = np.minimum(levels, previous_levels)
        elif direction == "increasing":
            slopes = np.maximum(slopes, 0.0)
            levels = np.maximum(levels, previous_levels)
        if step in horizons:
            samples_by_horizon[step] = levels.copy()
    samples = np.column_stack([samples_by_horizon[horizon] for horizon in horizons])
    points = np.mean(samples, axis=0)
    quantiles = np.quantile(samples, QUANTILE_LEVELS, axis=0)
    return points, quantiles, resample_count


def _predict_small_ml(state: SyntheticCandidateState, prefix: np.ndarray) -> ForecastVector:
    feature = _features(prefix).reshape(1, -1)
    points: list[float] = []
    quantile_columns: list[np.ndarray] = []
    for horizon in state.horizons:
        estimator = state.fitted[horizon]
        if state.candidate_id == "small_ml_elastic_net_direct":
            scaler, model = estimator
            increment = float(model.predict(scaler.transform(feature))[0])
        else:
            increment = float(estimator.predict(feature)[0])
        point = float(prefix[-1] + increment)
        points.append(point)
        residuals = state.residuals[horizon]
        quantile_columns.append(point + np.quantile(residuals, QUANTILE_LEVELS))
    matrix = np.column_stack(quantile_columns)
    return ForecastVector(
        state.horizons,
        tuple(points),
        tuple((level, tuple(matrix[index])) for index, level in enumerate(QUANTILE_LEVELS)),
        (("interval_semantics", "IN_SAMPLE_TOY_RESIDUAL_SHAPE_ONLY_NOT_CALIBRATED"),),
    )


def predict_synthetic_candidate(
    state: SyntheticCandidateState,
    prefix: Sequence[float] | np.ndarray,
    *,
    direction: str = "decreasing",
    authority: str,
) -> ForecastVector:
    _require_authority(authority)
    if not isinstance(state, SyntheticCandidateState):
        raise SN1ModelError("invalid SN1 fitted state")
    values = _validate_series(prefix, minimum=8)
    if state.candidate_id.startswith("classical_"):
        return _predict_classical(state, values)
    if state.candidate_id == "online_ssm_rls_rels_trend":
        points = _rls_point(values, state.horizons)
        scales = state.train_scale * np.sqrt(np.asarray(state.horizons, dtype=np.float64))
        matrix = _normal_quantiles(points, scales)
        return ForecastVector(
            state.horizons,
            tuple(points),
            tuple((level, tuple(matrix[index])) for index, level in enumerate(QUANTILE_LEVELS)),
        )
    if state.candidate_id == "online_ssm_robust_local_trend_pf":
        points, matrix, resamples = _pf_forecast(
            values,
            state.horizons,
            state.train_scale,
            state.seed,
            direction,
        )
        return ForecastVector(
            state.horizons,
            tuple(points),
            tuple((level, tuple(matrix[index])) for index, level in enumerate(QUANTILE_LEVELS)),
            (("particle_count", 512), ("resample_count", resamples)),
        )
    return _predict_small_ml(state, values)
