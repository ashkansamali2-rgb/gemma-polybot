from __future__ import annotations

import math
import uuid
from abc import ABC, abstractmethod
from typing import Optional

from polybot.config import ExecutionConfig
from polybot.types import ExecutionPlan, ExecutionResult, MarketObservation
from polybot_legacy.paper_trader import PaperWallet


class ExecutionPlanner:
    def __init__(self, config: ExecutionConfig):
        self.config = config

    def plan(
        self,
        *,
        market: MarketObservation,
        calibrated_probability: float,
        uncertainty_score: float,
        stake_amount: float,
    ) -> ExecutionPlan:
        best_bid = market.best_bid if market.best_bid is not None else market.mid_price
        best_ask = market.best_ask if market.best_ask is not None else market.mid_price
        maker_fill_price = min(best_ask, best_bid + market.tick_size)
        taker_fill_price = best_ask
        depth_total = max(market.depth_bid + market.depth_ask, 1.0)
        depth_pressure = min(1.0, stake_amount / depth_total)
        partial_fill_ratio = max(
            0.1,
            min(1.0, self.config.model_partial_fill_ratio * (1.0 - depth_pressure * 0.5)),
        )
        weighted_fill = (maker_fill_price * partial_fill_ratio) + (
            taker_fill_price * (1.0 - partial_fill_ratio)
        )
        taker_fee_bps = float(
            market.fee_schedule.get("taker_bps", self.config.default_taker_fee_bps)
        )
        maker_fee_bps = float(
            market.fee_schedule.get("maker_bps", self.config.default_maker_fee_bps)
        )
        effective_fee_bps = (maker_fee_bps * partial_fill_ratio) + (
            taker_fee_bps * (1.0 - partial_fill_ratio)
        )
        fees_paid = stake_amount * (effective_fee_bps / 10000.0)
        slippage_haircut = weighted_fill * (
            (self.config.slippage_haircut_bps / 10000.0) + depth_pressure * 0.02
        )
        uncertainty_haircut = max(0.0, calibrated_probability * uncertainty_score * 0.05)
        spread_bps = 0.0
        if market.best_bid is not None and market.best_ask is not None and market.mid_price > 0:
            spread_bps = ((market.best_ask - market.best_bid) / market.mid_price) * 10000.0
        stale_quote = False
        if market.orderbook_timestamp is not None:
            stale_quote = (market.forecast_timestamp - market.orderbook_timestamp) > 90.0
        return ExecutionPlan(
            execution_mode=self.config.execution_mode,
            expected_fill_price=weighted_fill,
            maker_fill_price=maker_fill_price,
            taker_fill_price=taker_fill_price,
            fees_paid=fees_paid,
            slippage_haircut=slippage_haircut,
            uncertainty_haircut=uncertainty_haircut,
            max_cross_spread_bps=min(spread_bps, self.config.max_cross_spread_bps),
            min_remaining_edge_after_cross=self.config.min_remaining_edge_after_cross,
            stale_quote=stale_quote,
            partial_fill_ratio=partial_fill_ratio,
            cancel_replace_policy=self.config.cancel_replace_policy,
        )

    @staticmethod
    def edge_after_costs(calibrated_probability: float, plan: ExecutionPlan) -> float:
        return (
            calibrated_probability
            - plan.expected_fill_price
            - plan.fees_paid
            - plan.slippage_haircut
            - plan.uncertainty_haircut
        )


class Broker(ABC):
    @abstractmethod
    def buy_yes(
        self,
        market: MarketObservation,
        amount: float,
        execution_plan: ExecutionPlan,
        *,
        decision_id: str = "",
    ) -> ExecutionResult:
        raise NotImplementedError

    @abstractmethod
    def reduce_yes(self, market: MarketObservation, amount: float) -> ExecutionResult:
        raise NotImplementedError

    @abstractmethod
    def mode(self) -> str:
        raise NotImplementedError


class PaperBroker(Broker):
    def __init__(self, wallet_file: str = "state/sim_wallet.json"):
        self.wallet = PaperWallet(filename=wallet_file)

    def buy_yes(
        self,
        market: MarketObservation,
        amount: float,
        execution_plan: ExecutionPlan,
        *,
        decision_id: str = "",
    ) -> ExecutionResult:
        fee_rate = (execution_plan.fees_paid / amount) if amount > 0 else 0.0
        success, msg = self.wallet.buy_shares(
            market_title=market.title,
            side="YES",
            price=execution_plan.expected_fill_price,
            amount=amount,
            category=market.category,
            expiry_timestamp=market.expiry_timestamp,
            fee_rate=fee_rate,
            market_id=market.market_id,
            event_id=market.event_id,
            token_id=market.token_id,
            execution_mode=execution_plan.execution_mode,
            expected_fill_price=execution_plan.expected_fill_price,
            decision_id=decision_id,
        )
        return ExecutionResult(
            success=success,
            message=msg,
            mode=self.mode(),
            filled_amount=amount if success else 0.0,
            fill_price=execution_plan.expected_fill_price if success else None,
            fees_paid=execution_plan.fees_paid if success else 0.0,
            order_id=uuid.uuid4().hex[:12],
            decision_id=decision_id,
        )

    def reduce_yes(self, market: MarketObservation, amount: float) -> ExecutionResult:
        success, msg = self.wallet.reduce_position(
            market_id=market.market_id,
            sell_price=market.best_bid if market.best_bid is not None else market.mid_price,
            amount=amount,
        )
        return ExecutionResult(success=success, message=msg, mode=self.mode())

    def mode(self) -> str:
        return "PAPER"


class LiveBroker(Broker):
    def __init__(self):
        from polybot_legacy.secure_trader import SecureTrader

        self.trader = SecureTrader(dry_run=False)

    def buy_yes(
        self,
        market: MarketObservation,
        amount: float,
        execution_plan: ExecutionPlan,
        *,
        decision_id: str = "",
    ) -> ExecutionResult:
        token_id = market.token_id
        if not token_id:
            return ExecutionResult(
                success=False,
                message="token_id missing in market data for live execution",
                mode=self.mode(),
                decision_id=decision_id,
            )
        if execution_plan.stale_quote:
            return ExecutionResult(
                success=False,
                message="stale orderbook blocked live execution",
                mode=self.mode(),
                decision_id=decision_id,
            )
        payload = self.trader.place_safe_bet(
            side="BUY",
            price=float(execution_plan.expected_fill_price),
            amount=amount,
            token_id=token_id,
        )
        return ExecutionResult(
            success=payload.get("status") == "success",
            message=payload.get("message", str(payload)),
            mode=self.mode(),
            filled_amount=amount if payload.get("status") == "success" else 0.0,
            fill_price=execution_plan.expected_fill_price if payload.get("status") == "success" else None,
            fees_paid=execution_plan.fees_paid if payload.get("status") == "success" else 0.0,
            order_id=str(payload.get("order_id", uuid.uuid4().hex[:12])),
            decision_id=decision_id,
        )

    def reduce_yes(self, market: MarketObservation, amount: float) -> ExecutionResult:
        return ExecutionResult(
            success=False,
            message="inventory reduction not implemented for live broker",
            mode=self.mode(),
        )

    def mode(self) -> str:
        return "LIVE"

