from paper_trader import PaperWallet


class PortfolioAccounting:
    """Portfolio/accounting layer for reporting and metrics."""

    def __init__(self, wallet_file: str = "sim_wallet.json", wallet: PaperWallet = None):
        self.wallet = wallet if wallet is not None else PaperWallet(filename=wallet_file)

    def snapshot(self):
        # Always refresh from disk so snapshots include broker/settlement mutations.
        state = self.wallet._load_state()
        self.wallet.state = state
        positions = state.get("positions", [])
        settled = state.get("settled", [])
        return {
            "balance": state.get("balance", 0.0),
            "open_positions": len(positions),
            "settled_positions": len(settled),
            "deployed_capital": sum(p.get("amount", 0.0) for p in positions),
        }
