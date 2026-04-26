import time
import random
import json
import sys
import subprocess
import re
from datetime import datetime, date
from engine import PolyEngine
from paper_trader import PaperWallet
from polymarket_api import fetch_live_polymarket_data

# --- CONFIG ---
POLLING_INTERVAL = 300  # 5 minutes
EDGE_THRESHOLD = 0.15   # 15% Edge
STAKE_AMOUNT = 1.00     # Strictly €1.00 per trade
DAILY_LIMIT = 5

# --- AGENT PROMPTS ---
BULL_PROMPT_TEMPLATE = (
    "<|im_start|>system\nAct as a bullish aggressive analyst.<|im_end|>\n"
    "<|im_start|>user\nGiven the market title '{title}' and live search context below, "
    "write a ruthless 1-paragraph thesis on why this event WILL happen. Ignore all doubts.\n\n"
    "LIVE CONTEXT:\n{context}<|im_end|>\n"
    "<|im_start|>assistant\n"
)

BEAR_PROMPT_TEMPLATE = (
    "<|im_start|>system\nAct as a highly skeptical risk manager.<|im_end|>\n"
    "<|im_start|>user\nGiven the same market title '{title}' and context below, "
    "write a ruthless 1-paragraph thesis on why this event WILL FAIL. Focus on flaws in the Bull thesis.\n\n"
    "BULL THESIS:\n{bull_thesis}\n\n"
    "LIVE CONTEXT:\n{context}<|im_end|>\n"
    "<|im_start|>assistant\n"
)

JUDGE_PROMPT_TEMPLATE = (
    "<|im_start|>system\nAct as the Lead Quantitative Manager.<|im_end|>\n"
    "<|im_start|>user\nReview the Bull Thesis and the Bear Thesis below. Compare them against the current Polymarket odds ({odds}). "
    "Weigh the risk, find the true edge, and output your final verdict. "
    "You must end your response with EXACTLY: FINAL_PROBABILITY: [XX]%.\n\n"
    "MARKET: {title}\n"
    "BULL THESIS: {bull_thesis}\n"
    "BEAR THESIS: {bear_thesis}<|im_end|>\n"
    "<|im_start|>assistant\n"
)

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

def extract_probability(text):
    """Extracts the percentage from the FINAL_PROBABILITY: [XX]% format."""
    match = re.search(r'FINAL_PROBABILITY:\s*\[?(\d+(?:\.\d+)?)\]?%', text)
    if match:
        return float(match.group(1)) / 100.0
    return None

def fetch_top_markets():
    """
    Fetches real markets from Polymarket's Gamma API.
    Filters for short-term expiration (0 < expiry_hours <= 24).
    """
    markets = fetch_live_polymarket_data(limit=1000)
    markets.sort(key=lambda x: x['expiry_hours'])
    return markets

def run_autopilot():
    log_quantum("INITIATING_MULTI_AGENT_DEBATE_AUTOPILOT...", B)
    engine = PolyEngine()
    wallet = PaperWallet()
    
    last_trade_date = None
    daily_trades = 0
    
    while True:
        today = date.today()
        if last_trade_date != today:
            log_quantum(f"NEW_DAY_DETECTED: {today}. RESETTING_DAILY_BATCH.", G)
            last_trade_date = today
            daily_trades = 0
            subprocess.run(['python3', 'settlement.py'])

        if daily_trades >= DAILY_LIMIT:
            log_quantum(f"[DAILY BATCH COMPLETE. HIBERNATING UNTIL TOMORROW...]", Y)
            time.sleep(3600)
            continue

        log_quantum(f"SCANNING_MARKETS... (DAILY_PROGRESS: {daily_trades}/{DAILY_LIMIT})", Y)
        markets = fetch_top_markets()
        
        for m in markets:
            if daily_trades >= DAILY_LIMIT:
                break

            print(f'\n{BOLD}[SYSTEM] Analyzing Market: {m["title"]}{C}')
            
            # 1. Bull Agent
            print(f"{Y}[SYSTEM] Spawning Bull Agent...{C}")
            context = f"Odds are {m['odds']}. Volume: ${m['volume']:,.0f}"
            bull_prompt = BULL_PROMPT_TEMPLATE.format(title=m["title"], context=context)
            bull_thesis = engine.analyze(m, raw_prompt=bull_prompt)
            print(f"{G}Bull Thesis: {bull_thesis[:200]}...{C}")

            # 2. Bear Agent
            print(f"{Y}[SYSTEM] Spawning Bear Agent...{C}")
            bear_prompt = BEAR_PROMPT_TEMPLATE.format(title=m["title"], context=context, bull_thesis=bull_thesis)
            bear_thesis = engine.analyze(m, raw_prompt=bear_prompt)
            print(f"{R}Bear Thesis: {bear_thesis[:200]}...{C}")

            # 3. Judge Agent
            print(f"{Y}[SYSTEM] The Judge is evaluating odds...{C}")
            judge_prompt = JUDGE_PROMPT_TEMPLATE.format(
                title=m["title"], 
                odds=m["odds"], 
                bull_thesis=bull_thesis, 
                bear_thesis=bear_thesis
            )
            final_analysis = engine.analyze(m, raw_prompt=judge_prompt)
            print(f"{B}--- JUDGE VERDICT ---{C}\n{final_analysis}\n{B}---------------------{C}")

            # Extraction and Execution
            ai_prob = extract_probability(final_analysis)
            market_price = m["price"]
            
            if ai_prob is not None:
                edge = ai_prob - market_price
                log_quantum(f"AI_PROB: {ai_prob:.1%} | MARKET: {market_price:.1%} | EDGE: {edge:.1%}", Y)
                
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
                        log_quantum(f"TRADE_EXECUTED: {msg}", G)
                        daily_trades += 1
                    else:
                        log_quantum(f"TRADE_FAILED: {msg}", R)
                else:
                    log_quantum(f"HOLD: Edge {edge:.1%} below threshold.", Y)
            else:
                log_quantum("FAILED_TO_PARSE_PROBABILITY.", R)
        
        log_quantum(f"CYCLE_COMPLETE. CURRENT_BALANCE: €{wallet.get_balance():.2f}", B)
        time.sleep(POLLING_INTERVAL)

if __name__ == "__main__":
    try:
        run_autopilot()
    except KeyboardInterrupt:
        log_quantum("AUTOPILOT_SHUTDOWN_BY_USER.", R)
