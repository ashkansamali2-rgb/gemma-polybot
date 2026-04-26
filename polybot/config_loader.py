import json
import os
from dataclasses import asdict
from typing import Any, Dict

from polybot.config import StrategyConfig


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


def build_config(*, config_file: str = "", overrides: Dict[str, Any] = None) -> StrategyConfig:
    config_dict = asdict(StrategyConfig())
    if overrides:
        for key, value in overrides.items():
            if key in config_dict and value is not None:
                config_dict[key] = value

    if not config_file:
        return StrategyConfig(**config_dict)

    loaded = load_config_file(config_file)
    if not isinstance(loaded, dict):
        raise ValueError("Config file root must be a JSON/YAML object")

    # Config file overrides base defaults.
    for key, value in loaded.items():
        if key in config_dict:
            config_dict[key] = value

    # Explicit CLI flags override config file values.
    if overrides:
        for key, value in overrides.items():
            if key in config_dict and value is not None:
                config_dict[key] = value

    return StrategyConfig(**config_dict)
