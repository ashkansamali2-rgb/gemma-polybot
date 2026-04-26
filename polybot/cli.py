import argparse
import subprocess
import sys

from polybot.config_loader import build_config
from polybot.logging_utils import new_run_id


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

    backtest_cmd = sub.add_parser("backtest", help="Run replay/backtest from snapshots")
    backtest_cmd.add_argument("--replay-file", required=True)
    backtest_cmd.add_argument("--config", default="", help="Path to JSON/YAML config file")
    backtest_cmd.add_argument("--edge-threshold", type=float)
    backtest_cmd.add_argument("--stake-amount", type=float)
    backtest_cmd.add_argument("--daily-limit", type=int)
    backtest_cmd.add_argument("--market-limit", type=int)
    backtest_cmd.add_argument("--backtest-report-path")
    backtest_cmd.add_argument("--wallet-file")

    sub.add_parser("settle", help="Settle resolved paper positions")
    sub.add_parser("dashboard", help="Launch Streamlit dashboard")

    return parser


def main():
    parser = _build_parser()
    args = parser.parse_args()
    run_id = new_run_id()

    if args.command == "settle":
        from settlement import run_settlement

        run_settlement()
        return

    if args.command == "dashboard":
        subprocess.run([sys.executable, "-m", "streamlit", "run", "app.py"], check=False)
        return

    if args.command == "run":
        from polybot.runner import build_runner

        overrides = {
            "polling_interval": 300,
            "edge_threshold": 0.15,
            "stake_amount": 1.0,
            "daily_limit": 5,
            "market_limit": 1000,
            "backtest_report_path": "backtest_report.json",
            "wallet_file": "sim_wallet.json",
        }
        if args.polling_interval is not None:
            overrides["polling_interval"] = args.polling_interval
        if args.edge_threshold is not None:
            overrides["edge_threshold"] = args.edge_threshold
        if args.stake_amount is not None:
            overrides["stake_amount"] = args.stake_amount
        if args.daily_limit is not None:
            overrides["daily_limit"] = args.daily_limit
        if args.market_limit is not None:
            overrides["market_limit"] = args.market_limit
        if args.backtest_report_path is not None:
            overrides["backtest_report_path"] = args.backtest_report_path
        if args.wallet_file is not None:
            overrides["wallet_file"] = args.wallet_file

        config = build_config(
            config_file=args.config,
            overrides=overrides,
        )
        runner = build_runner(mode=args.mode, config=config, run_id=run_id)
        runner.run_live(once=args.once)
        return

    if args.command == "backtest":
        from polybot.runner import build_runner

        overrides = {
            "polling_interval": 0,
            "edge_threshold": 0.15,
            "stake_amount": 1.0,
            "daily_limit": 999999,
            "market_limit": 999999,
            "backtest_report_path": "backtest_report.json",
            "wallet_file": "backtest_wallet.json",
        }
        if args.edge_threshold is not None:
            overrides["edge_threshold"] = args.edge_threshold
        if args.stake_amount is not None:
            overrides["stake_amount"] = args.stake_amount
        if args.daily_limit is not None:
            overrides["daily_limit"] = args.daily_limit
        if args.market_limit is not None:
            overrides["market_limit"] = args.market_limit
        if args.backtest_report_path is not None:
            overrides["backtest_report_path"] = args.backtest_report_path
        if args.wallet_file is not None:
            overrides["wallet_file"] = args.wallet_file

        config = build_config(
            config_file=args.config,
            overrides=overrides,
        )
        runner = build_runner(mode="paper", config=config, run_id=run_id)
        report = runner.run_backtest(replay_file=args.replay_file)
        print(f"Backtest report written: {config.backtest_report_path}")
        print(
            f"Win rate: {report.win_rate:.2%}" if report.win_rate is not None else "Win rate: N/A"
        )
        print(
            f"Average edge: {report.average_edge:.2%}"
            if report.average_edge is not None
            else "Average edge: N/A"
        )
        print(f"Equity curve points: {len(report.equity_curve)}")
        return


if __name__ == "__main__":
    main()
