from __future__ import annotations

from typing import Dict, Optional

from polybot_infra.paper_trader import PaperWallet


class PortfolioAccounting:
    def __init__(self, wallet_file: str = "state/sim_wallet.json", wallet: Optional[PaperWallet] = None):
        self.wallet = wallet if wallet is not None else PaperWallet(filename=wallet_file)
        self._peak_balance = 0.0

    def snapshot(self) -> Dict[str, float | int | Dict[str, float]]:
        state = self.wallet._load_state()
        self.wallet.state = state
        balance = float(state.get("balance", 0.0))
        positions = state.get("positions", [])
        settled = state.get("settled", [])
        deployed_capital = float(sum(p.get("amount", 0.0) for p in positions))
        self._peak_balance = max(self._peak_balance, balance + deployed_capital)
        peak = self._peak_balance or (balance + deployed_capital)
        drawdown = 0.0 if peak <= 0 else max(0.0, 1.0 - ((balance + deployed_capital) / peak))
        return {
            "balance": balance,
            "open_positions": len(positions),
            "settled_positions": len(settled),
            "deployed_capital": deployed_capital,
            "category_exposure": self._group_exposure(positions, "category"),
            "event_exposure": self._group_exposure(positions, "event_id"),
            "drawdown_pct": drawdown,
        }

    @staticmethod
    def _group_exposure(positions, key: str) -> Dict[str, float]:
        grouped: Dict[str, float] = {}
        for pos in positions:
            bucket = str(pos.get(key) or "unknown")
            grouped[bucket] = grouped.get(bucket, 0.0) + float(pos.get("amount", 0.0))
        return grouped

