from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


def _default_capability_flags() -> Dict[str, bool]:
    return {
        "supports_negative_risk": False,
        "supports_dynamic_fees": True,
        "supports_partial_fills": True,
        "supports_inventory_reduction": True,
    }


def _default_category_profiles() -> Dict[str, Dict[str, float]]:
    return {
        "default": {
            "retrieval_aggressiveness": 1.0,
            "uncertainty_threshold": 0.35,
            "min_edge_threshold": 0.03,
            "max_trade_size": 3.0,
        },
        "politics": {
            "retrieval_aggressiveness": 1.3,
            "uncertainty_threshold": 0.30,
            "min_edge_threshold": 0.025,
            "max_trade_size": 3.0,
        },
        "macro": {
            "retrieval_aggressiveness": 1.2,
            "uncertainty_threshold": 0.28,
            "min_edge_threshold": 0.03,
            "max_trade_size": 2.5,
        },
        "crypto": {
            "retrieval_aggressiveness": 0.9,
            "uncertainty_threshold": 0.33,
            "min_edge_threshold": 0.035,
            "max_trade_size": 2.0,
        },
        "tech": {
            "retrieval_aggressiveness": 1.1,
            "uncertainty_threshold": 0.34,
            "min_edge_threshold": 0.03,
            "max_trade_size": 2.0,
        },
        "legal": {
            "retrieval_aggressiveness": 1.2,
            "uncertainty_threshold": 0.29,
            "min_edge_threshold": 0.03,
            "max_trade_size": 2.0,
        },
    }


@dataclass
class ProviderConfig:
    discovery_provider: str = "gamma"
    executable_provider: str = "clob"
    market_limit: int = 1000
    stale_quote_seconds: int = 90
    max_horizon_hours: float = 48.0
    platform_version: str = "polymarket-2026"
    capability_flags: Dict[str, bool] = field(default_factory=_default_capability_flags)


@dataclass
class RetrievalConfig:
    enabled: bool = True
    max_evidence_items: int = 6
    max_evidence_age_hours: float = 168.0
    min_source_credibility: float = 0.4
    deduplicate_sources: bool = True
    category_policies: Dict[str, float] = field(default_factory=dict)


@dataclass
class CalibrationConfig:
    enabled: bool = True
    methods_priority: List[str] = field(
        default_factory=lambda: ["isotonic", "beta", "logistic"]
    )
    min_isotonic_samples: int = 25
    min_category_samples: int = 12
    training_window: int = 250
    artifact_version: str = "cal-v1"
    warm_start_method: str = "logistic"


@dataclass
class UncertaintyConfig:
    judge_samples: int = 5
    ensemble_agents: int = 50
    prompt_variants: int = 3
    evidence_subsets: int = 3
    no_trade_above: float = 0.35
    update_instability_penalty: float = 0.5
    conformal_quantile: float = 0.9


@dataclass
class MarketFilterConfig:
    min_edge_threshold: float = 0.03
    max_spread_bps: float = 800.0
    min_depth: float = 50.0
    min_volume: float = 0.0
    require_tradable_token_live: bool = True
    exclude_ambiguous_rules: bool = True


@dataclass
class ExecutionConfig:
    execution_mode: str = "maker_first"
    maker_timeout_sec: int = 45
    cancel_replace_policy: str = "one_cancel_then_cross"
    max_cross_spread_bps: float = 75.0
    min_remaining_edge_after_cross: float = 0.01
    slippage_haircut_bps: float = 15.0
    default_maker_fee_bps: float = 0.0
    default_taker_fee_bps: float = 100.0
    model_partial_fill_ratio: float = 0.7


@dataclass
class SizingConfig:
    default_stake_amount: float = 1.0
    fractional_kelly: float = 0.25
    min_trade_size: float = 0.5
    max_trade_size: float = 3.0
    uncertainty_haircut_scale: float = 0.5
    liquidity_haircut_scale: float = 0.5


@dataclass
class ExposureConfig:
    daily_trade_limit: int = 5
    category_capital_limit: float = 5.0
    thesis_capital_limit: float = 3.0
    unresolved_position_limit: int = 8
    max_drawdown_pct: float = 0.25


@dataclass
class EvaluationConfig:
    backtest_report_path: str = "reports/backtest_report.json"
    wallet_file: str = "state/sim_wallet.json"
    benchmark_windows: int = 3
    benchmark_strategy_id: str = "champion"
    challenger_strategy_ids: List[str] = field(default_factory=lambda: ["baseline"])


@dataclass
class OpsConfig:
    log_file: str = "logs/trading.log"
    global_pause_file: str = "state/global_pause.json"
    enable_auto_pause: bool = True
    recalibration_frequency: str = "daily"
    max_live_slippage_model_error_bps: float = 150.0


@dataclass
class StrategyVersionConfig:
    strategy_id: str = "experimental-enhancements"
    model_version: str = "bull-bear-judge"
    prompt_version: str = "judge-json-v1"
    calibrator_version: str = "cal-v1"
    uncertainty_version: str = "unc-v1"
    ranker_version: str = "rank-v1"
    execution_version: str = "exec-v1"


@dataclass
class StrategyConfig:
    polling_interval: int = 300
    provider: ProviderConfig = field(default_factory=ProviderConfig)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    calibration: CalibrationConfig = field(default_factory=CalibrationConfig)
    uncertainty: UncertaintyConfig = field(default_factory=UncertaintyConfig)
    market_filters: MarketFilterConfig = field(default_factory=MarketFilterConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    sizing: SizingConfig = field(default_factory=SizingConfig)
    exposure: ExposureConfig = field(default_factory=ExposureConfig)
    evaluation: EvaluationConfig = field(default_factory=EvaluationConfig)
    ops: OpsConfig = field(default_factory=OpsConfig)
    versions: StrategyVersionConfig = field(default_factory=StrategyVersionConfig)
    category_profiles: Dict[str, Dict[str, float]] = field(default_factory=_default_category_profiles)

    @property
    def edge_threshold(self) -> float:
        return self.market_filters.min_edge_threshold

    @property
    def stake_amount(self) -> float:
        return self.sizing.default_stake_amount

    @property
    def daily_limit(self) -> int:
        return self.exposure.daily_trade_limit

    @property
    def market_limit(self) -> int:
        return self.provider.market_limit

    @property
    def backtest_report_path(self) -> str:
        return self.evaluation.backtest_report_path

    @property
    def wallet_file(self) -> str:
        return self.evaluation.wallet_file

