import json
from typing import Dict, Iterable, List

from polymarket_api import fetch_live_polymarket_data


class LivePolymarketDataSource:
    """Data ingestion layer for live candidate markets."""

    def fetch_markets(self, limit: int = 1000) -> List[Dict]:
        markets = fetch_live_polymarket_data(limit=limit)
        markets.sort(key=lambda x: x.get("expiry_hours", 9999))
        return markets


class ReplayDataSource:
    """Backtest/replay data source using newline-delimited JSON snapshots."""

    def __init__(self, replay_file: str):
        self.replay_file = replay_file

    def iter_markets(self) -> Iterable[Dict]:
        with open(self.replay_file, "r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                payload = json.loads(stripped)
                if isinstance(payload, dict):
                    yield payload
