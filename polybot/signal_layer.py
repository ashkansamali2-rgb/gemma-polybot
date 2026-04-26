from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from statistics import mean
from typing import Dict, List, Optional, Sequence

from polybot.calibration import CalibrationManager, UncertaintyEngine
from polybot.config import MarketFilterConfig, RetrievalConfig, StrategyConfig
from polybot.types import (
    CandidateRanking,
    CalibrationArtifact,
    EvidenceRecord,
    ForecastRecord,
    ForecastResponse,
    ReplayFrame,
    SignalDecision,
)
from polybot_legacy.engine import PolyEngine


STRUCTURED_RESPONSE_SCHEMA = {
    "required": [
        "raw_probability",
        "short_rationale",
        "key_drivers",
        "counter_drivers",
        "invalidation_condition",
        "confidence_band",
        "evidence_used",
    ]
}


BULL_PROMPT_TEMPLATE = (
    "<|im_start|>system\nAct as a bullish aggressive analyst focused on binary event markets."
    " Use only the supplied market state and evidence. Cite concrete drivers, avoid certainty."
    "<|im_end|>\n"
    "<|im_start|>user\n{context}<|im_end|>\n<|im_start|>assistant\n"
)

BEAR_PROMPT_TEMPLATE = (
    "<|im_start|>system\nAct as a skeptical risk manager focused on failure modes, weak evidence,"
    " and microstructure traps. Use only the supplied context.<|im_end|>\n"
    "<|im_start|>user\n{context}\n\nBULL THESIS:\n{bull_thesis}<|im_end|>\n<|im_start|>assistant\n"
)

JUDGE_PROMPT_TEMPLATE = (
    "<|im_start|>system\nAct as the final forecaster for a calibration-first trading system."
    " Output valid JSON only. No markdown, no prose outside JSON."
    " Required keys: raw_probability, short_rationale, key_drivers, counter_drivers,"
    " invalidation_condition, confidence_band, evidence_used."
    " raw_probability must be a 0-1 float. confidence_band must be [low, high]."
    "<|im_end|>\n"
    "<|im_start|>user\n{context}\n\nBULL THESIS:\n{bull_thesis}\n\nBEAR THESIS:\n{bear_thesis}\n\n"
    "PROMPT_VARIANT: {variant_label}\n"
    "EVIDENCE_SUBSET: {subset_label}\n<|im_end|>\n<|im_start|>assistant\n"
)


def extract_probability(text: str):
    match = re.search(r"FINAL_PROBABILITY:\s*(\d+(?:\.\d+)?)%", text, re.IGNORECASE)
    if match:
        return float(match.group(1)) / 100.0
    return None


def _extract_json_object(text: str) -> Optional[str]:
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence_match:
        return fence_match.group(1)

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    return None


def parse_structured_forecast(text: str) -> Optional[ForecastResponse]:
    json_blob = _extract_json_object(text)
    if not json_blob:
        return None

    try:
        payload = json.loads(json_blob)
    except json.JSONDecodeError:
        return None

    if not isinstance(payload, dict):
        return None
    if any(key not in payload for key in STRUCTURED_RESPONSE_SCHEMA["required"]):
        return None

    try:
        probability = float(payload["raw_probability"])
        if probability < 0.0 or probability > 1.0:
            return None
        confidence_band = list(payload["confidence_band"])
        if len(confidence_band) != 2:
            return None
        confidence_band = [float(confidence_band[0]), float(confidence_band[1])]
        return ForecastResponse(
            raw_probability=probability,
            short_rationale=str(payload["short_rationale"]),
            key_drivers=[str(item) for item in payload["key_drivers"]],
            counter_drivers=[str(item) for item in payload["counter_drivers"]],
            invalidation_condition=str(payload["invalidation_condition"]),
            confidence_band=confidence_band,
            evidence_used=[str(item) for item in payload["evidence_used"]],
            raw_response=text,
        )
    except (TypeError, ValueError):
        return None


def build_resolved_market_dataset(frames: Sequence[ReplayFrame]) -> List[Dict]:
    dataset = []
    for frame in frames:
        outcome = frame.market.resolved_outcome
        if outcome is None:
            continue
        dataset.append(
            {
                "market_id": frame.market.market_id,
                "event_id": frame.market.event_id,
                "category": frame.market.category,
                "forecast_timestamp": frame.market.forecast_timestamp,
                "expiry_timestamp": frame.market.expiry_timestamp,
                "resolution_criteria": frame.market.resolution_criteria,
                "description": frame.market.description,
                "evidence": [record.to_dict() for record in frame.evidence],
                "resolved_outcome": outcome,
            }
        )
    return dataset


