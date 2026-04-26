import time
import json
import os
from typing import Optional

from engine import PolyEngine
from polybot.config import StrategyConfig
from polybot.data_layer import LivePolymarketDataSource, ReplayDataSource
from polybot.execution_layer import Broker, LiveBroker, PaperBroker
from polybot.logging_utils import configure_structured_logging, new_run_id
from polybot.portfolio_layer import PortfolioAccounting
from polybot.risk_layer import RiskModel
from polybot.signal_layer import DebateSignalGenerator
from polybot.types import BacktestReport
from settlement import run_settlement


class StrategyRunner:
    def __init__(
        self,
        config: StrategyConfig,
        broker: Broker,
        run_id: Optional[str] = None,
    ):
        self.config = config
        self.run_id = run_id or new_run_id()
        self.logger = configure_structured_logging(run_id=self.run_id)
        self.data = LivePolymarketDataSource()
        self.signal = DebateSignalGenerator(PolyEngine())
        self.risk = RiskModel(config)
        self.broker = broker
        shared_wallet = getattr(self.broker, "wallet", None)
        self.portfolio = PortfolioAccounting(
            wallet_file=self.config.wallet_file,
            wallet=shared_wallet,
        )

    def _log(self, message: str, **fields):
        fields["run_id"] = self.run_id
        self.logger.info(message, extra={"extra_fields": fields})

    def run_cycle(self):
        self.risk.reset_if_new_day()
        self._log(
            "scan_started",
            mode=self.broker.mode(),
            daily_progress=f"{self.risk.daily_trades}/{self.config.daily_limit}",
        )

        markets = self.data.fetch_markets(limit=self.config.market_limit)
        for market in markets:
            if self.risk.daily_trades >= self.config.daily_limit:
                self._log("daily_limit_reached", limit=self.config.daily_limit)
                break

            signal = self.signal.evaluate_market(market)
            self._log(
                "signal_evaluated",
                market=signal.market_title,
                ai_prob=signal.ai_probability,
                market_price=signal.market_price,
                edge=signal.edge,
                action=signal.action,
            )

            ok_to_trade, reason = self.risk.can_trade(signal)
            if not ok_to_trade:
                self._log("trade_skipped", market=signal.market_title, reason=reason)
                continue

            result = self.broker.buy_yes(market, self.config.stake_amount)
            self._log(
                "trade_attempted",
                market=signal.market_title,
                success=result.success,
                message=result.message,
                broker_mode=result.mode,
            )
            if result.success:
                self.risk.record_fill()

        snapshot = self.portfolio.snapshot()
        self._log("cycle_completed", **snapshot)

    def run_live(self, once: bool = False):
        self._log("runner_started", mode=self.broker.mode())
        while True:
            if isinstance(self.broker, PaperBroker):
                run_settlement(
                    wallet_file=self.config.wallet_file,
                    wallet=self.broker.wallet,
                )
            self.run_cycle()
            if once:
                break
            time.sleep(self.config.polling_interval)

    def run_backtest(self, replay_file: str) -> BacktestReport:
        self._log("backtest_started", replay_file=replay_file, mode=self.broker.mode())
        replay = ReplayDataSource(replay_file)
        signals_total = 0
        signals_with_edge = 0
        trades_attempted = 0
        trades_filled = 0
        trades_resolved = 0
        wins = 0
        losses = 0
        edge_sum = 0.0
        equity_curve = []

        for market in replay.iter_markets():
            signals_total += 1
            signal = self.signal.evaluate_market(market)
            if signal.edge is not None:
                signals_with_edge += 1
                edge_sum += signal.edge

            ok_to_trade, reason = self.risk.can_trade(signal)
            self._log(
                "backtest_signal",
                market=signal.market_title,
                ai_prob=signal.ai_probability,
                edge=signal.edge,
                eligible=ok_to_trade,
                reason=reason,
            )
            if ok_to_trade:
                trades_attempted += 1
                result = self.broker.buy_yes(market, self.config.stake_amount)
                self._log(
                    "backtest_trade",
                    market=signal.market_title,
                    success=result.success,
                    message=result.message,
                )
                if result.success:
                    trades_filled += 1
                    self.risk.record_fill()
                    resolved = market.get("resolved_outcome")
                    if resolved is not None:
                        trades_resolved += 1
                        if str(resolved).upper() == "YES":
                            wins += 1
                        else:
                            losses += 1
                    snapshot = self.portfolio.snapshot()
                    equity_curve.append(float(snapshot["balance"]))

        snapshot = self.portfolio.snapshot()
        win_rate = (wins / trades_resolved) if trades_resolved > 0 else None
        average_edge = (edge_sum / signals_with_edge) if signals_with_edge > 0 else None

        report = BacktestReport(
            run_id=self.run_id,
            replay_file=replay_file,
            signals_total=signals_total,
            signals_with_edge=signals_with_edge,
            trades_attempted=trades_attempted,
            trades_filled=trades_filled,
            trades_resolved=trades_resolved,
            wins=wins,
            losses=losses,
            win_rate=win_rate,
            average_edge=average_edge,
            final_balance=float(snapshot["balance"]),
            equity_curve=equity_curve,
        )
        report_dir = os.path.dirname(self.config.backtest_report_path)
        if report_dir:
            os.makedirs(report_dir, exist_ok=True)
        with open(self.config.backtest_report_path, "w", encoding="utf-8") as handle:
            json.dump(report.__dict__, handle, indent=2)

        self._log(
            "backtest_completed",
            report_path=self.config.backtest_report_path,
            **snapshot,
            win_rate=win_rate,
            average_edge=average_edge,
        )
        return report


def build_runner(mode: str, config: StrategyConfig, run_id: Optional[str] = None) -> StrategyRunner:
    broker = PaperBroker(wallet_file=config.wallet_file) if mode.lower() == "paper" else LiveBroker()
    return StrategyRunner(config=config, broker=broker, run_id=run_id)
