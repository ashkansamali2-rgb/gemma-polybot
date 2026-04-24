import time
import random
import json
from engine import PolyEngine
from paper_trader import PaperWallet

# --- CONFIG ---
POLLING_INTERVAL = 900  # 15 minutes
EDGE_THRESHOLD = 0.15   # 15% Edge
STAKE_AMOUNT = 1.00     # €1.00 per trade

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
    Simulates fetching top Geopolitics/Sports markets from Polymarket.
    In a production scenario, this would use requests to hit Polymarket's Gamma API.
    """
    mock_markets = [
        {"title": "Will there be a ceasefire in Ukraine by July?", "category": "Geopolitics", "expiry_hours": 60, "odds": "35%"},
        {"title": "Lakers vs Nuggets: Who wins Game 5?", "category": "Sports", "expiry_hours": 12, "odds": "55%"},
        {"title": "Will Bitcoin hit $100k before May?", "category": "Crypto", "expiry_hours": 72, "odds": "48%"},
        {"title": "Will France win the Euro 2026?", "category": "Sports", "expiry_hours": 500, "odds": "15%"},
        {"title": "US Presidential Election: Trump vs Biden?", "category": "Geopolitics", "expiry_hours": 4000, "odds": "50%"}
    ]
    # Filter for Geopolitics/Sports and Expiry < 72h
    filtered = [m for m in mock_markets if m["category"] in ["Geopolitics", "Sports"] and m["expiry_hours"] < 72]
    return filtered

def run_autopilot():
    log_quantum("INITIATING_QUANTUM_AUTOPILOT...", B)
    engine = PolyEngine()
    wallet = PaperWallet()
    
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
                    price=0.50, # Mock price
                    amount=STAKE_AMOUNT,
                    category=m["category"]
                )
                if success:
                    log_quantum(f"TRADE_EXECUTED: {m['title']} | {msg}", G)
                else:
                    log_quantum(f"TRADE_FAILED: {msg}", R)
            else:
                log_quantum(f"HOLD: Edge {edge:.1%} below threshold.", Y)
        
        log_quantum(f"CYCLE_COMPLETE. CURRENT_BALANCE: €{wallet.get_balance():.2f}", B)
        log_quantum(f"SLEEPING_FOR_{POLLING_INTERVAL // 60}_MINUTES...", C)
        time.sleep(POLLING_INTERVAL)

if __name__ == "__main__":
    try:
        run_autopilot()
    except KeyboardInterrupt:
        log_quantum("AUTOPILOT_SHUTDOWN_BY_USER.", R)
