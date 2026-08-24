"""Small causal forecasting models used by the frozen Stress-2 harness."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

MODEL_ORDER = ("last_value", "global_drift", "local_linear", "exponential", "local_trend_kf", "ridge")


def candidate_configs(model: str) -> list[dict[str, Any]]:
    if model in {"last_value", "global_drift"}:
        return [{}]
    if model == "local_linear":
        return [{"window": k} for k in (2, 3, 4)]
    if model == "exponential":
        return [
            {"window": window, "direction": direction}
            for window in (4, "all")
            for direction in ("none", "physical")
        ]
    if model == "local_trend_kf":
        return [
            {"q_level": ql, "q_slope": qs, "r": r}
            for ql in (1e-4, 1e-2)
            for qs in (1e-4, 1e-2)
            for r in (1e-2, 1.0)
        ]
    if model == "ridge":
        return [{"window": k, "alpha": alpha} for k in (2, 3, 4) for alpha in (1e-4, 1e-2, 1.0, 1e2)]
    raise KeyError(model)


def _linear_fit(values: np.ndarray) -> tuple[float, float]:
    x = np.arange(values.size, dtype=np.float64)
    x_bar = float(np.mean(x))
    y_bar = float(np.mean(values))
    denom = float(np.sum((x - x_bar) ** 2))
    slope = 0.0 if denom == 0.0 else float(np.sum((x - x_bar) * (values - y_bar)) / denom)
    intercept = y_bar - slope * x_bar
    return intercept, slope


def _ridge_features(prefix: np.ndarray, window: int) -> np.ndarray:
    if prefix.size < window:
        raise ValueError("prefix shorter than ridge window")
    recent = prefix[-window:]
    diffs = np.diff(recent)
    return np.asarray([prefix[-1], float(prefix.size - 1), *diffs.tolist()], dtype=np.float64)


@dataclass(frozen=True)
class RidgeState:
    scaler: StandardScaler
    model: Ridge
    window: int


def fit_global_state(
    model: str,
    unit_series: dict[str, np.ndarray],
    horizon: int,
    context: int,
    config: dict[str, Any],
) -> Any:
    if model == "local_trend_kf":
        diffs = np.concatenate([np.diff(np.asarray(values, dtype=np.float64)) for values in unit_series.values()])
        scale = max(float(np.median(np.abs(diffs))), 1e-6)
        return {"scale": scale}
    if model != "ridge":
        return None

    window = int(config["window"])
    features: list[np.ndarray] = []
    responses: list[float] = []
    raw_weights: list[float] = []
    for unit in sorted(unit_series):
        values = np.asarray(unit_series[unit], dtype=np.float64)
        origins = list(range(context - 1, values.size - horizon))
        if not origins:
            raise ValueError(f"no training origins for {unit}")
        unit_weight = 1.0 / len(origins)
        for origin in origins:
            prefix = values[: origin + 1]
            features.append(_ridge_features(prefix, window))
            responses.append(float(values[origin + horizon] - values[origin]))
            raw_weights.append(unit_weight)
    x = np.vstack(features)
    y = np.asarray(responses)
    weights = np.asarray(raw_weights)
    scaler = StandardScaler().fit(x, sample_weight=weights)
    ridge = Ridge(alpha=float(config["alpha"]), fit_intercept=True)
    ridge.fit(scaler.transform(x), y, sample_weight=weights)
    return RidgeState(scaler=scaler, model=ridge, window=window)


def _kalman_prediction(prefix: np.ndarray, horizon: int, config: dict[str, Any], scale: float) -> float:
    f = np.asarray([[1.0, 1.0], [0.0, 1.0]])
    h_vec = np.asarray([[1.0, 0.0]])
    variance = scale * scale
    q = variance * np.diag([float(config["q_level"]), float(config["q_slope"])])
    r = variance * float(config["r"])
    initial_slope = float(prefix[1] - prefix[0]) if prefix.size > 1 else 0.0
    state = np.asarray([float(prefix[0]), initial_slope])
    covariance = variance * np.diag([10.0, 10.0])
    for observation in prefix[1:]:
        state = f @ state
        covariance = f @ covariance @ f.T + q
        innovation = float(observation - (h_vec @ state)[0])
        innovation_var = float((h_vec @ covariance @ h_vec.T)[0, 0] + r)
        gain = (covariance @ h_vec.T)[:, 0] / innovation_var
        state = state + gain * innovation
        covariance = (np.eye(2) - np.outer(gain, h_vec[0])) @ covariance
    future = np.asarray([[1.0, float(horizon)], [0.0, 1.0]]) @ state
    return float(future[0])


def predict_prefix(
    model: str,
    prefix: np.ndarray,
    horizon: int,
    target: str,
    config: dict[str, Any],
    global_state: Any = None,
) -> float:
    """Predict from a revealed prefix only; no future timestamps are accepted."""

    values = np.asarray(prefix, dtype=np.float64)
    if values.ndim != 1 or not np.all(np.isfinite(values)):
        raise ValueError("prefix must be a finite vector")
    if horizon < 1:
        raise ValueError("horizon must be positive")
    if model == "last_value":
        return float(values[-1])
    if model == "global_drift":
        slope = 0.0 if values.size < 2 else float((values[-1] - values[0]) / (values.size - 1))
        return float(values[-1] + horizon * slope)
    if model == "local_linear":
        window = int(config["window"])
        local = values[-window:]
        intercept, slope = _linear_fit(local)
        return float(intercept + slope * (local.size - 1 + horizon))
    if model == "exponential":
        window = values.size if config["window"] == "all" else int(config["window"])
        local = values[-window:]
        if np.any(local <= 0.0):
            raise ValueError("exponential model requires positive ratios")
        intercept, slope = _linear_fit(np.log(local))
        if config["direction"] == "physical":
            if target == "capacity_ratio":
                slope = min(slope, 0.0)
            elif target == "esr_ratio":
                slope = max(slope, 0.0)
            else:
                raise KeyError(target)
            x = np.arange(local.size, dtype=np.float64)
            intercept = float(np.mean(np.log(local)) - slope * np.mean(x))
        return float(np.exp(intercept + slope * (local.size - 1 + horizon)))
    if model == "local_trend_kf":
        if not isinstance(global_state, dict) or "scale" not in global_state:
            raise ValueError("KF requires training-side scale")
        return _kalman_prediction(values, horizon, config, float(global_state["scale"]))
    if model == "ridge":
        if not isinstance(global_state, RidgeState):
            raise ValueError("ridge requires a fitted training-side state")
        x = _ridge_features(values, global_state.window).reshape(1, -1)
        increment = float(global_state.model.predict(global_state.scaler.transform(x))[0])
        return float(values[-1] + increment)
    raise KeyError(model)
