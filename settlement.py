import json
import requests
import time
from paper_trader import PaperWallet

# --- TERMINAL STYLING ---
G = "\033[92m"  # Green
Y = "\033[93m"  # Yellow
B = "\033[94m"  # Blue
R = "\033[91m"  # Red
C = "\033[0m"   # Reset
BOLD = "\033[1m"
GLOW = "\033[1;97;48;5;208m" # High contrast orange-ish bg

def log_receipt(title, shares, entry, payout, result):
    color = G if result == "WON" else R
    print(f"{BOLD}{'='*60}{C}")
    print(f"{BOLD}SETTLEMENT RECEIPT:{C}")
    print(f"MARKET: {Y}{title}{C}")
    print(f"SHARES: {shares:.2f} | ENTRY: {entry}¢")
    print(f"RESULT: {color}{BOLD}{result}{C}")
    print(f"PAYOUT: {color}€{payout:.2f}{C}")
    print(f"{BOLD}{'='*60}{C}\n")

def run_settlement():
    wallet = PaperWallet()
    positions = wallet.state.get("positions", [])
    
    if not positions:
        print(f"{Y}No active positions to settle.{C}")
        return

    print(f"{BOLD}{B}INITIATING SETTLEMENT PROTOCOL...{C}\n")
    
    to_settle = []
    
    for pos in positions:
        title = pos["market_title"]
        print(f"Checking: {title}...")
        
        try:
            response = requests.get(
                'https://gamma-api.polymarket.com/markets', 
                params={'query': title, 'closed': 'true', 'active': 'false'}
            )
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            print(f"Error fetching API for {title}: {e}")
            continue
            
        if data:
            api_market = data[0]
            
            # Check if resolved (or equivalent closed status)
            is_resolved = api_market.get("resolved") is True or api_market.get("closed") is True
            
            if is_resolved:
                outcome = api_market.get("outcome")
                outcome_prices = json.loads(api_market.get("outcomePrices", "[]"))
                winning_side = None
                
                outcomes_str = api_market.get("outcomes", '["Yes", "No"]')
                try:
                    outcomes = json.loads(outcomes_str)
                except:
                    outcomes = ["YES", "NO"]

                # Option 1: Explicit outcome index
                if outcome is not None:
                    try:
                        idx = int(outcome)
                        winning_side = outcomes[idx].upper()
                    except (ValueError, IndexError):
                        pass
                
                # Option 2: Check outcomePrices
                if winning_side is None and outcome_prices:
                    try:
                        yes_price = float(outcome_prices[0])
                        no_price = float(outcome_prices[1]) if len(outcome_prices) > 1 else 0
                        
                        if yes_price == 1:
                            winning_side = outcomes[0].upper()
                        elif no_price == 1 or (yes_price == 0 and is_resolved):
                            winning_side = outcomes[1].upper() if len(outcomes) > 1 else "NO"
                    except (ValueError, IndexError):
                        pass
                
                if winning_side:
                    to_settle.append((title, winning_side, pos))
                else:
                    print(" - Market found but Oracle is still resolving.")
            else:
                print(" - Market found but Oracle is still resolving.")
        else:
            print(" - Could not find closed market.")

    total_payout = 0
    
    for title, winning_side, pos in to_settle:
        shares = pos["shares"]
        entry = int(pos["price"] * 100)
        
        success, msg = wallet.settle_market(title, winning_side)
        if success:
            is_win = pos["side"].upper() == winning_side.upper()
            result = "WON" if is_win else "LOST"
            payout = shares if is_win else 0.0
            total_payout += payout
            
            log_receipt(title, shares, entry, payout, result)

    if to_settle:
        print(f"{GLOW} TOTAL SETTLEMENT PAYOUT: €{total_payout:.2f} {C}")
    else:
        print(f"{Y}No markets resolved in this cycle.{C}")

if __name__ == "__main__":
    run_settlement()