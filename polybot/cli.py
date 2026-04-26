from __future__ import annotations

import argparse
import subprocess
import sys
from typing import Any, Dict

from polybot.config_loader import build_config
from polybot.logging_utils import new_run_id
from polybot.paths import APPS_DIR


CLI_OVERRIDE_MAP = {
    "polling_interval": ("polling_interval",),
    "edge_threshold": ("market_filters", "min_edge_threshold"),
    "stake_amount": ("sizing", "default_stake_amount"),
    "daily_limit": ("exposure", "daily_trade_limit"),
    "market_limit": ("provider", "market_limit"),
    "backtest_report_path": ("evaluation", "backtest_report_path"),
    "wallet_file": ("evaluation", "wallet_file"),
    "uncertainty_no_trade_above": ("uncertainty", "no_trade_above"),
    "max_spread_bps": ("market_filters", "max_spread_bps"),
    "min_depth": ("market_filters", "min_depth"),
    "max_trade_size": ("sizing", "max_trade_size"),
    "strategy_id": ("versions", "strategy_id"),
}


def _set_nested(payload: Dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    cursor = payload
    for key in path[:-1]:
        child = cursor.get(key)
        if not isinstance(child, dict):
            child = {}
            cursor[key] = child
        cursor = child
    cursor[path[-1]] = value


def _collect_overrides(args, option_names) -> Dict[str, Any]:
    overrides: Dict[str, Any] = {}
    for option_name in option_names:
        value = getattr(args, option_name)
        if value is None:
            continue
        path = CLI_OVERRIDE_MAP.get(option_name, (option_name,))
        _set_nested(overrides, path, value)
    return overrides


def _run_defaults():
    return {
        "polling_interval": 300,
        "market_filters": {"min_edge_threshold": 0.03},
        "sizing": {"default_stake_amount": 1.0, "max_trade_size": 3.0},
        "exposure": {"daily_trade_limit": 5},
        "provider": {"market_limit": 1000},
        "evaluation": {
            "backtest_report_path": "reports/backtest_report.json",
            "wallet_file": "state/sim_wallet.json",
        },
    }


def _backtest_defaults(run_id: str):
    return {
        "polling_interval": 0,
        "market_filters": {"min_edge_threshold": 0.03},
        "sizing": {"default_stake_amount": 1.0, "max_trade_size": 3.0},
        "exposure": {"daily_trade_limit": 999999},
        "provider": {"market_limit": 999999},
        "evaluation": {
            "backtest_report_path": "reports/backtest_report.json",
            "wallet_file": f"state/backtest_wallet_{run_id}.json",
        },
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="polybot", description="PolyBot CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    run_cmd = sub.add_parser("run", help="Run live/paper strategy loop")
    run_cmd.add_argument("--mode", choices=["paper", "live"], default="paper")
    run_cmd.add_argument("--once", action="store_true", help="Run one cycle and exit")
    run_cmd.add_argument("--config", default="", help="Path to JSON/YAML config file")
    run_cmd.add_argument("--polling-interval", type=int)
    run_cmd.add_argument("--edge-threshold", type=float)
    run_cmd.add_argument("--stake-amount", type=float)
    run_cmd.add_argument("--daily-limit", type=int)
    run_cmd.add_argument("--market-limit", type=int)
    run_cmd.add_argument("--backtest-report-path")
    run_cmd.add_argument("--wallet-file")
    run_cmd.add_argument("--uncertainty-no-trade-above", type=float)
    run_cmd.add_argument("--max-spread-bps", type=float)
    run_cmd.add_argument("--min-depth", type=float)
    run_cmd.add_argument("--max-trade-size", type=float)
    run_cmd.add_argument("--strategy-id")

    backtest_cmd = sub.add_parser("backtest", help="Run replay/backtest from snapshots")
    backtest_cmd.add_argument("--replay-file", required=True)
    backtest_cmd.add_argument("--config", default="", help="Path to JSON/YAML config file")
    backtest_cmd.add_argument("--edge-threshold", type=float)
    backtest_cmd.add_argument("--stake-amount", type=float)
    backtest_cmd.add_argument("--daily-limit", type=int)
    backtest_cmd.add_argument("--market-limit", type=int)
    backtest_cmd.add_argument("--backtest-report-path")
    backtest_cmd.add_argument("--wallet-file")
    backtest_cmd.add_argument("--uncertainty-no-trade-above", type=float)
    backtest_cmd.add_argument("--max-spread-bps", type=float)
    backtest_cmd.add_argument("--min-depth", type=float)
    backtest_cmd.add_argument("--max-trade-size", type=float)
    backtest_cmd.add_argument("--strategy-id")

    sub.add_parser("settle", help="Settle resolved paper positions")
    sub.add_parser("dashboard", help="Launch Streamlit dashboard")

    return parser


def main():
    parser = _build_parser()
    args = parser.parse_args()
    run_id = new_run_id()

    if args.command == "settle":
        from polybot_infra.settlement import run_settlement

        run_settlement()
        return

    if args.command == "dashboard":
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", str(APPS_DIR / "streamlit" / "app.py")],
            check=False,
        )
        return

    if args.command == "run":
        from polybot.runner import build_runner

        config = build_config(
            config_file=args.config,
            defaults=_run_defaults(),
            overrides=_collect_overrides(
                args,
                (
                    "polling_interval",
                    "edge_threshold",
                    "stake_amount",
                    "daily_limit",
                    "market_limit",
                    "backtest_report_path",
                    "wallet_file",
                    "uncertainty_no_trade_above",
                    "max_spread_bps",
                    "min_depth",
                    "max_trade_size",
                    "strategy_id",
                ),
            ),
        )
        runner = build_runner(mode=args.mode, config=config, run_id=run_id)
        runner.run_live(once=args.once)
        return

    if args.command == "backtest":
        from polybot.runner import build_runner

        config = build_config(
            config_file=args.config,
            defaults=_backtest_defaults(run_id),
            overrides=_collect_overrides(
                args,
                (
                    "edge_threshold",
                    "stake_amount",
                    "daily_limit",
                    "market_limit",
                    "backtest_report_path",
                    "wallet_file",
                    "uncertainty_no_trade_above",
                    "max_spread_bps",
                    "min_depth",
                    "max_trade_size",
                    "strategy_id",
                ),
            ),
        )
        runner = build_runner(mode="paper", config=config, run_id=run_id)
        report = runner.run_backtest(replay_file=args.replay_file)
        print(f"Backtest report written: {config.backtest_report_path}")
        print(
            f"Win rate: {report.win_rate:.2%}" if report.win_rate is not None else "Win rate: N/A"
        )
        brier = report.forecast_metrics.get("brier")
        print(f"Brier score: {brier:.4f}" if brier is not None else "Brier score: N/A")
        print(
            f"Average executable edge: {report.average_edge:.2%}"
            if report.average_edge is not None
            else "Average executable edge: N/A"
        )
        print(f"Trades filled/resolved: {report.trades_filled}/{report.trades_resolved}")
        return


if __name__ == "__main__":
    main()

