from __future__ import annotations

import json
import os
from dataclasses import asdict
from typing import Any, Dict

from polybot.config import (
    CalibrationConfig,
    EvaluationConfig,
    ExecutionConfig,
    ExposureConfig,
    MarketFilterConfig,
    OpsConfig,
    ProviderConfig,
    RetrievalConfig,
    SizingConfig,
    StrategyConfig,
    StrategyVersionConfig,
    UncertaintyConfig,
)


LEGACY_KEY_MAP = {
    "market_limit": ("provider", "market_limit"),
    "edge_threshold": ("market_filters", "min_edge_threshold"),
    "stake_amount": ("sizing", "default_stake_amount"),
    "daily_limit": ("exposure", "daily_trade_limit"),
    "backtest_report_path": ("evaluation", "backtest_report_path"),
    "wallet_file": ("evaluation", "wallet_file"),
}


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_yaml(path: str) -> Dict[str, Any]:
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError(
            "YAML config requested but PyYAML is not installed. Run: pip install pyyaml"
        ) from exc
    with open(path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
        return data or {}


def load_config_file(path: str) -> Dict[str, Any]:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".json":
        return _load_json(path)
    if ext in (".yaml", ".yml"):
        return _load_yaml(path)
    raise ValueError("Unsupported config type. Use .json, .yaml, or .yml")


def _set_nested(payload: Dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    cursor = payload
    for key in path[:-1]:
        child = cursor.get(key)
        if not isinstance(child, dict):
            child = {}
            cursor[key] = child
        cursor = child
    cursor[path[-1]] = value


def _normalize_legacy_keys(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized = json.loads(json.dumps(payload))
    for key, path in LEGACY_KEY_MAP.items():
        if key in payload and value_is_present(payload[key]):
            _set_nested(normalized, path, payload[key])
    return normalized


def _deep_merge(base: Dict[str, Any], overlay: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in overlay.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def value_is_present(value: Any) -> bool:
    return value is not None


def build_config(
    *,
    config_file: str = "",
    defaults: Dict[str, Any] | None = None,
    overrides: Dict[str, Any] | None = None,
) -> StrategyConfig:
    config_dict = asdict(StrategyConfig())

    if defaults:
        _deep_merge(config_dict, _normalize_legacy_keys(defaults))

    if config_file:
        loaded = load_config_file(config_file)
        if not isinstance(loaded, dict):
            raise ValueError("Config file root must be a JSON/YAML object")
        _deep_merge(config_dict, _normalize_legacy_keys(loaded))

    if overrides:
        present_overrides = {
            key: value for key, value in overrides.items() if value_is_present(value)
        }
        _deep_merge(config_dict, _normalize_legacy_keys(present_overrides))

    return StrategyConfig(
        polling_interval=config_dict["polling_interval"],
        provider=ProviderConfig(**config_dict["provider"]),
        retrieval=RetrievalConfig(**config_dict["retrieval"]),
        calibration=CalibrationConfig(**config_dict["calibration"]),
        uncertainty=UncertaintyConfig(**config_dict["uncertainty"]),
        market_filters=MarketFilterConfig(**config_dict["market_filters"]),
        execution=ExecutionConfig(**config_dict["execution"]),
        sizing=SizingConfig(**config_dict["sizing"]),
        exposure=ExposureConfig(**config_dict["exposure"]),
        evaluation=EvaluationConfig(**config_dict["evaluation"]),
        ops=OpsConfig(**config_dict["ops"]),
        versions=StrategyVersionConfig(**config_dict["versions"]),
        category_profiles=config_dict["category_profiles"],
    )
