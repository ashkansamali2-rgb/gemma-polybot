from __future__ import annotations

import math
from collections import defaultdict
from typing import Dict, Iterable, List, Sequence

from polybot.types import ForecastRecord, TradeRecord


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def brier_score(records: Sequence[ForecastRecord], *, calibrated: bool = True) -> float | None:
    pairs = []
    for record in records:
        outcome = record.outcome_value()
        if outcome is None:
            continue
        probability = record.calibrated_probability if calibrated else record.raw_probability
        pairs.append((probability - outcome) ** 2)
    return _mean(pairs) if pairs else None


def log_loss(records: Sequence[ForecastRecord], *, calibrated: bool = True) -> float | None:
    losses = []
    for record in records:
        outcome = record.outcome_value()
        if outcome is None:
            continue
        probability = record.calibrated_probability if calibrated else record.raw_probability
        probability = min(max(probability, 1e-6), 1.0 - 1e-6)
        losses.append(-(outcome * math.log(probability) + (1.0 - outcome) * math.log(1.0 - probability)))
    return _mean(losses) if losses else None


def expected_calibration_error(records: Sequence[ForecastRecord], *, bins: int = 10) -> float | None:
    eligible = [record for record in records if record.outcome_value() is not None]
    if not eligible:
        return None
    bin_pairs: Dict[int, List[tuple[float, float]]] = defaultdict(list)
    for record in eligible:
        probability = min(max(record.calibrated_probability, 0.0), 0.999999)
        bucket = min(int(probability * bins), bins - 1)
        bin_pairs[bucket].append((probability, record.outcome_value()))
    total = len(eligible)
    ece = 0.0
    for bucket, pairs in bin_pairs.items():
        avg_prob = _mean([pair[0] for pair in pairs])
        avg_outcome = _mean([pair[1] for pair in pairs])
        ece += (len(pairs) / total) * abs(avg_prob - avg_outcome)
    return ece


def calibration_curve(records: Sequence[ForecastRecord], *, bins: int = 10) -> List[Dict[str, float]]:
    eligible = [record for record in records if record.outcome_value() is not None]
    if not eligible:
        return []
    bin_pairs: Dict[int, List[tuple[float, float]]] = defaultdict(list)
    for record in eligible:
        probability = min(max(record.calibrated_probability, 0.0), 0.999999)
        bucket = min(int(probability * bins), bins - 1)
        bin_pairs[bucket].append((probability, record.outcome_value()))
    curve = []
    for bucket in sorted(bin_pairs):
        pairs = bin_pairs[bucket]
        curve.append(
            {
                "bucket": float(bucket),
                "forecast_mean": _mean([pair[0] for pair in pairs]),
                "outcome_mean": _mean([pair[1] for pair in pairs]),
                "count": float(len(pairs)),
            }
        )
    return curve


def max_drawdown(equity_curve: Sequence[float]) -> float:
    peak = float("-inf")
    worst = 0.0
    for value in equity_curve:
        peak = max(peak, value)
        if peak > 0:
            worst = max(worst, 1.0 - (value / peak))
    return worst


def summarize_trades(trades: Sequence[TradeRecord], equity_curve: Sequence[float]) -> Dict[str, float | int | Dict]:
    resolved = [trade for trade in trades if trade.pnl is not None]
    wins = [trade for trade in resolved if (trade.pnl or 0.0) > 0]
    losses = [trade for trade in resolved if (trade.pnl or 0.0) <= 0]
    slippage = [
        abs(trade.realized_fill_price - trade.expected_fill_price)
        for trade in trades
        if trade.realized_fill_price is not None
    ]
    by_uncertainty: Dict[str, Dict[str, float]] = defaultdict(lambda: {"count": 0.0, "wins": 0.0})
    by_category: Dict[str, Dict[str, float]] = defaultdict(lambda: {"count": 0.0, "pnl": 0.0})
    by_execution: Dict[str, Dict[str, float]] = defaultdict(lambda: {"count": 0.0, "pnl": 0.0})

    for trade in trades:
        bucket = f"{min(int(trade.uncertainty_score * 4), 3)}"
        by_uncertainty[bucket]["count"] += 1.0
        by_uncertainty[bucket]["wins"] += 1.0 if (trade.pnl or 0.0) > 0 else 0.0
        by_category[trade.category]["count"] += 1.0
        by_category[trade.category]["pnl"] += float(trade.pnl or 0.0)
        by_execution[trade.execution_mode]["count"] += 1.0
        by_execution[trade.execution_mode]["pnl"] += float(trade.pnl or 0.0)

    return {
        "post_cost_pnl": sum(float(trade.pnl or 0.0) for trade in resolved),
        "drawdown": max_drawdown(equity_curve),
        "hit_rate": (len(wins) / len(resolved)) if resolved else None,
        "inventory_turnover": float(len(trades)),
        "realized_slippage": _mean(slippage) if slippage else 0.0,
        "maker_vs_taker": dict(by_execution),
        "category_performance": dict(by_category),
        "uncertainty_buckets": {
            key: {
                "count": value["count"],
                "win_rate": (value["wins"] / value["count"]) if value["count"] else None,
            }
            for key, value in by_uncertainty.items()
        },
    }


def summarize_strategy(
    forecasts: Sequence[ForecastRecord],
    trades: Sequence[TradeRecord],
) -> Dict[str, Dict]:
    category_forecasts: Dict[str, List[ForecastRecord]] = defaultdict(list)
    for record in forecasts:
        category_forecasts[record.category].append(record)
    category_metrics = {
        category: {
            "count": len(records),
            "brier": brier_score(records),
            "ece": expected_calibration_error(records),
        }
        for category, records in category_forecasts.items()
    }
    evidence_on = [record for record in forecasts if record.evidence_count > 0]
    evidence_off = [record for record in forecasts if record.evidence_count == 0]
    return {
        "category_metrics": category_metrics,
        "evidence_comparison": {
            "evidence_on_brier": brier_score(evidence_on),
            "evidence_off_brier": brier_score(evidence_off),
        },
        "raw_vs_calibrated": {
            "raw_brier": brier_score(forecasts, calibrated=False),
            "calibrated_brier": brier_score(forecasts, calibrated=True),
        },
        "trade_count": len(trades),
    }


def benchmark_summary(strategy_id: str, baseline_id: str, challenger_ids: Iterable[str]) -> Dict[str, object]:
    return {
        "champion": strategy_id,
        "baseline": baseline_id,
        "challengers": list(challenger_ids),
        "methodology": "rolling walk-forward benchmark",
    }

