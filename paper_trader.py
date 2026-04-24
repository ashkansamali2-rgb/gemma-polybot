import json
import os

class PaperWallet:
    def __init__(self, filename="sim_wallet.json"):
        self.filename = filename
        self.state = self._load_state()

    def _load_state(self):
        if not os.path.exists(self.filename):
            initial_state = {
                "balance": 5.00,
                "positions": []
            }
            self._save_state(initial_state)
            return initial_state
        with open(self.filename, "r") as f:
            return json.load(f)

    def _save_state(self, state=None):
        if state:
            self.state = state
        with open(self.filename, "w") as f:
            json.dump(self.state, f, indent=4)

    def get_fee_rate(self, category):
        cat = category.lower()
        if "geopolitics" in cat:
            return 0.0
        if "sports" in cat:
            return 0.0075
        if "crypto" in cat:
            return 0.015
        return 0.01 # Default 1%

    def buy_shares(self, market_title, side, price, amount, category):
        fee_rate = self.get_fee_rate(category)
        fee = amount * fee_rate
        total_cost = amount + fee

        if self.state["balance"] < total_cost:
            return False, "INSUFFICIENT_FUNDS"

        shares = amount / price if price > 0 else 0
        
        self.state["balance"] -= total_cost
        self.state["positions"].append({
            "market_title": market_title,
            "side": side,
            "price": price,
            "amount": amount,
            "shares": shares,
            "category": category,
            "fee": fee
        })
        self._save_state()
        return True, f"BOUGHT {shares:.2f} SHARES | FEE: €{fee:.4f}"

    def settle_market(self, market_title, winning_side):
        updated_positions = []
        payout = 0
        found = False

        for pos in self.state["positions"]:
            if pos["market_title"] == market_title:
                found = True
                if pos["side"].lower() == winning_side.lower():
                    # Pays out $1.00 per share
                    payout += pos["shares"]
                # If incorrect, it's just removed (loss already deducted at buy)
            else:
                updated_positions.append(pos)
        
        if found:
            self.state["balance"] += payout
            self.state["positions"] = updated_positions
            self._save_state()
            return True, f"SETTLED | PAYOUT: €{payout:.2f}"
        return False, "MARKET_NOT_FOUND"

    def get_balance(self):
        return self.state["balance"]
