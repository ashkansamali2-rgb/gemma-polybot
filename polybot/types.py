from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


def _default_fee_schedule() -> Dict[str, float]:
    return {
        "maker_bps": 0.0,
        "taker_bps": 100.0,
    }


@dataclass
class MarketObservation:
    market_id: str
    event_id: str
    token_id: Optional[str]
    title: str
    description: str
    resolution_criteria: str
    category: str
    subcategory: str
    forecast_timestamp: float
    expiry_timestamp: Optional[float]
    best_bid: Optional[float]
    best_ask: Optional[float]
    mid_price: float
    last_trade_price: Optional[float]
    spread: Optional[float]
    depth_bid: float
    depth_ask: float
    tick_size: float
    fee_schedule: Dict[str, float] = field(default_factory=_default_fee_schedule)
    volume: float = 0.0
    open_interest: Optional[float] = None
    market_status: str = "active"
    resolved_outcome: Optional[str] = None
    raw_provider_payloads: Dict[str, Any] = field(default_factory=dict)
    orderbook_timestamp: Optional[float] = None
    platform_capability_flags: Dict[str, bool] = field(default_factory=dict)

    @property
    def price(self) -> float:
        return self.mid_price

    @property
    def odds(self) -> str:
        return f"{round(self.mid_price * 100)}%"

    @property
    def executable_mid(self) -> float:
        if self.best_bid is not None and self.best_ask is not None:
            return (self.best_bid + self.best_ask) / 2.0
        return self.mid_price

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvidenceRecord:
    evidence_id: str
    source_url: str
    source_type: str
    publication_timestamp: float
    ingestion_timestamp: float
    source_credibility: float
    source_credibility_metadata: Dict[str, Any]
    extracted_claims: List[str]
    summary: str
    linked_event_id: Optional[str]
    linked_market_id: Optional[str]
    version: str = "v1"
    raw_payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FeatureSnapshot:
    market_id: str
    event_id: str
    as_of_timestamp: float
    market_microstructure: Dict[str, float]
    price_history: Dict[str, float]
    liquidity: Dict[str, float]
    evidence: Dict[str, float]
    metadata: Dict[str, Any]
    calibration_context: Dict[str, Any]

    def flat_dict(self) -> Dict[str, Any]:
        flattened: Dict[str, Any] = {
            "market_id": self.market_id,
            "event_id": self.event_id,
            "as_of_timestamp": self.as_of_timestamp,
        }
        for group_name, payload in (
            ("market_microstructure", self.market_microstructure),
            ("price_history", self.price_history),
            ("liquidity", self.liquidity),
            ("evidence", self.evidence),
            ("metadata", self.metadata),
            ("calibration_context", self.calibration_context),
        ):
            for key, value in payload.items():
                flattened[f"{group_name}.{key}"] = value
        return flattened


