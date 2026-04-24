import json
import os
import re
from engine import PolyEngine

# Ground Truth Mapping for our Trap Scenarios
# 1: Event Happens (YES), 0: Event Fails (NO), 0.5: Pure Toss-up
TRAP_GROUND_TRUTH = {
    "Will Company Z's CEO be re-elected?": 0.0,  # Toxic News: Board hates him
    "Will the coin land Heads? (Special Polymarket Event)": 0.5, # Misleading Math: Fair coin
    "Will 'Obscure Token' reach $1.00 by Sunday?": 0.0, # Low Liquidity: Impossible to buy enough
    "Will Crypto Exchange Alpha get its license?": 0.0, # Regulatory: Criminal probe
}

def calculate_brier_score(forecast, outcome):
    """Calculates (f - o)^2"""
    return (forecast - outcome) ** 2

def extract_probability(text):
    """Extracts a decimal probability from the model's response."""
    # Look for patterns like "Probability: 0.85" or "Confidence in YES: 10%"
    match = re.search(r"(?:probability|confidence|prob):\s*(0?\.\d+|1\.0|\d+%)", text, re.IGNORECASE)
    if match:
        val = match.group(1)
        if "%" in val:
            return float(val.replace("%", "")) / 100
        return float(val)
    return None

def run_brier_evaluation():
    test_file = "finetune/traps_test.jsonl"
    if not os.path.exists(test_file):
        print("Error: traps_test.jsonl not found.")
        return

    engine = PolyEngine()
    total_brier = 0
    count = 0
    critical_failures = 0
    
    print("\n" + "="*50)
    print("🚀 INITIATING PROBABILISTIC BRIER EVALUATION")
    print("="*50 + "\n")

    with open(test_file, "r") as f:
        for line in f:
            data = json.loads(line)
            user_msg = data["messages"][1]["content"][0]["text"]
            
            # Extract market title to get ground truth
            title = user_msg.split("scenario:")[1].split(". Odds:")[0].strip()
            outcome = TRAP_GROUND_TRUTH.get(title)
            
            if outcome is None:
                continue

            # Modified prompt to force a probability output
            analysis_request = {
                "title": title,
                "odds": user_msg.split("Odds:")[1].split(". News:")[0].strip(),
                "news": user_msg.split("News:")[1].split(". Initial Thought:")[0].strip()
            }
            
            # We inject a specific instruction for evaluation
            analysis_request["initial_thought"] += "\nIMPORTANT: Provide your final estimate as a decimal probability (0.0 to 1.0) labeled as 'PROBABILITY: X'."

            response = engine.analyze(analysis_request)
            forecast = extract_probability(response)
            
            if forecast is not None:
                score = calculate_brier_score(forecast, outcome)
                total_brier += score
                count += 1
                
                status = "✅ STABLE"
                # A Brier score > 0.5 on a binary event is very poor (worse than guessing 0.5)
                if score > 0.4:
                    status = "🚨 CRITICAL FAILURE"
                    critical_failures += 1
                
                print(f"MARKET: {title[:40]}...")
                print(f"FORECAST: {forecast:.2f} | TRUTH: {outcome:.2f} | BRIER: {score:.4f} | {status}")
                print("-" * 30)
            else:
                print(f"⚠️ Could not extract probability for: {title}")

    if count > 0:
        avg_brier = total_brier / count
        print("\n" + "="*50)
        print("📊 FINAL BRIER METRICS")
        print(f"Average Brier Score: {avg_brier:.4f}")
        print(f"Critical Failures: {critical_failures}")
        print(f"Successful Evaluations: {count}")
        print("Note: Lower Brier Score is better (0.0 is perfect).")
        print("="*50)
    else:
        print("No valid evaluations completed.")

if __name__ == "__main__":
    run_brier_evaluation()
