import time
import random
import json
import sys
from engine import PolyEngine
from paper_trader import PaperWallet

# --- CONFIG ---
POLLING_INTERVAL = 300  # 5 minutes
EDGE_THRESHOLD = 0.15   # 15% Edge
STAKE_AMOUNT = 0.60     # Exactly €0.60 per trade

# --- TERMINAL STYLING ---
G = "\033[92m"  # Green
Y = "\033[93m"  # Yellow
B = "\033[94m"  # Blue
R = "\033[91m"  # Red
C = "\033[0m"   # Reset
BOLD = "\033[1m"

def log_quantum(msg, color=G):
    timestamp = time.strftime("%H:%M:%S")
    print(f"{BOLD}[{timestamp}] {color}{msg}{C}")

from polymarket_api import fetch_live_polymarket_data

def fetch_top_markets():
    """
    Fetches real markets from Polymarket's Gamma API.
    """
    markets = fetch_live_polymarket_data(limit=20)
    # Filter for Geopolitics/Sports/Other and Expiry < 72h
    # Polymarket category might vary, so we just use the live data.
    filtered = [m for m in markets if m["expiry_hours"] < 72]
    return filtered

def run_autopilot():
    log_quantum("INITIATING_QUANTUM_AUTOPILOT...", B)
    engine = PolyEngine()
    wallet = PaperWallet()
    trades_completed = 0
    
    while True:
        log_quantum("SCANNING_MARKETS...", Y)
        markets = fetch_top_markets()
        
        if not markets:
            log_quantum("NO_QUALIFIED_MARKETS_FOUND. SLEEPING...", Y)
        
        for m in markets:
            log_quantum(f"ANALYZING: {m['title']}...", B)
            
            # Analyze using Qwen 27B engine
            analysis = engine.analyze(m)
            
            # Simulated edge detection from analysis text
            # In real use, we'd parse the model's structured output
            # For this pilot, we simulate the model finding an edge
            edge = random.uniform(0.05, 0.25)
            
            if edge > EDGE_THRESHOLD:
                log_quantum(f"EDGE_DETECTED: {edge:.1%} | SIGNAL: BUY", G)
                success, msg = wallet.buy_shares(
                    market_title=m["title"],
                    side="YES",
                    price=m["price"],
                    amount=STAKE_AMOUNT,
                    category=m["category"],
                    expiry_timestamp=m.get("expiry_timestamp")
                )
                if success:
                    log_quantum(f"TRADE_EXECUTED: {m['title']} | {msg}", G)
                    trades_completed += 1
                    if trades_completed >= 5:
                        log_quantum("🛑 DAILY LIMIT OF 5 TRADES REACHED. SHUTTING DOWN.", R)
                        sys.exit()
                else:
                    log_quantum(f"TRADE_FAILED: {msg}", R)
            else:
                log_quantum(f"HOLD: Edge {edge:.1%} below threshold.", Y)
        
        log_quantum(f"CYCLE_COMPLETE. TRADES_TODAY: {trades_completed}/5 | CURRENT_BALANCE: €{wallet.get_balance():.2f}", B)
        log_quantum(f"SLEEPING_FOR_{POLLING_INTERVAL // 60}_MINUTES...", C)
        time.sleep(POLLING_INTERVAL)

if __name__ == "__main__":
    try:
        run_autopilot()
    except KeyboardInterrupt:
        log_quantum("AUTOPILOT_SHUTDOWN_BY_USER.", R)
