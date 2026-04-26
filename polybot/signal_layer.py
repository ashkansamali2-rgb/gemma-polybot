import re
from typing import Dict

from engine import PolyEngine
from polybot.types import SignalDecision

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


def extract_probability(text: str):
    match = re.search(r"FINAL_PROBABILITY:\s*\[?(\d+(?:\.\d+)?)\]?%", text)
    if match:
        return float(match.group(1)) / 100.0
    return None


class DebateSignalGenerator:
    """Signal generation layer."""

    def __init__(self, engine: PolyEngine):
        self.engine = engine

    def evaluate_market(self, market: Dict) -> SignalDecision:
        context = f"Odds are {market['odds']}. Volume: ${market.get('volume', 0):,.0f}"
        bull_prompt = BULL_PROMPT_TEMPLATE.format(title=market["title"], context=context)
        bull_thesis = self.engine.analyze(market, raw_prompt=bull_prompt)

        bear_prompt = BEAR_PROMPT_TEMPLATE.format(
            title=market["title"], context=context, bull_thesis=bull_thesis
        )
        bear_thesis = self.engine.analyze(market, raw_prompt=bear_prompt)

        judge_prompt = JUDGE_PROMPT_TEMPLATE.format(
            title=market["title"],
            odds=market["odds"],
            bull_thesis=bull_thesis,
            bear_thesis=bear_thesis,
        )
        final_analysis = self.engine.analyze(market, raw_prompt=judge_prompt)
        ai_probability = extract_probability(final_analysis)
        market_price = float(market.get("price", 0.0))
        edge = (ai_probability - market_price) if ai_probability is not None else None

        if ai_probability is None:
            return SignalDecision(
                market_title=market["title"],
                ai_probability=None,
                market_price=market_price,
                edge=None,
                action="HOLD",
                reason="FAILED_TO_PARSE_PROBABILITY",
                raw_analysis=final_analysis,
            )

        return SignalDecision(
            market_title=market["title"],
            ai_probability=ai_probability,
            market_price=market_price,
            edge=edge,
            action="BUY" if edge and edge > 0 else "HOLD",
            reason="EDGE_COMPUTED",
            raw_analysis=final_analysis,
        )
