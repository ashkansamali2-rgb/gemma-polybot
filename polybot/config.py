from dataclasses import dataclass


@dataclass
class StrategyConfig:
    polling_interval: int = 300
    edge_threshold: float = 0.15
    stake_amount: float = 1.0
    daily_limit: int = 5
    market_limit: int = 1000
    backtest_report_path: str = "backtest_report.json"
    wallet_file: str = "sim_wallet.json"