@dataclass
class CandidateRanker:
    config: StrategyConfig

    def rank(self, frame: ReplayFrame, *, live_mode: bool) -> CandidateRanking:
        market = frame.market
        features = frame.features
        if features is None:
            return CandidateRanking(
                rank_score=0.0,
                passed_filters=False,
                exclusion_reason="MISSING_FEATURES",
                factor_scores={},
            )

        spread_bps = float(features.market_microstructure.get("spread_bps", math.inf))
        depth_total = float(features.liquidity.get("depth_total", 0.0))
        rule_clarity = 0.0 if not market.resolution_criteria.strip() else 1.0
        stale_quote = False
        if market.orderbook_timestamp is not None:
            stale_quote = (
                market.forecast_timestamp - market.orderbook_timestamp
                > self.config.provider.stale_quote_seconds
            )

        if live_mode and self.config.market_filters.require_tradable_token_live and not market.token_id:
            return CandidateRanking(0.0, False, "MISSING_TRADABILITY_ID", {})
        if spread_bps > self.config.market_filters.max_spread_bps:
            return CandidateRanking(0.0, False, "SPREAD_TOO_WIDE", {"spread_bps": spread_bps})
        if depth_total < self.config.market_filters.min_depth:
            return CandidateRanking(0.0, False, "INSUFFICIENT_DEPTH", {"depth_total": depth_total})
        if stale_quote:
            return CandidateRanking(0.0, False, "STALE_ORDERBOOK", {"staleness_seconds": market.forecast_timestamp - market.orderbook_timestamp})
        if self.config.market_filters.exclude_ambiguous_rules and rule_clarity == 0.0:
            return CandidateRanking(0.0, False, "AMBIGUOUS_RULES", {"rule_clarity": rule_clarity})

        hours_to_expiry = float(features.metadata.get("hours_to_expiry", 9999.0))
        evidence_quality = float(features.evidence.get("mean_credibility", 0.0))
        volume = float(features.liquidity.get("volume", 0.0))
        factor_scores = {
            "spread_quality": max(0.0, 1.0 - min(spread_bps / max(self.config.market_filters.max_spread_bps, 1.0), 1.0)),
            "depth_quality": min(depth_total / max(self.config.market_filters.min_depth, 1.0), 3.0) / 3.0,
            "volume_quality": min(volume / 10000.0, 1.0),
            "horizon_quality": max(0.0, 1.0 - min(hours_to_expiry / max(self.config.provider.max_horizon_hours, 1.0), 1.0)),
            "rule_clarity": rule_clarity,
            "evidence_quality": evidence_quality,
        }
        rank_score = mean(factor_scores.values())
        return CandidateRanking(
            rank_score=rank_score,
            passed_filters=True,
            exclusion_reason="",
            factor_scores=factor_scores,
        )


ENSEMBLE_PROMPT_TEMPLATE = (
    "<|im_start|>system\nAct as a specialized prediction market trader. "
    "Output valid JSON only. Required keys: bid, ask, short_rationale. "
    "bid and ask must be 0-1 floats representing your limit order. bid < ask."
    "<|im_end|>\n"
    "<|im_start|>user\n{context}\n\n"
    "Your assigned persona for this execution is: [{persona}]. Strictly embody this persona.\n"
    "<|im_end|>\n<|im_start|>assistant\n"
)

PERSONAS = [
    "Aggressive Momentum Trader", "Skeptical Value Investor", "Pure Statistician",
    "Contrarian Risk-Seeker", "Geopolitical Hawk", "Market Microstructure Expert",
    "Macro-Economist", "News-Driven Retail Trader", "Algorithmic Arbitrageur",
    "Conservative Option Writer", "High-Frequency Taker", "Behavioral Finance Expert",
]


def extract_ensemble_quote(text: str) -> Optional[tuple[float, float, str]]:
    json_blob = _extract_json_object(text)
    if not json_blob:
        return None
    try:
        payload = json.loads(json_blob)
        bid = float(payload.get("bid", 0))
        ask = float(payload.get("ask", 0))
        rationale = str(payload.get("short_rationale", ""))
        if 0 <= bid <= ask <= 1:
            return bid, ask, rationale
    except Exception:
        pass
    return None


