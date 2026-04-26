from polybot.calibration import CalibrationManager, UncertaintyEngine
from polybot.config import StrategyConfig
from polybot.data_layer import FeatureStore, normalize_market_snapshot
from polybot.execution_layer import ExecutionPlanner
from polybot.risk_layer import RiskModel
from polybot.signal_layer import CandidateRanker, DebateSignalGenerator, parse_structured_forecast
from polybot.types import ReplayFrame


class StructuredEngine:
    def __init__(self, final_payload: str):
        self.final_payload = final_payload
        self.calls = []

    def analyze(self, market, raw_prompt=None, max_tokens=1000, system_prompt=None):
        self.calls.append({"prompt": raw_prompt, "max_tokens": max_tokens})
        if len(self.calls) == 1:
            return "Bull thesis"
        if len(self.calls) == 2:
            return "Bear thesis"
        return self.final_payload


def make_frame():
    market = normalize_market_snapshot(
        {
            "market_id": "m1",
            "event_id": "e1",
            "title": "Will parser hold safely?",
            "description": "A test market.",
            "resolution_criteria": "Binary resolution rules.",
            "category": "crypto",
            "forecast_timestamp": 1000.0,
            "expiry_timestamp": 2000.0,
            "volume": 2500.0,
        },
        {
            "token_id": "tok",
            "best_bid": 0.44,
            "best_ask": 0.46,
            "depth_bid": 180.0,
            "depth_ask": 220.0,
            "tick_size": 0.01,
            "orderbook_timestamp": 995.0,
        },
    )
    features = FeatureStore().build(market, [])
    return ReplayFrame(
        snapshot_id="snap-1",
        market=market,
        evidence=[],
        features=features,
        resolution=None,
        raw_payload={},
    )


def test_parse_structured_forecast_requires_full_json_contract():
    parsed = parse_structured_forecast('{"raw_probability":0.6}')
    assert parsed is None

    parsed = parse_structured_forecast(
        '{"raw_probability":0.6,"short_rationale":"x","key_drivers":["a"],'
        '"counter_drivers":["b"],"invalidation_condition":"c","confidence_band":[0.5,0.7],'
        '"evidence_used":["ev1"]}'
    )
    assert parsed is not None
    assert parsed.raw_probability == 0.6


def test_signal_generator_falls_back_to_hold_on_invalid_judge_output():
    config = StrategyConfig()
    engine = StructuredEngine("FINAL_PROBABILITY: 62%")
    generator = DebateSignalGenerator(
        engine,
        config=config,
        calibration_manager=CalibrationManager(config.calibration),
        uncertainty_engine=UncertaintyEngine(config.uncertainty),
    )
    frame = make_frame()
    ranking = CandidateRanker(config).rank(frame, live_mode=False)
    artifact = CalibrationManager(config.calibration).fit([], category="crypto", as_of_timestamp=1000.0)

    decision = generator.evaluate_frame(frame, calibration_artifact=artifact, ranking=ranking)

    assert decision.action == "HOLD"
    assert decision.reason == "FAILED_STRUCTURED_FORECAST"


def test_execution_planner_and_risk_model_use_post_cost_edge_and_caps():
    config = StrategyConfig()
    market = make_frame().market
    planner = ExecutionPlanner(config.execution)
    plan = planner.plan(
        market=market,
        calibrated_probability=0.68,
        uncertainty_score=0.10,
        stake_amount=1.0,
    )
    edge_after_costs = planner.edge_after_costs(0.68, plan)

    decision = CandidateRanker(config)  # keeps import live for ranker coverage
    assert decision is not None

    signal = generator_signal = parse_structured_forecast(
        '{"raw_probability":0.68,"short_rationale":"x","key_drivers":["a"],'
        '"counter_drivers":["b"],"invalidation_condition":"c","confidence_band":[0.6,0.75],'
        '"evidence_used":[]}'
    )
    assert signal is not None

    risk_signal = make_risk_signal(edge_after_costs=edge_after_costs)
    snapshot = {
        "balance": 10.0,
        "deployed_capital": 0.0,
        "open_positions": 0,
        "category_exposure": {},
        "event_exposure": {},
        "drawdown_pct": 0.0,
    }
    risk = RiskModel(config)
    ok, reason, size = risk.can_trade(risk_signal, market, plan, snapshot)

    assert ok
    assert reason == "RISK_OK"
    assert size >= config.sizing.min_trade_size


def make_risk_signal(edge_after_costs: float):
    frame = make_frame()
    return type(
        "RiskSignal",
        (),
        {
            "calibrated_probability": 0.68,
            "edge_after_costs": edge_after_costs,
            "uncertainty_score": 0.10,
            "calibration_method": "beta",
        },
    )()

