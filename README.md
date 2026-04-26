# Gemma PolyBot

Autonomous Polymarket research and paper-trading bot with:
- MLX-based inference (`PolyEngine`)
- a Bull/Bear/Judge debate loop
- paper wallet + settlement simulation
- optional secure live-order wrapper
- Streamlit dashboard

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
python auto_pilot.py

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
- `trading.log` - runtime log output
- `paper_trades.log` - dry-run secure trader log

Never commit private keys or secrets.

## Typical Workflow

```bash
pip install -r requirements.txt
python system_check.py
python auto_pilot.py
streamlit run app.py
```
