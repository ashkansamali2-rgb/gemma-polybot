from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from polybot.paths import STATE_DIR
from polybot_infra.engine import PolyEngine


def run_system_check():
    print("--- Starting System Check ---")

    try:
        with open(STATE_DIR / "sim_wallet.json", "r", encoding="utf-8") as f:
            wallet_data = json.load(f)
            balance = wallet_data.get("balance", "N/A")
            print(f"[WALLET] Live Balance: {balance}")
    except Exception as e:
        print(f"[WALLET] Error loading wallet: {e}")

    print("[ENGINE] Initializing PolyEngine...")
    try:
        engine = PolyEngine()
        print("[ENGINE] Model and adapters loaded successfully.")
    except Exception as e:
        print(f"[ENGINE] Error initializing engine: {e}")
        return

    print("[INFERENCE] Running dummy prompt...")
    try:
        dummy_data = {
            "title": "SYSTEM_CHECK",
            "odds": "N/A",
            "news": "N/A",
            "initial_thought": "Respond with exactly: CONNECTION_STABLE",
        }
        response = engine.analyze(dummy_data)
        print(f"[INFERENCE] Response: {response.strip()}")

        if "CONNECTION_STABLE" in response:
            print("[STATUS] ALL SYSTEMS ONLINE")
        else:
            print("[STATUS] UNEXPECTED RESPONSE - CHECK MODEL OUTPUT")
    except Exception as e:
        print(f"[INFERENCE] Error during inference: {e}")


if __name__ == "__main__":
    run_system_check()
