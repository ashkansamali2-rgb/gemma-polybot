from abc import ABC, abstractmethod
from typing import Dict

from paper_trader import PaperWallet
from polybot.types import ExecutionResult


class Broker(ABC):
    """Execution abstraction for paper/live brokers."""

    @abstractmethod
    def buy_yes(self, market: Dict, amount: float) -> ExecutionResult:
        raise NotImplementedError

    @abstractmethod
    def mode(self) -> str:
        raise NotImplementedError


class PaperBroker(Broker):
    def __init__(self, wallet_file: str = "sim_wallet.json"):
        self.wallet = PaperWallet(filename=wallet_file)

    def buy_yes(self, market: Dict, amount: float) -> ExecutionResult:
        success, msg = self.wallet.buy_shares(
            market_title=market["title"],
            side="YES",
            price=float(market["price"]),
            amount=amount,
            category=market.get("category", "Other"),
            expiry_timestamp=market.get("expiry_timestamp"),
        )
        return ExecutionResult(success=success, message=msg, mode=self.mode())

    def mode(self) -> str:
        return "PAPER"


class LiveBroker(Broker):
    def __init__(self):
        # Import lazily so paper mode does not require live-trading deps.
        from secure_trader import SecureTrader

        self.trader = SecureTrader(dry_run=False)

    def buy_yes(self, market: Dict, amount: float) -> ExecutionResult:
        token_id = market.get("token_id")
        if not token_id:
            return ExecutionResult(
                success=False,
                message="token_id missing in market data for live execution",
                mode=self.mode(),
            )
        payload = self.trader.place_safe_bet(
            side="BUY",
            price=float(market["price"]),
            amount=amount,
            token_id=token_id,
        )
        return ExecutionResult(
            success=payload.get("status") == "success",
            message=payload.get("message", str(payload)),
            mode=self.mode(),
        )

    def mode(self) -> str:
        return "LIVE"
