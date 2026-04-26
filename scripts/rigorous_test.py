from pathlib import Path
import json
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from polybot_infra.engine import PolyEngine

KEYWORDS = ["wait", "mispriced", "slippage"]


def run_rigorous_test():
    test_file = "finetune/traps_test.jsonl"
    if not os.path.exists(test_file):
        print(f"Error: {test_file} not found. Run 'python finetune/generate_data.py' first.")
        return

    engine = PolyEngine()
    total = 0
    success = 0

    print("\n" + "=" * 60)
    print("INITIATING RIGOROUS ALPHA TEST (TRAP DETECTION)")
    print("=" * 60 + "\n")

    with open(test_file, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue

            data = json.loads(line)
            user_msg = data["messages"][1]["content"][0]["text"]

            try:
                market_part = user_msg.split("scenario:")[1]
                title = market_part.split(". Odds:")[0].strip()
                odds = market_part.split("Odds:")[1].split(". News:")[0].strip()
                news = market_part.split("News:")[1].split(". Initial Thought:")[0].strip()
                initial_thought = market_part.split("Initial Thought:")[1].strip()

                market_data = {
                    "title": title,
                    "odds": odds,
                    "news": news,
                    "initial_thought": initial_thought,
                }

                response = engine.analyze(market_data)
                has_think = "<|think|>" in response
                found_keywords = [kw for kw in KEYWORDS if kw.lower() in response.lower()]
                has_keyword = len(found_keywords) > 0

                total += 1
                if has_think and has_keyword:
                    success += 1
                    status = "DODGED (Alpha Detected)"
                else:
                    status = "TRAPPED (No Correction)"

                print(f"MARKET: {title[:50]}...")
                print(f"THINKING TAG: {'FOUND' if has_think else 'MISSING'}")
                print(f"KEYWORDS:    {', '.join(found_keywords) if found_keywords else 'NONE'}")
                print(f"RESULT:      {status}")
                print("-" * 40)
            except Exception as e:
                print(f"Error processing entry: {e}")

    if total > 0:
        alpha_score = (success / total) * 100
        print("\n" + "=" * 60)
        print(f"FINAL ALPHA SCORE: {alpha_score:.2f}%")
        print(f"Traps Dodged: {success}/{total}")
        print("Status: " + ("Alpha Strategy Validated" if alpha_score > 80 else "Needs Further Tuning"))
        print("=" * 60)
    else:
        print("No valid test cases found.")


if __name__ == "__main__":
    run_rigorous_test()