@dataclass
class ForecastResponse:
    raw_probability: float
    short_rationale: str
    key_drivers: List[str]
    counter_drivers: List[str]
    invalidation_condition: str
    confidence_band: List[float]
    evidence_used: List[str]
    raw_response: str
    bull_thesis: str = ""
    bear_thesis: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CalibrationArtifact:
    version: str
    method: str
    training_start: Optional[float]
    training_end: Optional[float]
    feature_set: List[str]
    category_scope: str
    sample_count: int
    parameters: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class UncertaintyEstimate:
    uncertainty_score: float
    forecast_variance: float
    semantic_disagreement_score: float
    update_instability_score: float
    prompt_sensitivity_score: float
    evidence_sensitivity_score: float
    calibration_residual_score: float
    confidence_low: float
    confidence_high: float
    sample_probabilities: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CandidateRanking:
    rank_score: float
    passed_filters: bool
    exclusion_reason: str
    factor_scores: Dict[str, float]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionPlan:
    execution_mode: str
    expected_fill_price: float
    maker_fill_price: float
    taker_fill_price: float
    fees_paid: float
    slippage_haircut: float
    uncertainty_haircut: float
    max_cross_spread_bps: float
    min_remaining_edge_after_cross: float
    stale_quote: bool
    partial_fill_ratio: float
    cancel_replace_policy: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SignalDecision:
    market_id: str
    event_id: str
    token_id: Optional[str]
    market_title: str
    forecast_timestamp: float
    raw_probability: Optional[float]
    calibrated_probability: Optional[float]
    market_price: float
    executable_price: Optional[float]
    edge_after_costs: Optional[float]
    action: str
    reason: str
    uncertainty_score: float
    forecast_variance: float
    semantic_disagreement_score: float
    update_instability_score: float
    confidence_low: Optional[float] = None
    confidence_high: Optional[float] = None
    raw_confidence_band: List[float] = field(default_factory=list)
    evidence_ids: List[str] = field(default_factory=list)
    key_drivers: List[str] = field(default_factory=list)
    counter_drivers: List[str] = field(default_factory=list)
    invalidation_condition: str = ""
    short_rationale: str = ""
    raw_analysis: str = ""
    calibration_artifact_version: str = ""
    calibration_method: str = ""
    execution_mode: str = ""
    execution_plan: Dict[str, Any] = field(default_factory=dict)
    uncertainty_components: Dict[str, float] = field(default_factory=dict)
    rank_score: float = 0.0
    candidate_status: str = ""
    hold_reasons: List[str] = field(default_factory=list)
    post_cost_edge_before_haircuts: Optional[float] = None
    stake_amount: float = 0.0

    @property
    def ai_probability(self) -> Optional[float]:
        return self.raw_probability

    @property
    def edge(self) -> Optional[float]:
        return self.edge_after_costs

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutionResult:
    success: bool
    message: str
    mode: str
    filled_amount: float = 0.0
    fill_price: Optional[float] = None
    fees_paid: float = 0.0
    order_id: str = ""
    decision_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ForecastRecord:
    market_id: str
    event_id: str
    timestamp: float
    category: str
    raw_probability: float
    calibrated_probability: float
    market_price: float
    resolved_outcome: Optional[str]
    uncertainty_score: float
    evidence_count: int
    calibration_method: str

    def outcome_value(self) -> Optional[float]:
        if self.resolved_outcome is None:
            return None
        if str(self.resolved_outcome).upper() == "YES":
            return 1.0
        if str(self.resolved_outcome).upper() == "NO":
            return 0.0
        return None


@dataclass
class TradeRecord:
    market_id: str
    event_id: str
    market_title: str
    category: str
    timestamp: float
    side: str
    amount: float
    expected_fill_price: float
    realized_fill_price: float
    fees_paid: float
    execution_mode: str
    edge_after_costs: float
    uncertainty_score: float
    resolved_outcome: Optional[str]
    pnl: Optional[float]
    status: str

    def hit(self) -> Optional[bool]:
        if self.resolved_outcome is None:
            return None
        return str(self.resolved_outcome).upper() == "YES"


@dataclass
class AuditEnvelope:
    market_snapshot_id: str
    evidence_bundle_id: str
    forecast_artifact_id: str
    calibration_artifact_id: str
    trade_decision_id: str
    execution_result_id: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReplayFrame:
    snapshot_id: str
    market: MarketObservation
    evidence: List[EvidenceRecord]
    features: Optional[FeatureSnapshot]
    resolution: Optional[Dict[str, Any]]
    raw_payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "snapshot_id": self.snapshot_id,
            "market": self.market.to_dict(),
            "evidence": [item.to_dict() for item in self.evidence],
            "features": self.features.flat_dict() if self.features else None,
            "resolution": self.resolution,
            "raw_payload": self.raw_payload,
        }
        return payload


@dataclass
class BacktestReport:
    run_id: str
    replay_file: str
    strategy_id: str
    strategy_versions: Dict[str, str]
    signals_total: int
    candidates_ranked: int
    candidates_eligible: int
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
    forecast_metrics: Dict[str, Any] = field(default_factory=dict)
    trade_metrics: Dict[str, Any] = field(default_factory=dict)
    strategy_diagnostics: Dict[str, Any] = field(default_factory=dict)
    audit_summary: Dict[str, Any] = field(default_factory=dict)
    benchmark_summary: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
