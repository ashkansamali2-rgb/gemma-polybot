# Gemma PolyBot

Autonomous Polymarket research and paper-trading bot with:
- MLX-based inference (`PolyEngine`)
- a Bull/Bear/Judge debate loop
- Lean-style layered runtime modules
- paper wallet + settlement simulation
- optional live execution abstraction
- Streamlit dashboard + CLI entrypoint

## What This Codebase Does

PolyBot scans near-expiry Polymarket events, runs model reasoning, extracts a final probability, compares it with market price, and executes simulated buys when edge exceeds a threshold.

Flow:
1. Fetch candidate markets from Polymarket Gamma API
2. Generate Bull and Bear theses
3. Judge outputs `FINAL_PROBABILITY: [XX]%`
4. Compute edge: `ai_prob - market_price`
5. Buy in paper wallet if edge is high enough
6. Settle resolved markets and update wallet state

## Repository Structure

- `auto_pilot.py` - Main autonomous loop (paper mode)
- `engine.py` - Model/adapters loading + inference wrapper
- `polymarket_api.py` - Live market fetch/filter
- `paper_trader.py` - Paper wallet and position bookkeeping
- `settlement.py` - Market resolution and payouts
- `app.py` - Streamlit dashboard
- `secure_trader.py` - Dry-run/live order wrapper via `polymarket-apis`
- `system_check.py` - Environment/model sanity check
- `train.py` - LoRA training launcher (`mlx_vlm.lora`)
- `evaluate.py` - Brier-score evaluation
- `rigorous_test.py` - Trap-detection evaluation
- `finetune/generate_data.py` - Synthetic trap dataset generation
- `.env.template` - Env var template
- `requirements.txt` - Dependencies

Layered engine modules:
- `polybot/data_layer.py` - data ingestion (live + replay)
- `polybot/signal_layer.py` - signal generation (debate + probability extraction)
- `polybot/risk_layer.py` - risk model (edge threshold + daily limits)
- `polybot/execution_layer.py` - broker abstraction (paper/live)
- `polybot/portfolio_layer.py` - portfolio/accounting snapshots
- `polybot/runner.py` - shared runner for live cycles and backtests
- `polybot/logging_utils.py` - structured logs with per-run IDs
- `polybot/cli.py` - command entrypoint

## Prerequisites

- Python 3.10+ (3.11 recommended)
- `pip`
- Internet access (Gamma API)
- Model/adapters for `mlx-lm` / `mlx-vlm`

Compatibility note:
- `mlx-lm` / `mlx-vlm` are Apple Silicon-centric. On Windows/Linux, inference/training may require a different backend or a compatible macOS runtime.

## Quick Setup

```bash
# 1) Create virtual environment
python -m venv .venv

# 2) Activate
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# macOS/Linux
source .venv/bin/activate

# 3) Install dependencies
pip install -r requirements.txt

# 4) Create env file
copy .env.template .env.local   # Windows
# cp .env.template .env.local   # macOS/Linux
```

## Environment Variables

From `.env.template`:
- `POLYMARKET_PK`
- `POLYMARKET_ADDRESS`
- `DRY_RUN=True`

`secure_trader.py` stays in dry-run unless configured for live mode.

## Run Commands

Preferred CLI (Lean-style):
```bash
# run one paper cycle
python -m polybot run --mode paper --once

# run continuous paper trading
python -m polybot run --mode paper

# run live mode (requires token_id in market data + credentials)
python -m polybot run --mode live

# run with config file (.json/.yaml/.yml)
python -m polybot run --config polybot.config.example.yaml --mode paper
```

Backtest/replay mode:
```bash
python -m polybot backtest --replay-file finetune/replay_snapshots.jsonl

# with explicit report output path
python -m polybot backtest --replay-file finetune/replay_snapshots.jsonl --backtest-report-path reports/backtest_run_01.json

# isolate wallet state for backtests
python -m polybot backtest --replay-file finetune/replay_snapshots.jsonl --wallet-file backtests/wallet_run01.json
```

Utilities:
```bash
python -m polybot settle
python -m polybot dashboard
```

Legacy command (kept for compatibility):
```bash
python auto_pilot.py
```

System check:
```bash
python system_check.py
```

Start autonomous paper-trading:
```bash
python auto_pilot.py
```

Manual settlement:
```bash
python settlement.py
```

Dashboard:
```bash
streamlit run app.py
```

Secure trader wrapper test:
```bash
python secure_trader.py
```

## Training Commands

Generate trap samples:
```bash
python finetune/generate_data.py
```

Run LoRA training launcher:
```bash
python train.py
```

`train.py` expects:
- `finetune/train.jsonl`
- output adapters in `poly_adapters/`

## Evaluation Commands

Rigorous trap test:
```bash
python rigorous_test.py
```

Brier evaluation:
```bash
python evaluate.py
```

## Build and Deploy

This repo currently has no packaged build artifact (no Dockerfile/CI release pipeline). Practical deployment is service-style:

```bash
# bot service
python -m polybot run --mode paper

# optional UI service
streamlit run app.py --server.port 8501
```

Recommended production hardening (future work):
- Add `Dockerfile` + `docker-compose.yml`
- Add process supervision (`systemd`, `pm2`, or `supervisord`)
- Centralize logs/alerts for `trading.log`
- Use secrets manager instead of local env files

## State and Logs

- `sim_wallet.json` - paper wallet state
- `trading.log` - structured JSON runtime logs (includes `run_id`)
- `paper_trades.log` - dry-run secure trader log

Never commit private keys or secrets.

## Replay File Format

Backtest/replay expects newline-delimited JSON (`.jsonl`) where each line is one market snapshot object. Minimum recommended fields:

```json
{"title":"Will BTC close above 70k today?","odds":"62%","price":0.62,"volume":1200000,"category":"Crypto","expiry_timestamp":1730000000}
```

Optional fields for richer metrics:
- `resolved_outcome`: `"YES"` or `"NO"` (enables win rate calculation on filled trades)

## Backtest Reports

Backtest command writes a JSON report (default: `backtest_report.json`) containing:
- `win_rate` (when `resolved_outcome` exists in replay snapshots)
- `average_edge`
- `equity_curve` (balance snapshot after each filled trade)
- execution totals (`trades_attempted`, `trades_filled`, etc.)

## Config File Support

PolyBot can load config from JSON or YAML:
- `.json`
- `.yaml`
- `.yml`

Example:
```bash
python -m polybot run --config polybot.config.example.yaml --mode paper
python -m polybot backtest --config polybot.config.example.yaml --replay-file finetune/replay_snapshots.jsonl
```

## Typical Workflow

```bash
pip install -r requirements.txt
python system_check.py
python -m polybot run --mode paper
python -m polybot dashboard
```
