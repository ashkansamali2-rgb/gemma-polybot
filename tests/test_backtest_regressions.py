import json
import uuid
from pathlib import Path

from polybot.config import StrategyConfig
from polybot.calibration import CalibrationManager
from polybot.execution_layer import PaperBroker, ExecutionPlanner
from polybot.portfolio_layer import PortfolioAccounting
from polybot.risk_layer import RiskModel
from polybot.runner import StrategyRunner
from polybot.signal_layer import CandidateRanker
from polybot.types import ForecastRecord, SignalDecision


TEST_DATA_DIR = Path(__file__).resolve().parents[1] / ".testdata"
TEST_DATA_DIR.mkdir(exist_ok=True)


def make_test_dir():
    path = TEST_DATA_DIR / uuid.uuid4().hex
    path.mkdir()
    return path


class DummyLogger:
    def info(self, message, extra=None):
        return None


class DummySignal:
    def __init__(self):
        self.sample_counts = []

    def evaluate_frame(self, frame, *, calibration_artifact, ranking):
        self.sample_counts.append(calibration_artifact.sample_count)
        return SignalDecision(
            market_id=frame.market.market_id,
            event_id=frame.market.event_id,
            token_id=frame.market.token_id,
            market_title=frame.market.title,
            forecast_timestamp=frame.market.forecast_timestamp,
            raw_probability=0.78,
            calibrated_probability=0.78,
            market_price=frame.market.mid_price,
            executable_price=None,
            edge_after_costs=None,
            action="HOLD",
            reason="FORECAST_READY",
            uncertainty_score=0.05,
            forecast_variance=0.001,
            semantic_disagreement_score=0.0,
            update_instability_score=0.0,
            calibration_method="beta",
            execution_mode="maker_first",
            rank_score=ranking.rank_score,
            candidate_status="ELIGIBLE",
        )

    def build_forecast_record(self, decision, *, category, resolved_outcome):
        return ForecastRecord(
            market_id=decision.market_id,
            event_id=decision.event_id,
            timestamp=decision.forecast_timestamp,
            category=category,
            raw_probability=decision.raw_probability or 0.5,
            calibrated_probability=decision.calibrated_probability or 0.5,
            market_price=decision.market_price,
            resolved_outcome=resolved_outcome,
            uncertainty_score=decision.uncertainty_score,
            evidence_count=0,
            calibration_method=decision.calibration_method,
        )


def test_backtest_uses_walk_forward_resolution_timing():
    test_dir = make_test_dir()
    replay_path = test_dir / "replay.jsonl"
    wallet_path = test_dir / "wallet.json"
    report_path = test_dir / "report.json"
    config = StrategyConfig()
    config.evaluation.wallet_file = str(wallet_path)
    config.evaluation.backtest_report_path = str(report_path)
    config.exposure.daily_trade_limit = 50
    config.market_filters.min_edge_threshold = 0.01
    config.sizing.max_trade_size = 1.0
    config.sizing.default_stake_amount = 1.0
    config.sizing.min_trade_size = 0.1
    config.market_filters.min_depth = 1.0
    config.market_filters.max_spread_bps = 1000.0

    frames = [
        {
            "market": {
                "market_id": "m1",
                "event_id": "e1",
                "title": "First market",
                "description": "desc",
                "resolution_criteria": "rules",
                "category": "Geopolitics",
                "forecast_timestamp": 100.0,
                "expiry_timestamp": 210.0,
                "resolved_outcome": "YES",
                "best_bid": 0.38,
                "best_ask": 0.40,
                "depth_bid": 200.0,
                "depth_ask": 200.0,
                "tick_size": 0.01,
                "fee_schedule": {"maker_bps": 0.0, "taker_bps": 0.0},
                "orderbook_timestamp": 95.0,
            },
            "resolution": {"resolved_outcome": "YES", "resolution_timestamp": 200.0},
        },
        {
            "market": {
                "market_id": "m2",
                "event_id": "e2",
                "title": "Second market",
                "description": "desc",
                "resolution_criteria": "rules",
                "category": "Geopolitics",
                "forecast_timestamp": 150.0,
                "expiry_timestamp": 260.0,
                "resolved_outcome": "NO",
                "best_bid": 0.39,
                "best_ask": 0.41,
                "depth_bid": 200.0,
                "depth_ask": 200.0,
                "tick_size": 0.01,
                "fee_schedule": {"maker_bps": 0.0, "taker_bps": 0.0},
                "orderbook_timestamp": 145.0,
            },
            "resolution": {"resolved_outcome": "NO", "resolution_timestamp": 300.0},
        },
        {
            "market": {
                "market_id": "m3",
                "event_id": "e3",
                "title": "Third market",
                "description": "desc",
                "resolution_criteria": "rules",
                "category": "Geopolitics",
                "forecast_timestamp": 250.0,
                "expiry_timestamp": 360.0,
                "resolved_outcome": "YES",
                "best_bid": 0.36,
                "best_ask": 0.38,
                "depth_bid": 200.0,
                "depth_ask": 200.0,
                "tick_size": 0.01,
                "fee_schedule": {"maker_bps": 0.0, "taker_bps": 0.0},
                "orderbook_timestamp": 245.0,
            },
            "resolution": {"resolved_outcome": "YES", "resolution_timestamp": 260.0},
        },
    ]
    replay_path.write_text("\n".join(json.dumps(frame) for frame in frames), encoding="utf-8")

    broker = PaperBroker(wallet_file=str(wallet_path))
    runner = StrategyRunner.__new__(StrategyRunner)
    runner.config = config
    runner.run_id = "testrun"
    runner.logger = DummyLogger()
    runner.signal = DummySignal()
    runner.ranker = CandidateRanker(config)
    runner.calibration_manager = CalibrationManager(config.calibration)
    runner.execution_planner = ExecutionPlanner(config.execution)
    runner.risk = RiskModel(config)
    runner.broker = broker
    runner.portfolio = PortfolioAccounting(wallet_file=str(wallet_path), wallet=broker.wallet)
    runner.calibration_history = []
    runner.pending_calibration_records = []
    runner.pending_trade_resolutions = []
    runner.forecasts = []
    runner.trades = []

    report = StrategyRunner.run_backtest(runner, replay_file=str(replay_path))

    assert runner.signal.sample_counts[:3] == [0, 0, 1]
    assert report.trades_filled == 3
    assert report.trades_resolved == 3
    assert report.win_rate is not None
    assert report.final_balance > 5.0
    assert report.forecast_metrics["brier"] is not None
    assert report.trade_metrics["post_cost_pnl"] != 0.0


def test_backtest_defaults_use_run_scoped_wallet_file():
    from polybot.cli import _backtest_defaults

    defaults = _backtest_defaults("abc123")
    assert defaults["evaluation"]["wallet_file"] == "state/backtest_wallet_abc123.json"
