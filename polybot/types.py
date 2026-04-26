from dataclasses import dataclass
from typing import List, Optional


@dataclass
class SignalDecision:
    market_title: str
    ai_probability: Optional[float]
    market_price: float
    edge: Optional[float]
    action: str
    reason: str
    raw_analysis: str = ""


@dataclass
class ExecutionResult:
    success: bool
    message: str
    mode: str


@dataclass
class BacktestReport:
    run_id: str
    replay_file: str
    signals_total: int
    signals_with_edge: int
    trades_attempted: int
    trades_filled: int
    trades_resolved: int
    wins: int
    losses: int
    win_rate: Optional[float]
    average_edge: Optional[float]
    final_balance: float
    equity_curve: List[float]
