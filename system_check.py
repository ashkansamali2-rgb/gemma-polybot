import json
from engine import PolyEngine

def run_system_check():
    print("--- Starting System Check ---")

    # 1. Load sim_wallet.json and print live balance
    try:
        with open("sim_wallet.json", "r") as f:
            wallet_data = json.load(f)
            balance = wallet_data.get("balance", "N/A")
            print(f"[WALLET] Live Balance: {balance}")
    except Exception as e:
        print(f"[WALLET] Error loading wallet: {e}")

    # 2. Initialize PolyEngine
    print("[ENGINE] Initializing PolyEngine...")
    try:
        # Using default paths as defined in engine.py
        engine = PolyEngine()
        print("[ENGINE] Model and adapters loaded successfully.")
    except Exception as e:
        print(f"[ENGINE] Error initializing engine: {e}")
        return

    # 3. Run dummy prompt
    print("[INFERENCE] Running dummy prompt...")
    try:
        # PolyEngine.analyze expects a dict. We'll pass one that directs it to the dummy response.
        # Although analyze() formats its own prompt, we can see if it respects the user request.
        dummy_data = {
            "title": "SYSTEM_CHECK",
            "odds": "N/A",
            "news": "N/A",
            "initial_thought": "Respond with exactly: CONNECTION_STABLE"
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
