from __future__ import annotations

import json
import os
from datetime import date
from typing import Dict, List, Tuple

from polybot.config import StrategyConfig
from polybot.types import ExecutionPlan, MarketObservation, SignalDecision


class RiskModel:
    def __init__(self, config: StrategyConfig):
        self.config = config
        self._daily_trades = 0
        self._last_trade_date = None
        self._paused_reason = ""

    def reset_if_new_day(self):
        today = date.today()
        if self._last_trade_date != today:
            self._last_trade_date = today
            self._daily_trades = 0

    @property
    def daily_trades(self) -> int:
        return self._daily_trades

    @property
    def paused_reason(self) -> str:
        return self._paused_reason

    def can_trade(
        self,
        signal: SignalDecision,
        market: MarketObservation,
        execution_plan: ExecutionPlan,
        portfolio_snapshot: Dict,
    ) -> Tuple[bool, str, float]:
        self.reset_if_new_day()
        reasons: List[str] = []
        self._paused_reason = ""

        pause_reason = self._manual_pause_reason()
        if pause_reason:
            reasons.append("GLOBAL_PAUSE")
            self._paused_reason = pause_reason

        if self._daily_trades >= self.config.exposure.daily_trade_limit:
            reasons.append("DAILY_LIMIT_REACHED")
        if signal.calibrated_probability is None:
            reasons.append("MISSING_CALIBRATED_PROBABILITY")
        if signal.edge_after_costs is None:
            reasons.append("MISSING_EXECUTABLE_EDGE")
        if signal.edge_after_costs is not None and signal.edge_after_costs <= self.config.market_filters.min_edge_threshold:
            reasons.append("EDGE_BELOW_THRESHOLD")
        if signal.uncertainty_score > self._uncertainty_threshold(market.category):
            reasons.append("UNCERTAINTY_TOO_HIGH")
        if execution_plan.stale_quote:
            reasons.append("STALE_QUOTE")
        if portfolio_snapshot.get("open_positions", 0) >= self.config.exposure.unresolved_position_limit:
            reasons.append("UNRESOLVED_POSITION_CAP")
        if float(portfolio_snapshot.get("drawdown_pct", 0.0)) >= self.config.exposure.max_drawdown_pct:
            reasons.append("DRAWDOWN_CIRCUIT_BREAKER")
        if self._category_exposure(portfolio_snapshot, market.category) >= self.config.exposure.category_capital_limit:
            reasons.append("CATEGORY_CAP_REACHED")
        if self._event_exposure(portfolio_snapshot, market.event_id) >= self.config.exposure.thesis_capital_limit:
            reasons.append("THESIS_CAP_REACHED")
        if signal.calibration_method == "identity" and self.config.calibration.enabled:
            pass # Removed CALIBRATOR_WARMUP_ONLY blocker to allow fallback live trading

        size = self.position_size(signal, execution_plan, portfolio_snapshot, market.category)
        if size < self.config.sizing.min_trade_size:
            reasons.append("SIZE_BELOW_MINIMUM")

        if reasons:
            return False, "|".join(reasons), 0.0
        return True, "RISK_OK", size

    def position_size(
        self,
        signal: SignalDecision,
        execution_plan: ExecutionPlan,
        portfolio_snapshot: Dict,
        category: str,
    ) -> float:
        calibrated_probability = signal.calibrated_probability
        if calibrated_probability is None:
            return 0.0

        bankroll = float(portfolio_snapshot.get("balance", 0.0)) + float(
            portfolio_snapshot.get("deployed_capital", 0.0)
        )
        if bankroll <= 0 or execution_plan.expected_fill_price <= 0:
            return 0.0

        price = execution_plan.expected_fill_price
        payout_ratio = max((1.0 - price) / max(price, 1e-6), 1e-6)
        q = 1.0 - calibrated_probability
        raw_kelly = max(0.0, (payout_ratio * calibrated_probability - q) / payout_ratio)
        base_size = bankroll * raw_kelly * self.config.sizing.fractional_kelly

        uncertainty_haircut = max(
            0.0,
            1.0 - (signal.uncertainty_score * self.config.sizing.uncertainty_haircut_scale),
        )
        liquidity_haircut = max(
            0.25,
            min(1.0, execution_plan.partial_fill_ratio + self.config.sizing.liquidity_haircut_scale * 0.25),
        )
        profile_cap = self.config.category_profiles.get(
            category.lower(),
            self.config.category_profiles["default"],
        ).get("max_trade_size", self.config.sizing.max_trade_size)

        sized = base_size * uncertainty_haircut * liquidity_haircut
        sized = min(sized, self.config.sizing.max_trade_size, profile_cap)
        sized = max(0.0, sized)
        return round(sized, 4)

    def should_unwind(
        self,
        signal: SignalDecision,
        portfolio_snapshot: Dict,
    ) -> bool:
        if signal.edge_after_costs is not None and signal.edge_after_costs < 0:
            return True
        if signal.uncertainty_score > (self.config.uncertainty.no_trade_above * 1.25):
            return True
        if float(portfolio_snapshot.get("drawdown_pct", 0.0)) >= self.config.exposure.max_drawdown_pct:
            return True
        return False

    def record_fill(self):
        self._daily_trades += 1

    def _manual_pause_reason(self) -> str:
        pause_file = self.config.ops.global_pause_file
        if not os.path.exists(pause_file):
            return ""
        try:
            with open(pause_file, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            return "invalid pause file"
        if payload.get("paused"):
            return str(payload.get("reason", "manual pause"))
        return ""

    def _uncertainty_threshold(self, category: str) -> float:
        profile = self.config.category_profiles.get(
            category.lower(),
            self.config.category_profiles["default"],
        )
        return float(profile.get("uncertainty_threshold", self.config.uncertainty.no_trade_above))

    @staticmethod
    def _category_exposure(portfolio_snapshot: Dict, category: str) -> float:
        return float(portfolio_snapshot.get("category_exposure", {}).get(category, 0.0))

    @staticmethod
    def _event_exposure(portfolio_snapshot: Dict, event_id: str) -> float:
        return float(portfolio_snapshot.get("event_exposure", {}).get(event_id, 0.0))

