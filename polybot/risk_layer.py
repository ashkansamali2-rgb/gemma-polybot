from datetime import date

from polybot.config import StrategyConfig
from polybot.types import SignalDecision


class RiskModel:
    """Risk policy layer."""

    def __init__(self, config: StrategyConfig):
        self.config = config
        self._daily_trades = 0
        self._last_trade_date = None

    def reset_if_new_day(self):
        today = date.today()
        if self._last_trade_date != today:
            self._last_trade_date = today
            self._daily_trades = 0

    @property
    def daily_trades(self) -> int:
        return self._daily_trades

    def can_trade(self, signal: SignalDecision):
        self.reset_if_new_day()
        if self._daily_trades >= self.config.daily_limit:
            return False, "DAILY_LIMIT_REACHED"
        if signal.edge is None:
            return False, "NO_EDGE_VALUE"
        if signal.edge <= self.config.edge_threshold:
            return False, "EDGE_BELOW_THRESHOLD"
        return True, "RISK_OK"

    def record_fill(self):
        self._daily_trades += 1
