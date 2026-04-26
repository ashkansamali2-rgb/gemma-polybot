import time
import random
import json
import sys
import subprocess
from datetime import datetime, date
from engine import PolyEngine
from paper_trader import PaperWallet
from polymarket_api import fetch_live_polymarket_data

# --- CONFIG ---
POLLING_INTERVAL = 300  # 5 minutes
EDGE_THRESHOLD = 0.15   # 15% Edge
STAKE_AMOUNT = 1.00     # Strictly €1.00 per trade
DAILY_LIMIT = 5

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

def fetch_top_markets():
    """
    Fetches real markets from Polymarket's Gamma API.
    Filters for short-term expiration (0 < expiry_hours <= 24).
    """
    markets = fetch_live_polymarket_data(limit=1000)
    markets.sort(key=lambda x: x['expiry_hours'])
    return markets

def run_autopilot():
    log_quantum("INITIATING_DAILY_SNIPER_AUTOPILOT...", B)
    engine = PolyEngine()
    wallet = PaperWallet()
    
    last_trade_date = None
    daily_trades = 0
    
    while True:
        # Date-Aware Hibernation Check
        today = date.today()
        if last_trade_date != today:
            log_quantum(f"NEW_DAY_DETECTED: {today}. RESETTING_DAILY_BATCH.", G)
            last_trade_date = today
            daily_trades = 0
            
            print('\n[SYSTEM] Waking up. Running daily settlement check...')
            subprocess.run(['python3', 'settlement.py'])

        if daily_trades >= DAILY_LIMIT:
            log_quantum(f"[DAILY BATCH COMPLETE. HIBERNATING UNTIL TOMORROW...]", Y)
            time.sleep(3600) # Sleep for 1 hour then check date again
            continue

        log_quantum(f"SCANNING_MARKETS... (DAILY_PROGRESS: {daily_trades}/{DAILY_LIMIT})", Y)
        markets = fetch_top_markets()
        
        if not markets:
            log_quantum("NO_QUALIFIED_MARKETS_FOUND (<= 24H). SLEEPING...", Y)
        
        for m in markets:
            if daily_trades >= DAILY_LIMIT:
                break

            print(f'[SYSTEM] Analyzing market resolving in {m["expiry_hours"]:.1f}h: {m["title"]}')
            
            # Analyze using Qwen 27B engine
            analysis = engine.analyze(m)
            
            # Simulated edge detection
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
                    daily_trades += 1
                else:
                    log_quantum(f"TRADE_FAILED: {msg}", R)
            else:
                log_quantum(f"HOLD: Edge {edge:.1%} below threshold.", Y)
        
        log_quantum(f"CYCLE_COMPLETE. CURRENT_BALANCE: €{wallet.get_balance():.2f}", B)
        time.sleep(POLLING_INTERVAL)

if __name__ == "__main__":
    try:
        run_autopilot()
    except KeyboardInterrupt:
        log_quantum("AUTOPILOT_SHUTDOWN_BY_USER.", R)
