import json
import os
from pathlib import Path

from polybot.paths import STATE_DIR


class PaperWallet:
    def __init__(self, filename=None):
        self.filename = filename or str(STATE_DIR / "sim_wallet.json")
        self.state = self._load_state()

    def _load_state(self):
        if not os.path.exists(self.filename):
            initial_state = {
                "balance": 5.00,
                "positions": [],
                "settled": [],
            }
            self._save_state(initial_state)
            return initial_state
        with open(self.filename, "r", encoding="utf-8") as f:
            state = json.load(f)
            if "settled" not in state:
                state["settled"] = []
            return state

    def _save_state(self, state=None):
        if state:
            self.state = state
        Path(self.filename).parent.mkdir(parents=True, exist_ok=True)
        with open(self.filename, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=4)

    def get_fee_rate(self, category):
        cat = category.lower()
        if "geopolitics" in cat:
            return 0.0
        if "sports" in cat:
            return 0.0075
        if "crypto" in cat:
            return 0.015
        return 0.01

    def buy_shares(
        self,
        market_title,
        side,
        price,
        amount,
        category,
        expiry_timestamp=None,
        *,
        fee_rate=None,
        market_id=None,
        event_id=None,
        token_id=None,
        execution_mode="",
        expected_fill_price=None,
        decision_id="",
    ):
        fee_rate = self.get_fee_rate(category) if fee_rate is None else fee_rate
        fee = amount * fee_rate
        total_cost = amount + fee

        if self.state["balance"] < total_cost:
            return False, "INSUFFICIENT_FUNDS"

        shares = amount / price if price > 0 else 0

        self.state["balance"] -= total_cost
        self.state["positions"].append(
            {
                "market_title": market_title,
                "side": side,
                "price": price,
                "amount": amount,
                "shares": shares,
                "category": category,
                "fee": fee,
                "expiry_timestamp": expiry_timestamp,
                "market_id": market_id,
                "event_id": event_id,
                "token_id": token_id,
                "execution_mode": execution_mode,
                "expected_fill_price": expected_fill_price if expected_fill_price is not None else price,
                "decision_id": decision_id,
            }
        )
        self._save_state()
        return True, f"BOUGHT {shares:.2f} SHARES | FEE: EUR{fee:.4f}"

    def reduce_position(self, market_id, sell_price, amount):
        if amount <= 0:
            return False, "INVALID_REDUCTION_SIZE"

        remaining = amount
        updated_positions = []
        realized = 0.0
        found = False

        for pos in self.state["positions"]:
            if pos.get("market_id") != market_id or remaining <= 0:
                updated_positions.append(pos)
                continue

            found = True
            current_amount = float(pos.get("amount", 0.0))
            current_shares = float(pos.get("shares", 0.0))
            if current_amount <= remaining + 1e-9:
                realized += current_shares * sell_price
                remaining -= current_amount
                settled_entry = pos.copy()
                settled_entry["result"] = "REDUCED"
                settled_entry["payout"] = current_shares * sell_price
                self.state.setdefault("settled", []).append(settled_entry)
                continue

            ratio = remaining / current_amount
            sold_shares = current_shares * ratio
            realized += sold_shares * sell_price
            pos["amount"] = current_amount - remaining
            pos["shares"] = current_shares - sold_shares
            updated_positions.append(pos)
            settled_entry = pos.copy()
            settled_entry["amount"] = amount
            settled_entry["shares"] = sold_shares
            settled_entry["result"] = "REDUCED"
            settled_entry["payout"] = sold_shares * sell_price
            self.state.setdefault("settled", []).append(settled_entry)
            remaining = 0.0

        if not found:
            return False, "MARKET_NOT_FOUND"

        self.state["balance"] += realized
        self.state["positions"] = updated_positions
        self._save_state()
        return True, f"REDUCED | CREDIT: EUR{realized:.2f}"

    def settle_market(self, market_title, winning_side):
        updated_positions = []
        payout = 0
        found = False

        for pos in self.state["positions"]:
            if pos["market_title"] == market_title:
                found = True
                is_win = pos["side"].lower() == winning_side.lower()
                if is_win:
                    payout += pos["shares"]

                settled_entry = pos.copy()
                settled_entry["result"] = "WON" if is_win else "LOST"
                settled_entry["payout"] = pos["shares"] if is_win else 0
                self.state.setdefault("settled", []).append(settled_entry)
            else:
                updated_positions.append(pos)

        if found:
            self.state["balance"] += payout
            self.state["positions"] = updated_positions
            self._save_state()
            return True, f"SETTLED | PAYOUT: EUR{payout:.2f}"
        return False, "MARKET_NOT_FOUND"

    def get_balance(self):
        return self.state["balance"]
