from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence

import numpy as np

from polybot.config import CalibrationConfig, UncertaintyConfig
from polybot.types import CalibrationArtifact, ForecastRecord, UncertaintyEstimate


def clamp_probability(value: float, epsilon: float = 1e-6) -> float:
    return max(epsilon, min(1.0 - epsilon, value))


def _sigmoid(value: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-value))


def _fit_logistic(features: np.ndarray, targets: np.ndarray, steps: int = 500, lr: float = 0.05) -> np.ndarray:
    if features.ndim == 1:
        features = features.reshape(-1, 1)
    weights = np.zeros(features.shape[1] + 1, dtype=float)
    design = np.c_[features, np.ones(len(features))]
    for _ in range(steps):
        logits = design @ weights
        probs = _sigmoid(logits)
        gradient = design.T @ (probs - targets) / max(len(features), 1)
        weights -= lr * gradient
    return weights


def _predict_logistic(features: np.ndarray, weights: np.ndarray) -> np.ndarray:
    if features.ndim == 1:
        features = features.reshape(1, -1)
    design = np.c_[features, np.ones(len(features))]
    return _sigmoid(design @ weights)


def _fit_isotonic(probabilities: Sequence[float], outcomes: Sequence[float]) -> Dict[str, List[float]]:
    pairs = sorted(zip(probabilities, outcomes), key=lambda item: item[0])
    blocks = [
        {
            "x_min": prob,
            "x_max": prob,
            "weight": 1.0,
            "mean": outcome,
        }
        for prob, outcome in pairs
    ]

    idx = 0
    while idx < len(blocks) - 1:
        if blocks[idx]["mean"] > blocks[idx + 1]["mean"]:
            total_weight = blocks[idx]["weight"] + blocks[idx + 1]["weight"]
            merged_mean = (
                blocks[idx]["mean"] * blocks[idx]["weight"]
                + blocks[idx + 1]["mean"] * blocks[idx + 1]["weight"]
            ) / total_weight
            merged = {
                "x_min": blocks[idx]["x_min"],
                "x_max": blocks[idx + 1]["x_max"],
                "weight": total_weight,
                "mean": merged_mean,
            }
            blocks[idx : idx + 2] = [merged]
            idx = max(idx - 1, 0)
            continue
        idx += 1

    x = []
    y = []
    for block in blocks:
        midpoint = (block["x_min"] + block["x_max"]) / 2.0
        x.append(midpoint)
        y.append(block["mean"])
    return {"x": x, "y": y}


def _apply_isotonic(probability: float, parameters: Dict[str, List[float]]) -> float:
    x = parameters.get("x", [])
    y = parameters.get("y", [])
    if not x or not y:
        return probability
    if probability <= x[0]:
        return float(y[0])
    if probability >= x[-1]:
        return float(y[-1])
    return float(np.interp(probability, x, y))


class CalibrationManager:
    def __init__(self, config: CalibrationConfig):
        self.config = config

    def fit(
        self,
        records: Sequence[ForecastRecord],
        *,
        category: Optional[str] = None,
        as_of_timestamp: Optional[float] = None,
        feature_set: Optional[List[str]] = None,
    ) -> CalibrationArtifact:
        feature_set = feature_set or ["raw_probability"]
        eligible = [record for record in records if record.outcome_value() is not None]
        if category:
            category_matches = [record for record in eligible if record.category == category]
            if len(category_matches) >= self.config.min_category_samples:
                eligible = category_matches

        if as_of_timestamp is not None:
            eligible = [record for record in eligible if record.timestamp < as_of_timestamp]

        eligible = eligible[-self.config.training_window :]
        if not eligible:
            return CalibrationArtifact(
                version=self.config.artifact_version,
                method="identity",
                training_start=None,
                training_end=None,
                feature_set=feature_set,
                category_scope=category or "global",
                sample_count=0,
                parameters={},
            )

        probabilities = np.array([clamp_probability(record.raw_probability) for record in eligible])
        outcomes = np.array([record.outcome_value() for record in eligible], dtype=float)

        method = self._choose_method(len(eligible))
        parameters: Dict[str, List[float] | float]
        if method == "isotonic":
            parameters = _fit_isotonic(probabilities.tolist(), outcomes.tolist())
        elif method == "beta":
            features = np.column_stack(
                [np.log(probabilities), np.log(1.0 - probabilities)]
            )
            parameters = {"weights": _fit_logistic(features, outcomes).tolist()}
        elif method == "logistic":
            features = np.log(probabilities / (1.0 - probabilities))
            parameters = {"weights": _fit_logistic(features, outcomes).tolist()}
        else:
            parameters = {}

        return CalibrationArtifact(
            version=self.config.artifact_version,
            method=method,
            training_start=min(record.timestamp for record in eligible),
            training_end=max(record.timestamp for record in eligible),
            feature_set=feature_set,
            category_scope=category or "global",
            sample_count=len(eligible),
            parameters=parameters,
        )

    def calibrate(self, probability: float, artifact: CalibrationArtifact) -> float:
        probability = clamp_probability(probability)
        if artifact.method == "identity":
            return probability
        if artifact.method == "isotonic":
            return clamp_probability(_apply_isotonic(probability, artifact.parameters))
        if artifact.method == "beta":
            weights = np.array(artifact.parameters.get("weights", []), dtype=float)
            if len(weights) != 3:
                return probability
            features = np.array([math.log(probability), math.log(1.0 - probability)])
            return float(clamp_probability(_predict_logistic(features, weights)[0]))
        if artifact.method == "logistic":
            weights = np.array(artifact.parameters.get("weights", []), dtype=float)
            if len(weights) != 2:
                return probability
            feature = np.array([math.log(probability / (1.0 - probability))])
            return float(clamp_probability(_predict_logistic(feature, weights)[0]))
        return probability

    def _choose_method(self, sample_count: int) -> str:
        for method in self.config.methods_priority:
            if method == "isotonic" and sample_count >= self.config.min_isotonic_samples:
                return "isotonic"
            if method == "beta" and sample_count >= 3:
                return "beta"
            if method == "logistic" and sample_count >= 2:
                return "logistic"
        return "identity"


