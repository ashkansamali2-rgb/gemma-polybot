from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from polybot_infra.secure_trader import DRY_RUN, SecureTrader


if __name__ == "__main__":
    trader = SecureTrader(dry_run=DRY_RUN)
    test_token = "7694489310729391738711511102048711130300200451903174214123216618230210212345"
    trader.place_safe_bet(
        side="BUY",
        price=0.50,
        amount=10,
        token_id=test_token,
    )
