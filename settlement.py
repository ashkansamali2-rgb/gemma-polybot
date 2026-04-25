import requests
import json
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

def check_resolution(market_title):
    """
    Queries Gamma API to find the resolution status of a market.
    """
    # Clean the title per instructions
    clean_title = market_title.replace('...', '').replace('?', '').strip()
    
    # Search for the market by title, filtering for closed markets
    url = "https://gamma-api.polymarket.com/markets"
    params = {"q": clean_title, "closed": "true"}
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        markets = response.json()
        
        for m in markets:
            # Check if clean_title is in the API market title (usually 'question' or 'title')
            api_title = m.get("question", m.get("title", "")).lower()
            
            if clean_title.lower() in api_title:
                # Confirm resolution: Some markets have closed: True but resolved: None
                # We also check if an outcome is present or if outcomePrices indicate resolution
                is_closed = m.get("closed") is True
                outcome = m.get("outcome")
                outcome_prices = json.loads(m.get("outcomePrices", "[]"))
                
                # If closed and we have outcome prices like ["1", "0"] or ["0", "1"], it's resolved
                if is_closed:
                    outcomes_str = m.get("outcomes", '["Yes", "No"]')
                    try:
                        outcomes = json.loads(outcomes_str)
                    except:
                        outcomes = ["YES", "NO"]

                    # Option 1: Explicit outcome index
                    if outcome is not None:
                        try:
                            idx = int(outcome)
                            winning_side = outcomes[idx].upper()
                            return True, winning_side
                        except (ValueError, IndexError):
                            pass
                    
                    # Option 2: outcomePrices are ["1", "0"], ["0", "1"], or even ["0", "0"] (which sometimes happens on old markets)
                    if outcome_prices:
                        try:
                            # If YES price is 0 and market is closed, it's a NO resolution (often)
                            # If NO price is 1, it's a NO resolution
                            yes_price = float(outcome_prices[0])
                            no_price = float(outcome_prices[1]) if len(outcome_prices) > 1 else 0
                            
                            if yes_price == 1:
                                winning_side = outcomes[0].upper()
                                return True, winning_side
                            elif no_price == 1 or (yes_price == 0 and is_closed):
                                # If Yes is 0, then NO must have won (or it was a draw/void, but usually NO)
                                winning_side = outcomes[1].upper() if len(outcomes) > 1 else "NO"
                                return True, winning_side
                        except (ValueError, IndexError):
                            pass
        return False, None
    except Exception as e:
        print(f"Error checking API for {market_title}: {e}")
        return False, None

def run_settlement():
    wallet = PaperWallet()
    positions = wallet.state.get("positions", [])
    
    if not positions:
        print(f"{Y}No active positions to settle.{C}")
        return

    print(f"{BOLD}{B}INITIATING SETTLEMENT PROTOCOL...{C}\n")
    
    # We need to iterate over a copy because settle_market modifies the list
    to_settle = []
    
    for pos in positions:
        title = pos["market_title"]
        print(f"Checking: {title}...")
        resolved, winning_side = check_resolution(title)
        
        if resolved:
            to_settle.append((title, winning_side, pos))
        else:
            print(f" - Still active or not found in API.")

    total_payout = 0
    
    for title, winning_side, pos in to_settle:
        shares = pos["shares"]
        entry = int(pos["price"] * 100)
        
        success, msg = wallet.settle_market(title, winning_side)
        if success:
            # The wallet settle_market already updated the state
            # We need to know if we won or lost for the receipt
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