@dataclass
class BeliefUpdateTracker:
    history: Dict[str, List[float]] = field(default_factory=dict)

    def update(self, market_id: str, probability: float) -> float:
        series = self.history.setdefault(market_id, [])
        instability = 0.0
        if series:
            instability = abs(probability - series[-1])
        series.append(probability)
        return instability


@dataclass
class UncertaintyEngine:
    config: UncertaintyConfig
    calibration_residuals: List[float] = field(default_factory=list)
    update_tracker: BeliefUpdateTracker = field(default_factory=BeliefUpdateTracker)

    def estimate(
        self,
        *,
        market_id: str,
        sample_probabilities: Sequence[float],
        rationales: Sequence[str],
        calibration_residual: float = 0.0,
    ) -> UncertaintyEstimate:
        if not sample_probabilities:
            return UncertaintyEstimate(
                uncertainty_score=1.0,
                forecast_variance=0.0,
                semantic_disagreement_score=1.0,
                update_instability_score=1.0,
                prompt_sensitivity_score=1.0,
                evidence_sensitivity_score=1.0,
                calibration_residual_score=1.0,
                confidence_low=0.0,
                confidence_high=1.0,
                sample_probabilities=[],
            )

        samples = np.array(sample_probabilities, dtype=float)
        variance = float(np.var(samples))
        low = float(np.quantile(samples, 0.1))
        high = float(np.quantile(samples, 0.9))
        semantic_disagreement = self._semantic_disagreement(rationales)
        prompt_sensitivity = float(max(samples) - min(samples))
        evidence_sensitivity = float(np.mean(np.abs(samples - np.mean(samples))))
        residual_score = float(min(1.0, max(0.0, calibration_residual)))
        update_instability = self.update_tracker.update(market_id, float(np.mean(samples)))

        score = min(
            1.0,
            (
                variance * 4.0
                + semantic_disagreement
                + prompt_sensitivity
                + evidence_sensitivity
                + residual_score
                + update_instability * self.config.update_instability_penalty
            )
            / 5.5,
        )
        self.calibration_residuals.append(residual_score)
        return UncertaintyEstimate(
            uncertainty_score=score,
            forecast_variance=variance,
            semantic_disagreement_score=semantic_disagreement,
            update_instability_score=update_instability,
            prompt_sensitivity_score=prompt_sensitivity,
            evidence_sensitivity_score=evidence_sensitivity,
            calibration_residual_score=residual_score,
            confidence_low=low,
            confidence_high=high,
            sample_probabilities=samples.tolist(),
        )

    def conformal_band(
        self,
        probability: float,
        historical_residuals: Optional[Iterable[float]] = None,
    ) -> tuple[float, float]:
        residuals = list(historical_residuals or self.calibration_residuals)
        if residuals:
            quantile = float(
                np.quantile(
                    np.array(residuals, dtype=float),
                    min(max(self.config.conformal_quantile, 0.0), 1.0),
                )
            )
        else:
            quantile = 0.1
        return (
            clamp_probability(probability - quantile),
            clamp_probability(probability + quantile),
        )

    @staticmethod
    def _semantic_disagreement(rationales: Sequence[str]) -> float:
        if len(rationales) <= 1:
            return 0.0
        token_sets = [
            {token for token in rationale.lower().split() if token}
            for rationale in rationales
        ]
        if not token_sets:
            return 0.0
        pair_scores = []
        for idx in range(len(token_sets)):
            for jdx in range(idx + 1, len(token_sets)):
                left = token_sets[idx]
                right = token_sets[jdx]
                union = left | right
                if not union:
                    pair_scores.append(0.0)
                    continue
                pair_scores.append(1.0 - (len(left & right) / len(union)))
        return float(np.mean(pair_scores)) if pair_scores else 0.0
