import logging
import os
from datetime import datetime

from dotenv import load_dotenv
from polymarket_apis import PolymarketClobClient

from polybot.paths import LOGS_DIR


load_dotenv()
LOGS_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOGS_DIR / "trading.log"),
        logging.StreamHandler(),
    ],
)

POLYMARKET_PK = os.getenv("POLYMARKET_PK")
POLYMARKET_ADDRESS = os.getenv("POLYMARKET_ADDRESS")
DRY_RUN = os.getenv("DRY_RUN", "True").lower() == "true"

if not POLYMARKET_PK and not DRY_RUN:
    raise ValueError("POLYMARKET_PK environment variable is required for live trading.")


class SecureTrader:
    def __init__(self, dry_run=True):
        self.dry_run = dry_run
        self.client = None

        if not self.dry_run:
            if not POLYMARKET_PK or not POLYMARKET_ADDRESS:
                logging.error("Missing credentials for live trading.")
                self.dry_run = True
            else:
                try:
                    self.client = PolymarketClobClient(
                        private_key=POLYMARKET_PK,
                        address=POLYMARKET_ADDRESS,
                    )
                    self.client.set_api_creds(self.client.create_or_derive_api_creds())
                    logging.info("Connected to Polymarket CLOB (LIVE MODE)")
                except Exception as e:
                    logging.error(f"Failed to initialize Polymarket client: {e}")
                    self.dry_run = True

        if self.dry_run:
            logging.info("Initialized in DRY RUN mode (Paper Trading)")

    def place_safe_bet(self, side, price, amount, token_id=None):
        if not token_id:
            logging.error("token_id is required to place a bet.")
            return {"status": "error", "message": "token_id is required"}

        trade_info = {
            "timestamp": datetime.now().isoformat(),
            "side": side,
            "price": price,
            "amount": amount,
            "token_id": token_id,
            "mode": "DRY_RUN" if self.dry_run else "LIVE",
        }

        if self.dry_run:
            self._log_paper_trade(trade_info)
            return {"status": "success", "message": "Paper trade logged", "data": trade_info}

        try:
            logging.info(f"Placing LIVE order: {side} {amount} shares at {price}")
            order = self.client.create_order(
                token_id=token_id,
                price=price,
                side=side,
                size=amount,
            )
            logging.info(f"Order placed successfully: {order}")
            return {"status": "success", "data": order}
        except Exception as e:
            logging.error(f"Failed to place live order: {e}")
            return {"status": "error", "message": str(e)}

    def _log_paper_trade(self, trade_info):
        log_file = LOGS_DIR / "paper_trades.log"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(
                f"{trade_info['timestamp']} | {trade_info['side']} | {trade_info['token_id']} | "
                f"Price: {trade_info['price']} | Amount: {trade_info['amount']}\n"
            )
        logging.info(
            f"DRY RUN: {trade_info['side']} {trade_info['amount']} @ {trade_info['price']} "
            f"for {trade_info['token_id']}"
        )
