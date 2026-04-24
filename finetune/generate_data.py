import json
import os

def generate_trap_dataset():
    trap_scenarios = [
        # 1. Toxic News Trap
        {
            "category": "Toxic News",
            "market": "Will Company Z's CEO be re-elected?",
            "odds": "85% YES",
            "news": "Leaked documents show 70% of board members are planning a vote of no confidence tomorrow morning.",
            "initial_thought": "Odds are very high at 85%, this looks like a safe bet for YES.",
            "correction": "Wait, the 85% odds haven't priced in the leaked 'no confidence' news yet. A 70% opposition from the board makes the 85% market price a massive trap. Selling YES or betting NO is the move before the news goes public.",
            "action": "Bet NO. The toxic news completely invalidates the current market pricing."
        },
        # 2. Misleading Math Trap
        {
            "category": "Misleading Math",
            "market": "Will the coin land Heads? (Special Polymarket Event)",
            "odds": "90% YES (Heads)",
            "news": "A reputable auditor confirms the coin is fair and perfectly balanced. It is a standard 50/50 flip.",
            "initial_thought": "90% probability is nearly a sure thing. Buying YES tokens.",
            "correction": "Wait, if the audit confirms a fair 50/50 flip, the 90% odds are mathematically absurd. Betting $0.90 to win $1.00 on a 50% event is extreme negative EV. I should be betting NO at $0.10 for a 50% win chance.",
            "action": "Bet NO. The market is massively mispriced relative to the underlying 50/50 probability."
        },
        # 3. Low Liquidity Trap
        {
            "category": "Low Liquidity",
            "market": "Will 'Obscure Token' reach $1.00 by Sunday?",
            "odds": "30% YES",
            "news": "Significant technical milestone achieved.",
            "initial_thought": "30% seems low for this news. I'll market buy $2,000 worth of YES.",
            "correction": "Checking the order book depth: there is only $150 of liquidity at the current price. A $2,000 market order will slip the price from $0.30 to $0.85, destroying any edge and putting me at an immediate loss.",
            "action": "PASS or use small LIMIT ORDERS. Market buying into this thin liquidity is a suicide mission."
        },
        # 4. Regulatory Trap
        {
            "category": "Regulatory",
            "market": "Will Crypto Exchange Alpha get its license?",
            "odds": "75% YES",
            "news": "Regulator just opened a separate criminal probe into the founder.",
            "initial_thought": "They have the best lawyers, 75% odds reflect their strength.",
            "correction": "A criminal probe into a founder usually halts licensing processes indefinitely. The market is underestimating the severity of 'criminal' vs 'civil' hurdles. 75% is way too optimistic.",
            "action": "Bet NO. Regulatory approval is unlikely while a criminal investigation is active."
        }
    ]

    dataset = []
    for s in trap_scenarios:
        dataset.append({
            "messages": [
                {"role": "system", "content": "You are a professional market analyst with self-correction capabilities."},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"Analyze this {s['category']} scenario: {s['market']}. Odds: {s['odds']}. News: {s['news']}. Initial Thought: {s['initial_thought']}"}
                    ]
                },
                {
                    "role": "assistant",
                    "content": f"<|think|>\n{s['correction']}\n<|think|>\n<|channel|>\nAction: {s['action']}"
                }
            ]
        })

    os.makedirs("finetune", exist_ok=True)
    with open("finetune/train.jsonl", "a") as f: # Append to existing
        for entry in dataset:
            f.write(json.dumps(entry) + "\n")
            
    # Also save as a separate test set for evaluation
    with open("finetune/traps_test.jsonl", "w") as f:
        for entry in dataset:
            f.write(json.dumps(entry) + "\n")

    return len(dataset)

if __name__ == "__main__":
    count = generate_trap_dataset()
    print(f"Added {count} Trap scenarios to finetune/train.jsonl and traps_test.jsonl")
