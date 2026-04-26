# Gemma PolyBot

`experimental-enhancements` is now a calibration-first, uncertainty-aware research and trading runtime for Polymarket-style binary event markets.

The core design is:
- Gamma-style discovery is separate from executable market state.
- Bull/Bear/Judge remains the raw forecaster, but it no longer decides size or trade authority.
- Every trade path runs through structured forecast parsing, walk-forward calibration, uncertainty estimation, executable-edge modeling, and portfolio/risk gates.
- Replay/backtest mode is time-correct: evidence, calibration labels, and settlements are only released when their timestamps are due.

## Current Runtime

Main package:
- `polybot/data_layer.py`: canonical market normalization, provider merge logic, replay frames, evidence store, deterministic feature store
- `polybot/signal_layer.py`: candidate ranking, retrieval-conditioned Bull/Bear/Judge prompting, strict JSON judge parsing, dataset scaffolding
- `polybot/calibration.py`: walk-forward calibration artifacts, isotonic/beta/logistic calibration, uncertainty engine, conformal-style bands
- `polybot/execution_layer.py`: maker-first execution planner, executable fill-price model, paper/live broker adapters
- `polybot/risk_layer.py`: constrained Kelly sizing, uncertainty gating, exposure caps, circuit breakers, unwind triggers
- `polybot/runner.py`: live cycle runner and event-driven walk-forward backtester
- `polybot/analytics.py`: forecast/trade metrics, calibration curves, category diagnostics, benchmark metadata
- `polybot/portfolio_layer.py`: wallet snapshots, exposure views, drawdown tracking
- `polybot/config.py`: grouped strategy config for provider, retrieval, calibration, uncertainty, execution, sizing, exposure, evaluation, and ops

Legacy compatibility:
- `polybot_legacy/` is still present for the underlying paper wallet, secure live trader wrapper, and model engine hooks.

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.template .env.local
```

Paper run:

```bash
python -m polybot run --mode paper --once
```

Replay backtest:

```bash
python -m polybot backtest --replay-file finetune/replay_snapshots.jsonl
```

Useful overrides:

```bash
python -m polybot backtest \
  --replay-file finetune/replay_snapshots.jsonl \
  --edge-threshold 0.02 \
  --uncertainty-no-trade-above 0.30 \
  --max-spread-bps 600 \
  --max-trade-size 2.0
```

Dashboard:

```bash
python -m polybot dashboard
```

## Config Shape

Use `polybot.config.example.yaml` as the reference. The top-level groups are:
- `provider`
- `retrieval`
- `calibration`
- `uncertainty`
- `market_filters`
- `execution`
- `sizing`
- `exposure`
- `evaluation`
- `ops`
- `versions`

Legacy flat keys like `edge_threshold`, `stake_amount`, `daily_limit`, `market_limit`, `backtest_report_path`, and `wallet_file` still load through the compatibility mapper.

## Replay Format

Backtests accept JSONL. Each line may be either:

1. A canonical frame

```json
{
  "snapshot_id": "snap-001",
  "market": {
    "market_id": "m1",
    "event_id": "e1",
    "title": "Will CPI print above consensus?",
    "description": "US CPI release",
    "resolution_criteria": "Official BLS release",
    "category": "macro",
    "forecast_timestamp": 1710000000,
    "expiry_timestamp": 1710003600,
    "best_bid": 0.47,
    "best_ask": 0.49,
    "depth_bid": 2000,
    "depth_ask": 1800,
    "tick_size": 0.01,
    "fee_schedule": {"maker_bps": 0, "taker_bps": 80},
    "orderbook_timestamp": 1710000000
  },
  "evidence": [
    {
      "evidence_id": "ev1",
      "source_url": "https://example.com/report",
      "source_type": "news",
      "publication_timestamp": 1709999000,
      "ingestion_timestamp": 1709999100,
      "source_credibility": 0.85,
      "source_credibility_metadata": {"tier": "wire"},
      "extracted_claims": ["Consensus moved higher"],
      "summary": "Consensus estimate revised upward"
    }
  ],
  "resolution": {
    "resolved_outcome": "YES",
    "resolution_timestamp": 1710007200
  }
}
```

2. A flat legacy-style market snapshot

```json
{"title":"Will BTC close above 70k today?","price":0.62,"forecast_timestamp":1710000000}
```

If `resolved_outcome` is present, the upgraded runner only uses that label for calibration or settlement once the resolution timestamp becomes due.

## What Changed From The Old Bot

Old flow:
- fetch market
- ask judge for one free-form probability
- compare with market mid
- buy fixed stake

New flow:
1. Normalize market discovery and executable state into a canonical snapshot.
2. Retrieve only evidence available as of the forecast timestamp.
3. Compute deterministic feature groups.
4. Rank/filter candidates before expensive LLM calls.
5. Require judge JSON with `raw_probability`, rationale fields, and evidence references.
6. Calibrate the raw probability with walk-forward artifacts.
7. Estimate composite uncertainty from multiple judge samples and disagreement signals.
8. Model executable fill price, fees, slippage, and uncertainty haircuts.
9. Apply constrained Kelly sizing plus exposure and drawdown controls.
10. Log versioned artifacts and produce forecast/trade diagnostics in the backtest report.

## Verification

```bash
pytest -q
```

The current test suite covers:
- canonical schema merge correctness
- replay-safe evidence retrieval
- structured JSON parsing with safe HOLD fallback
- calibration artifact fitting/prediction
- uncertainty aggregation behavior
- post-cost edge and risk gating
- walk-forward backtest timing and delayed settlement behavior