class MarketEnsembleGenerator:
    def __init__(
        self,
        engine: PolyEngine,
        config: StrategyConfig,
        calibration_manager: CalibrationManager,
        uncertainty_engine: UncertaintyEngine,
    ):
        self.engine = engine
        self.config = config
        self.calibration_manager = calibration_manager
        self.uncertainty_engine = uncertainty_engine

    def evaluate_frame(
        self,
        frame: ReplayFrame,
        *,
        calibration_artifact: CalibrationArtifact,
        ranking: CandidateRanking,
    ) -> SignalDecision:
        market = frame.market
        if not ranking.passed_filters:
            return self._hold_decision(
                frame,
                reason=ranking.exclusion_reason,
                rank_score=ranking.rank_score,
            )

        evidence = self._select_evidence(frame.evidence, market.category)
        context = self._build_context(frame, evidence)

        print(f"[SYSTEM] Spinning up {self.config.uncertainty.ensemble_agents}-Agent Internal Market Ensemble...")

        bids = []
        asks = []
        rationales = []
        
        # Internal Order Book Generation
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def _get_quote(i):
            persona = PERSONAS[i % len(PERSONAS)]
            prompt = ENSEMBLE_PROMPT_TEMPLATE.format(persona=persona, context=context)
            try:
                output = self.engine.analyze(market.to_dict(), raw_prompt=prompt, max_tokens=1024)
                return persona, extract_ensemble_quote(output)
            except Exception as e:
                print(f"[ERROR] Agent {persona} failed: {e}")
                return persona, None

        max_workers = min(16, self.config.uncertainty.ensemble_agents)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_get_quote, i) for i in range(self.config.uncertainty.ensemble_agents)]
            for future in as_completed(futures):
                persona, quote = future.result()
                if quote:
                    b, a, r = quote
                    bids.append(b)
                    asks.append(a)
                    rationales.append(f"[{persona}] {r}")
        
        if not bids or not asks:
            return self._hold_decision(
                frame,
                reason="FAILED_ENSEMBLE_QUOTES",
                rank_score=ranking.rank_score,
                raw_analysis="",
            )

        import numpy as np

        # Market Equilibrium Price Calculation (Supply/Demand curve intersection)
        if max(bids) < min(asks):
            equilibrium_price = (max(bids) + min(asks)) / 2.0
        else:
            best_volume = 0
            clearing_prices = []
            for p_int in range(1, 100):
                p = p_int / 100.0
                demand = sum(1 for b in bids if b >= p)
                supply = sum(1 for a in asks if a <= p)
                volume = min(demand, supply)
                
                if volume > best_volume:
                    best_volume = volume
                    clearing_prices = [p]
                elif volume == best_volume and volume > 0:
                    clearing_prices.append(p)
            equilibrium_price = sum(clearing_prices) / len(clearing_prices) if clearing_prices else 0.5

        raw_probability = equilibrium_price
        calibrated_probability = self.calibration_manager.calibrate(raw_probability, calibration_artifact)
        calibration_residual = abs(calibrated_probability - raw_probability)
        
        # Use average bid-ask spread to inform uncertainty
        uncertainty = self.uncertainty_engine.estimate(
            market_id=market.market_id,
            sample_probabilities=[(b+a)/2 for b, a in zip(bids, asks)],
            rationales=rationales,
            calibration_residual=calibration_residual,
        )
        
        confidence_low, confidence_high = self.uncertainty_engine.conformal_band(
            calibrated_probability,
            [calibration_residual],
        )

        return SignalDecision(
            market_id=market.market_id,
            event_id=market.event_id,
            token_id=market.token_id,
            market_title=market.title,
            forecast_timestamp=market.forecast_timestamp,
            raw_probability=raw_probability,
            calibrated_probability=calibrated_probability,
            market_price=market.mid_price,
            executable_price=None,
            edge_after_costs=None,
            action="HOLD",
            reason="FORECAST_READY",
            uncertainty_score=uncertainty.uncertainty_score,
            forecast_variance=uncertainty.forecast_variance,
            semantic_disagreement_score=uncertainty.semantic_disagreement_score,
            update_instability_score=uncertainty.update_instability_score,
            confidence_low=confidence_low,
            confidence_high=confidence_high,
            raw_confidence_band=[float(np.percentile(bids, 10)), float(np.percentile(asks, 90))],
            evidence_ids=[record.evidence_id for record in evidence],
            key_drivers=["Ensemble Demand Concentration", "Persona-weighted bids"],
            counter_drivers=["Ensemble Supply Resistance", "Persona-weighted asks"],
            invalidation_condition="Major internal orderbook imbalance shift",
            short_rationale=f"Market Ensemble Equilibrium at {equilibrium_price:.2f}. " + "\n".join(rationales[:2]),
            raw_analysis=f"Total Quotes: {len(bids)}. Top Bid/Ask: {max(bids):.2f}/{min(asks):.2f}",
            calibration_artifact_version=calibration_artifact.version,
            calibration_method=calibration_artifact.method,
            execution_mode=self.config.execution.execution_mode,
            uncertainty_components={
                "forecast_variance": uncertainty.forecast_variance,
                "semantic_disagreement": uncertainty.semantic_disagreement_score,
                "prompt_sensitivity": uncertainty.prompt_sensitivity_score,
                "evidence_sensitivity": uncertainty.evidence_sensitivity_score,
                "calibration_residual": uncertainty.calibration_residual_score,
                "update_instability": uncertainty.update_instability_score,
            },
            rank_score=ranking.rank_score,
            candidate_status="ELIGIBLE",
        )

    def build_forecast_record(
        self,
        decision: SignalDecision,
        *,
        category: str,
        resolved_outcome: Optional[str],
    ) -> ForecastRecord:
        return ForecastRecord(
            market_id=decision.market_id,
            event_id=decision.event_id,
            timestamp=decision.forecast_timestamp,
            category=category,
            raw_probability=decision.raw_probability if decision.raw_probability is not None else 0.5,
            calibrated_probability=(
                decision.calibrated_probability
                if decision.calibrated_probability is not None
                else 0.5
            ),
            market_price=decision.market_price,
            resolved_outcome=resolved_outcome,
            uncertainty_score=decision.uncertainty_score,
            evidence_count=len(decision.evidence_ids),
            calibration_method=decision.calibration_method or "identity",
        )

    def _select_evidence(
        self,
        evidence: Sequence[EvidenceRecord],
        category: str,
    ) -> List[EvidenceRecord]:
        if not self.config.retrieval.enabled:
            return []
        aggressiveness = self.config.category_profiles.get(
            category.lower(),
            self.config.category_profiles["default"],
        ).get("retrieval_aggressiveness", 1.0)
        limit = max(1, int(round(self.config.retrieval.max_evidence_items * aggressiveness)))
        sorted_evidence = sorted(
            evidence,
            key=lambda item: (item.source_credibility, item.publication_timestamp),
            reverse=True,
        )
        return list(sorted_evidence[:limit])

    def _build_context(self, frame: ReplayFrame, evidence: Sequence[EvidenceRecord]) -> str:
        market = frame.market
        features = frame.features
        evidence_lines = "\n".join(
            f"- [{record.source_type}] credibility={record.source_credibility:.2f}: {record.summary}"
            for record in evidence
        ) or "- No eligible evidence retrieved."
        feature_lines = ""
        if features is not None:
            feature_lines = (
                f"Spread bps: {features.market_microstructure.get('spread_bps', 0):.1f}\n"
                f"Depth total: {features.liquidity.get('depth_total', 0):.1f}\n"
                f"Momentum 1: {features.price_history.get('momentum_1', 0):.4f}\n"
                f"Evidence count: {features.evidence.get('count', 0):.0f}\n"
            )
        return (
            f"MARKET: {market.title}\n"
            f"CATEGORY: {market.category}\n"
            f"DESCRIPTION: {market.description}\n"
            f"RESOLUTION CRITERIA: {market.resolution_criteria or 'Not supplied'}\n"
            f"CURRENT MID PRICE: {market.mid_price:.4f}\n"
            f"BEST BID/ASK: {market.best_bid} / {market.best_ask}\n"
            f"VOLUME: {market.volume:.2f}\n"
            f"HOURS TO EXPIRY: {((market.expiry_timestamp - market.forecast_timestamp) / 3600.0) if market.expiry_timestamp else 'unknown'}\n"
            f"FEATURES:\n{feature_lines}"
            f"EVIDENCE:\n{evidence_lines}"
        )

    @staticmethod
    def _hold_decision(
        frame: ReplayFrame,
        *,
        reason: str,
        rank_score: float,
        raw_analysis: str = "",
    ) -> SignalDecision:
        market = frame.market
        return SignalDecision(
            market_id=market.market_id,
            event_id=market.event_id,
            token_id=market.token_id,
            market_title=market.title,
            forecast_timestamp=market.forecast_timestamp,
            raw_probability=None,
            calibrated_probability=None,
            market_price=market.mid_price,
            executable_price=None,
            edge_after_costs=None,
            action="HOLD",
            reason=reason,
            uncertainty_score=1.0 if reason == "FAILED_STRUCTURED_FORECAST" else 0.0,
            forecast_variance=0.0,
            semantic_disagreement_score=0.0,
            update_instability_score=0.0,
            raw_analysis=raw_analysis,
            execution_mode="",
            rank_score=rank_score,
            candidate_status="EXCLUDED",
            hold_reasons=[reason],
        )

