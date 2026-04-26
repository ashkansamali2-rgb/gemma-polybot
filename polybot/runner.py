from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from typing import List, Optional

from polybot.analytics import (
    benchmark_summary,
    brier_score,
    calibration_curve,
    expected_calibration_error,
    log_loss,
    summarize_strategy,
    summarize_trades,
)
from polybot.calibration import CalibrationManager, UncertaintyEngine
from polybot.config import StrategyConfig
from polybot.data_layer import LivePolymarketDataSource, ReplayDataSource
from polybot.execution_layer import Broker, ExecutionPlanner, LiveBroker, PaperBroker
from polybot.logging_utils import configure_structured_logging, new_run_id
from polybot.portfolio_layer import PortfolioAccounting
from polybot.risk_layer import RiskModel
from polybot.signal_layer import CandidateRanker, MarketEnsembleGenerator
from polybot.types import BacktestReport, ForecastRecord, ReplayFrame, TradeRecord
from polybot_legacy.engine import PolyEngine
from polybot_legacy.settlement import run_settlement


@dataclass
class PendingResolution:
    timestamp: float
    market_title: str
    market_id: str
    outcome: str
    record: Optional[ForecastRecord]


class StrategyRunner:
    def __init__(
        self,
        config: StrategyConfig,
        broker: Broker,
        run_id: Optional[str] = None,
    ):
        self.config = config
        self.run_id = run_id or new_run_id()
        self.logger = configure_structured_logging(
            run_id=self.run_id,
            log_file=self.config.ops.log_file,
        )
        self.data = LivePolymarketDataSource()
        self.calibration_manager = CalibrationManager(config.calibration)
        self.uncertainty_engine = UncertaintyEngine(config.uncertainty)
        self.signal = MarketEnsembleGenerator(
            PolyEngine(),
            config=config,
            calibration_manager=self.calibration_manager,
            uncertainty_engine=self.uncertainty_engine,
        )
        self.ranker = CandidateRanker(config)
        self.execution_planner = ExecutionPlanner(config.execution)
        self.risk = RiskModel(config)
        self.broker = broker
        shared_wallet = getattr(self.broker, "wallet", None)
        self.portfolio = PortfolioAccounting(
            wallet_file=self.config.wallet_file,
            wallet=shared_wallet,
        )
        self.calibration_history: List[ForecastRecord] = []
        self.pending_calibration_records: List[PendingResolution] = []
        self.pending_trade_resolutions: List[PendingResolution] = []
        self.forecasts: List[ForecastRecord] = []
        self.trades: List[TradeRecord] = []

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

        frames = self.data.fetch_markets(limit=self.config.market_limit)
        for frame in frames:
            self._process_live_frame(frame)

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
        candidates_ranked = 0
        candidates_eligible = 0
        signals_with_edge = 0
        trades_attempted = 0
        trades_filled = 0
        equity_curve: List[float] = []

        for frame in replay.iter_frames():
            self._release_due_calibration_records(frame.market.forecast_timestamp)
            self._settle_due_positions(frame.market.forecast_timestamp, equity_curve)
            signals_total += 1

            ranking = self.ranker.rank(frame, live_mode=False)
            candidates_ranked += 1
            if ranking.passed_filters:
                candidates_eligible += 1

            artifact = self.calibration_manager.fit(
                self.calibration_history,
                category=frame.market.category,
                as_of_timestamp=frame.market.forecast_timestamp,
                feature_set=["raw_probability", "category"],
            )
            decision = self.signal.evaluate_frame(
                frame,
                calibration_artifact=artifact,
                ranking=ranking,
            )

            if decision.calibrated_probability is not None:
                bootstrap_plan = self.execution_planner.plan(
                    market=frame.market,
                    calibrated_probability=decision.calibrated_probability,
                    uncertainty_score=decision.uncertainty_score,
                    stake_amount=max(self.config.sizing.default_stake_amount, self.config.sizing.min_trade_size),
                )
                bootstrap_edge = self.execution_planner.edge_after_costs(
                    decision.calibrated_probability,
                    bootstrap_plan,
                )
                decision.post_cost_edge_before_haircuts = bootstrap_edge
                decision.execution_plan = bootstrap_plan.to_dict()
                decision.executable_price = bootstrap_plan.expected_fill_price
                decision.edge_after_costs = bootstrap_edge
                decision.reason = "EXECUTABLE_EDGE_READY"
                if decision.edge_after_costs is not None:
                    signals_with_edge += 1
            else:
                bootstrap_plan = self.execution_planner.plan(
                    market=frame.market,
                    calibrated_probability=0.5,
                    uncertainty_score=1.0,
                    stake_amount=self.config.sizing.min_trade_size,
                )

            portfolio_snapshot = self.portfolio.snapshot()
            ok_to_trade, reason, stake_amount = self.risk.can_trade(
                decision,
                frame.market,
                bootstrap_plan,
                portfolio_snapshot,
            )
            decision.hold_reasons = [] if ok_to_trade else reason.split("|")
            self._log(
                "backtest_signal",
                market=decision.market_title,
                raw_probability=decision.raw_probability,
                calibrated_probability=decision.calibrated_probability,
                edge_after_costs=decision.edge_after_costs,
                eligible=ok_to_trade,
                reason=reason,
                rank_score=decision.rank_score,
                uncertainty=decision.uncertainty_score,
            )
            forecast_record = self.signal.build_forecast_record(
                decision,
                category=frame.market.category,
                resolved_outcome=frame.market.resolved_outcome,
            )

            decision_id = uuid.uuid4().hex[:12]
            trade_executed = False
            if ok_to_trade and decision.calibrated_probability is not None:
                trades_attempted += 1
                execution_plan = self.execution_planner.plan(
                    market=frame.market,
                    calibrated_probability=decision.calibrated_probability,
                    uncertainty_score=decision.uncertainty_score,
                    stake_amount=stake_amount,
                )
                decision.execution_plan = execution_plan.to_dict()
                decision.executable_price = execution_plan.expected_fill_price
                decision.edge_after_costs = self.execution_planner.edge_after_costs(
                    decision.calibrated_probability,
                    execution_plan,
                )
                decision.action = "BUY" if decision.edge_after_costs > 0 else "HOLD"
                decision.reason = "POST_COST_EDGE_POSITIVE" if decision.action == "BUY" else "POST_COST_EDGE_NEGATIVE"
                decision.stake_amount = stake_amount

                ok_to_trade, reason, stake_amount = self.risk.can_trade(
                    decision,
                    frame.market,
                    execution_plan,
                    portfolio_snapshot,
                )
                if ok_to_trade and decision.action == "BUY":
                    result = self.broker.buy_yes(
                        frame.market,
                        stake_amount,
                        execution_plan,
                        decision_id=decision_id,
                    )
                    self._log(
                        "backtest_trade",
                        market=decision.market_title,
                        success=result.success,
                        result_message=result.message,
                        fill_price=result.fill_price,
                        filled_amount=result.filled_amount,
                        fees_paid=result.fees_paid,
                    )
                    if result.success:
                        trades_filled += 1
                        trade_executed = True
                        self.risk.record_fill()
                        self.trades.append(
                            TradeRecord(
                                market_id=frame.market.market_id,
                                event_id=frame.market.event_id,
                                market_title=frame.market.title,
                                category=frame.market.category,
                                timestamp=frame.market.forecast_timestamp,
                                side="YES",
                                amount=stake_amount,
                                expected_fill_price=execution_plan.expected_fill_price,
                                realized_fill_price=result.fill_price or execution_plan.expected_fill_price,
                                fees_paid=result.fees_paid,
                                execution_mode=execution_plan.execution_mode,
                                edge_after_costs=decision.edge_after_costs or 0.0,
                                uncertainty_score=decision.uncertainty_score,
                                resolved_outcome=frame.market.resolved_outcome,
                                pnl=None,
                                status="OPEN",
                            )
                        )
                        if frame.market.resolved_outcome is not None:
                            self.pending_trade_resolutions.append(
                                PendingResolution(
                                    timestamp=self._resolution_timestamp(frame),
                                    market_title=frame.market.title,
                                    market_id=frame.market.market_id,
                                    outcome=str(frame.market.resolved_outcome).upper(),
                                    record=None,
                                )
                            )
                else:
                    decision.hold_reasons = reason.split("|")

            self.forecasts.append(forecast_record)
            self._schedule_calibration_record(frame, forecast_record)
            if not trade_executed and frame.market.resolved_outcome is not None:
                self._schedule_resolution_only(frame, forecast_record)

        self._release_due_calibration_records(float("inf"))
        self._settle_due_positions(float("inf"), equity_curve)

        snapshot = self.portfolio.snapshot()
        resolved_trades = [trade for trade in self.trades if trade.pnl is not None]
        wins = len([trade for trade in resolved_trades if (trade.pnl or 0.0) > 0])
        losses = len([trade for trade in resolved_trades if (trade.pnl or 0.0) <= 0])
        win_rate = (wins / len(resolved_trades)) if resolved_trades else None
        average_edge = (
            sum(trade.edge_after_costs for trade in self.trades) / len(self.trades)
            if self.trades
            else None
        )

        forecast_metrics = {
            "brier": brier_score(self.forecasts),
            "log_loss": log_loss(self.forecasts),
            "ece": expected_calibration_error(self.forecasts),
            "calibration_curve": calibration_curve(self.forecasts),
        }
        trade_metrics = summarize_trades(self.trades, equity_curve or [float(snapshot["balance"])])
        strategy_diagnostics = summarize_strategy(self.forecasts, self.trades)
        report = BacktestReport(
            run_id=self.run_id,
            replay_file=replay_file,
            strategy_id=self.config.versions.strategy_id,
            strategy_versions={
                "model_version": self.config.versions.model_version,
                "prompt_version": self.config.versions.prompt_version,
                "calibrator_version": self.config.versions.calibrator_version,
                "uncertainty_version": self.config.versions.uncertainty_version,
                "ranker_version": self.config.versions.ranker_version,
                "execution_version": self.config.versions.execution_version,
            },
            signals_total=signals_total,
            candidates_ranked=candidates_ranked,
            candidates_eligible=candidates_eligible,
            signals_with_edge=signals_with_edge,
            trades_attempted=trades_attempted,
            trades_filled=trades_filled,
            trades_resolved=len(resolved_trades),
            wins=wins,
            losses=losses,
            win_rate=win_rate,
            average_edge=average_edge,
            final_balance=float(snapshot["balance"]),
            equity_curve=equity_curve or [float(snapshot["balance"])],
            forecast_metrics=forecast_metrics,
            trade_metrics=trade_metrics,
            strategy_diagnostics=strategy_diagnostics,
            audit_summary={
                "forecast_records": len(self.forecasts),
                "trade_records": len(self.trades),
                "pending_calibration_records": len(self.pending_calibration_records),
                "pending_trade_resolutions": len(self.pending_trade_resolutions),
            },
            benchmark_summary=benchmark_summary(
                self.config.versions.strategy_id,
                self.config.evaluation.benchmark_strategy_id,
                self.config.evaluation.challenger_strategy_ids,
            ),
        )
        report_dir = os.path.dirname(self.config.backtest_report_path)
        if report_dir:
            os.makedirs(report_dir, exist_ok=True)
        with open(self.config.backtest_report_path, "w", encoding="utf-8") as handle:
            json.dump(report.to_dict(), handle, indent=2)

        self._log(
            "backtest_completed",
            report_path=self.config.backtest_report_path,
            final_balance=snapshot["balance"],
            win_rate=win_rate,
            average_edge=average_edge,
        )
        return report

    def _process_live_frame(self, frame: ReplayFrame) -> None:
        ranking = self.ranker.rank(frame, live_mode=self.broker.mode() == "LIVE")
        artifact = self.calibration_manager.fit(
            self.calibration_history,
            category=frame.market.category,
            as_of_timestamp=frame.market.forecast_timestamp,
        )
        decision = self.signal.evaluate_frame(
            frame,
            calibration_artifact=artifact,
            ranking=ranking,
        )
        if decision.calibrated_probability is None:
            self._log("trade_skipped", market=decision.market_title, reason=decision.reason)
            return

        execution_plan = self.execution_planner.plan(
            market=frame.market,
            calibrated_probability=decision.calibrated_probability,
            uncertainty_score=decision.uncertainty_score,
            stake_amount=max(self.config.sizing.default_stake_amount, self.config.sizing.min_trade_size),
        )
        decision.executable_price = execution_plan.expected_fill_price
        decision.edge_after_costs = self.execution_planner.edge_after_costs(
            decision.calibrated_probability,
            execution_plan,
        )
        decision.execution_plan = execution_plan.to_dict()
        portfolio_snapshot = self.portfolio.snapshot()
        ok_to_trade, reason, stake_amount = self.risk.can_trade(
            decision,
            frame.market,
            execution_plan,
            portfolio_snapshot,
        )
        self._log(
            "signal_evaluated",
            market=decision.market_title,
            raw_probability=decision.raw_probability,
            calibrated_probability=decision.calibrated_probability,
            edge_after_costs=decision.edge_after_costs,
            uncertainty=decision.uncertainty_score,
            action="BUY" if ok_to_trade else "HOLD",
            reason=reason,
        )
        if not ok_to_trade:
            decision.action = "HOLD"
            decision.reason = reason
            if self.risk.should_unwind(decision, portfolio_snapshot):
                result = self.broker.reduce_yes(
                    frame.market,
                    amount=min(self.config.sizing.default_stake_amount, self.config.exposure.thesis_capital_limit),
                )
                self._log(
                    "inventory_reduction_attempted",
                    market=decision.market_title,
                    success=result.success,
                    result_message=result.message,
                )
            return

        execution_plan = self.execution_planner.plan(
            market=frame.market,
            calibrated_probability=decision.calibrated_probability,
            uncertainty_score=decision.uncertainty_score,
            stake_amount=stake_amount,
        )
        
        # Sizing up might have caused slippage that destroys the edge! Check it again.
        final_edge = self.execution_planner.edge_after_costs(
            decision.calibrated_probability,
            execution_plan,
        )
        if final_edge <= self.config.market_filters.min_edge_threshold:
            self._log(
                "trade_skipped", 
                market=decision.market_title, 
                reason="NEGATIVE_EDGE_AFTER_SIZING_UP",
                edge_after_costs=final_edge,
            )
            decision.action = "HOLD"
            decision.reason = "NEGATIVE_EDGE_AFTER_SIZING_UP"
            return
            
        decision.action = "BUY"
        decision.reason = "POST_COST_EDGE_POSITIVE"
        decision.execution_plan = execution_plan.to_dict()
        decision.executable_price = execution_plan.expected_fill_price
        decision.edge_after_costs = final_edge
        decision.stake_amount = stake_amount

        result = self.broker.buy_yes(
            frame.market,
            stake_amount,
            execution_plan,
            decision_id=uuid.uuid4().hex[:12],
        )
        self._log(
            "trade_attempted",
            market=decision.market_title,
            success=result.success,
            result_message=result.message,
            broker_mode=result.mode,
        )
        if result.success:
            self.risk.record_fill()

    def _schedule_calibration_record(self, frame: ReplayFrame, record: ForecastRecord) -> None:
        if frame.market.resolved_outcome is None:
            return
        resolution_timestamp = self._resolution_timestamp(frame)
        self.pending_calibration_records.append(
            PendingResolution(
                timestamp=resolution_timestamp,
                market_title=frame.market.title,
                market_id=frame.market.market_id,
                outcome=str(frame.market.resolved_outcome).upper(),
                record=record,
            )
        )

    def _schedule_resolution_only(self, frame: ReplayFrame, record: ForecastRecord) -> None:
        # Keep outcome timing in the audit trail even when no trade was filled.
        self._log(
            "resolution_scheduled",
            market=frame.market.title,
            resolution_timestamp=self._resolution_timestamp(frame),
            resolved_outcome=frame.market.resolved_outcome,
            market_id=frame.market.market_id,
            forecast_timestamp=record.timestamp,
        )

    @staticmethod
    def _resolution_timestamp(frame: ReplayFrame) -> float:
        if frame.resolution and frame.resolution.get("resolution_timestamp") is not None:
            return float(frame.resolution["resolution_timestamp"])
        if frame.market.expiry_timestamp is not None:
            return float(frame.market.expiry_timestamp)
        return float(frame.market.forecast_timestamp)

    def _release_due_calibration_records(self, as_of_timestamp: float) -> None:
        pending = []
        for item in self.pending_calibration_records:
            if item.timestamp <= as_of_timestamp:
                if item.record is not None:
                    self.calibration_history.append(item.record)
            else:
                pending.append(item)
        self.pending_calibration_records = pending

    def _settle_due_positions(self, as_of_timestamp: float, equity_curve: List[float]) -> None:
        pending = []
        for item in self.pending_trade_resolutions:
            if item.timestamp > as_of_timestamp:
                pending.append(item)
                continue
            settled, message = self.broker.wallet.settle_market(item.market_title, item.outcome)
            self._log(
                "backtest_settlement",
                market=item.market_title,
                success=settled,
                outcome=item.outcome,
                result_message=message,
            )
            if settled:
                snapshot = self.portfolio.snapshot()
                equity_curve.append(float(snapshot["balance"]))
                for trade in reversed(self.trades):
                    if trade.market_id == item.market_id and trade.pnl is None:
                        payout = (trade.amount / max(trade.realized_fill_price, 1e-6)) if item.outcome == "YES" else 0.0
                        trade.pnl = payout - trade.amount - trade.fees_paid
                        trade.resolved_outcome = item.outcome
                        trade.status = "SETTLED"
                        break
        self.pending_trade_resolutions = pending


def build_runner(mode: str, config: StrategyConfig, run_id: Optional[str] = None) -> StrategyRunner:
    broker = PaperBroker(wallet_file=config.wallet_file) if mode.lower() == "paper" else LiveBroker()
    return StrategyRunner(config=config, broker=broker, run_id=run_id)
