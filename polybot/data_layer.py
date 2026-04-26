from __future__ import annotations

import json
import math
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence

from polybot.types import EvidenceRecord, FeatureSnapshot, MarketObservation, ReplayFrame
from polybot_infra.polymarket_api import fetch_live_polymarket_data


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _now_ts() -> float:
    return float(time.time())


def _make_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class GammaDiscoveryAdapter:
    def fetch_markets(self, limit: int = 1000) -> List[Dict]:
        raw_markets = fetch_live_polymarket_data(limit=limit)
        discovery_payloads = []
        for idx, market in enumerate(raw_markets):
            discovery_payloads.append(
                {
                    "event_id": market.get("event_id") or f"event-{idx}",
                    "market_id": market.get("market_id") or f"market-{idx}",
                    "title": market.get("title", "Unknown market"),
                    "description": market.get("description", ""),
                    "resolution_criteria": market.get("resolution_criteria", ""),
                    "category": market.get("category", "Other"),
                    "subcategory": market.get("subcategory", ""),
                    "expiry_timestamp": market.get("expiry_timestamp"),
                    "volume": market.get("volume", 0.0),
                    "token_id": market.get("token_id"),
                    "raw": market,
                }
            )
        return discovery_payloads


class ClobMarketStateAdapter:
    def fetch_market_state(self, discovery_payloads: Sequence[Dict]) -> Dict[str, Dict]:
        executable_state: Dict[str, Dict] = {}
        for payload in discovery_payloads:
            raw = payload.get("raw", {})
            market_id = payload["market_id"]
            mid_price = _safe_float(raw.get("price"), 0.5)
            spread = _safe_float(raw.get("spread"), 0.02)
            best_bid = _safe_float(raw.get("best_bid"), max(0.01, mid_price - spread / 2.0))
            best_ask = _safe_float(raw.get("best_ask"), min(0.99, mid_price + spread / 2.0))
            executable_state[market_id] = {
                "token_id": payload.get("token_id") or raw.get("token_id"),
                "best_bid": best_bid,
                "best_ask": best_ask,
                "last_trade_price": _safe_float(raw.get("last_trade_price"), mid_price),
                "spread": abs(best_ask - best_bid),
                "depth_bid": _safe_float(raw.get("depth_bid"), max(25.0, _safe_float(raw.get("volume"), 0.0) * 0.01)),
                "depth_ask": _safe_float(raw.get("depth_ask"), max(25.0, _safe_float(raw.get("volume"), 0.0) * 0.01)),
                "tick_size": _safe_float(raw.get("tick_size"), 0.01),
                "fee_schedule": raw.get(
                    "fee_schedule",
                    {
                        "maker_bps": _safe_float(raw.get("maker_fee_bps"), 0.0),
                        "taker_bps": _safe_float(raw.get("taker_fee_bps"), 100.0),
                    },
                ),
                "open_interest": raw.get("open_interest"),
                "market_status": raw.get("market_status", "active"),
                "orderbook_timestamp": raw.get("orderbook_timestamp") or _now_ts(),
                "raw": raw,
            }
        return executable_state


def normalize_market_snapshot(
    discovery_payload: Dict,
    executable_payload: Optional[Dict] = None,
    *,
    forecast_timestamp: Optional[float] = None,
) -> MarketObservation:
    executable_payload = executable_payload or {}
    raw_payloads = {
        "discovery": discovery_payload.get("raw", discovery_payload),
        "executable": executable_payload.get("raw", executable_payload),
    }

    best_bid = executable_payload.get("best_bid")
    best_ask = executable_payload.get("best_ask")
    explicit_mid = discovery_payload.get("mid_price")
    if explicit_mid is None and best_bid is not None and best_ask is not None:
        explicit_mid = (_safe_float(best_bid) + _safe_float(best_ask)) / 2.0
    if explicit_mid is None:
        explicit_mid = _safe_float(discovery_payload.get("price"), 0.5)

    spread = executable_payload.get("spread")
    if spread is None and best_bid is not None and best_ask is not None:
        spread = abs(_safe_float(best_ask) - _safe_float(best_bid))

    fee_schedule = executable_payload.get("fee_schedule") or discovery_payload.get("fee_schedule") or {
        "maker_bps": _safe_float(discovery_payload.get("maker_fee_bps"), 0.0),
        "taker_bps": _safe_float(discovery_payload.get("taker_fee_bps"), 100.0),
    }

    return MarketObservation(
        market_id=str(discovery_payload.get("market_id") or _make_id("market")),
        event_id=str(discovery_payload.get("event_id") or discovery_payload.get("market_id") or _make_id("event")),
        token_id=executable_payload.get("token_id") or discovery_payload.get("token_id"),
        title=discovery_payload.get("title", "Unknown market"),
        description=discovery_payload.get("description", ""),
        resolution_criteria=discovery_payload.get("resolution_criteria", ""),
        category=discovery_payload.get("category", "Other"),
        subcategory=discovery_payload.get("subcategory", ""),
        forecast_timestamp=float(
            forecast_timestamp
            or discovery_payload.get("forecast_timestamp")
            or executable_payload.get("orderbook_timestamp")
            or _now_ts()
        ),
        expiry_timestamp=discovery_payload.get("expiry_timestamp"),
        best_bid=_safe_float(best_bid, None) if best_bid is not None else None,
        best_ask=_safe_float(best_ask, None) if best_ask is not None else None,
        mid_price=_safe_float(explicit_mid, 0.5),
        last_trade_price=(
            _safe_float(executable_payload.get("last_trade_price"), None)
            if executable_payload.get("last_trade_price") is not None
            else None
        ),
        spread=_safe_float(spread, None) if spread is not None else None,
        depth_bid=_safe_float(executable_payload.get("depth_bid"), 0.0),
        depth_ask=_safe_float(executable_payload.get("depth_ask"), 0.0),
        tick_size=_safe_float(executable_payload.get("tick_size"), 0.01),
        fee_schedule={
            "maker_bps": _safe_float(fee_schedule.get("maker_bps"), 0.0),
            "taker_bps": _safe_float(fee_schedule.get("taker_bps"), 100.0),
        },
        volume=_safe_float(discovery_payload.get("volume"), 0.0),
        open_interest=(
            _safe_float(executable_payload.get("open_interest"), None)
            if executable_payload.get("open_interest") is not None
            else None
        ),
        market_status=executable_payload.get("market_status", discovery_payload.get("market_status", "active")),
        resolved_outcome=discovery_payload.get("resolved_outcome"),
        raw_provider_payloads=raw_payloads,
        orderbook_timestamp=executable_payload.get("orderbook_timestamp"),
        platform_capability_flags=discovery_payload.get("platform_capability_flags", {}),
    )


@dataclass
class EvidenceStore:
    records: List[EvidenceRecord] = field(default_factory=list)

    def ingest(self, records: Sequence[EvidenceRecord]) -> None:
        self.records.extend(records)

    def get_replay_safe_evidence(
        self,
        *,
        market_id: Optional[str],
        event_id: Optional[str],
        as_of_timestamp: float,
        max_items: int = 6,
        max_age_hours: float = 168.0,
        min_credibility: float = 0.0,
        deduplicate_sources: bool = True,
    ) -> List[EvidenceRecord]:
        min_publication = as_of_timestamp - (max_age_hours * 3600)
        eligible = [
            record
            for record in self.records
            if record.publication_timestamp <= as_of_timestamp
            and record.ingestion_timestamp <= as_of_timestamp
            and record.publication_timestamp >= min_publication
            and record.source_credibility >= min_credibility
            and (
                record.linked_market_id == market_id
                or record.linked_event_id == event_id
                or (record.linked_market_id is None and record.linked_event_id is None)
            )
        ]
        eligible.sort(
            key=lambda item: (
                item.linked_market_id == market_id,
                item.linked_event_id == event_id,
                item.source_credibility,
                item.publication_timestamp,
            ),
            reverse=True,
        )

        if deduplicate_sources:
            deduped: List[EvidenceRecord] = []
            seen_keys = set()
            for record in eligible:
                key = (record.source_url, record.summary)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                deduped.append(record)
            eligible = deduped
        return eligible[:max_items]


@dataclass
class FeatureStore:
    price_history: Dict[str, List[tuple[float, float]]] = field(default_factory=dict)

    def build(
        self,
        market: MarketObservation,
        evidence: Sequence[EvidenceRecord],
    ) -> FeatureSnapshot:
        history = self.price_history.setdefault(market.market_id, [])
        history.append((market.forecast_timestamp, market.mid_price))
        history = history[-32:]
        self.price_history[market.market_id] = history

        previous_price = history[-2][1] if len(history) >= 2 else market.mid_price
        momentum = market.mid_price - previous_price
        spread = market.spread if market.spread is not None else 0.0
        evidence_freshness_hours = 0.0
        if evidence:
            freshest = max(record.publication_timestamp for record in evidence)
            evidence_freshness_hours = max(0.0, (market.forecast_timestamp - freshest) / 3600.0)

        return FeatureSnapshot(
            market_id=market.market_id,
            event_id=market.event_id,
            as_of_timestamp=market.forecast_timestamp,
            market_microstructure={
                "spread_bps": spread * 10000.0,
                "depth_bid": market.depth_bid,
                "depth_ask": market.depth_ask,
                "tick_size": market.tick_size,
            },
            price_history={
                "last_mid_price": market.mid_price,
                "momentum_1": momentum,
                "history_points": float(len(history)),
            },
            liquidity={
                "volume": market.volume,
                "open_interest": _safe_float(market.open_interest, 0.0),
                "depth_total": market.depth_bid + market.depth_ask,
            },
            evidence={
                "count": float(len(evidence)),
                "mean_credibility": (
                    float(sum(record.source_credibility for record in evidence) / len(evidence))
                    if evidence
                    else 0.0
                ),
                "freshness_hours": evidence_freshness_hours,
            },
            metadata={
                "category": market.category,
                "subcategory": market.subcategory,
                "hours_to_expiry": (
                    max(0.0, (market.expiry_timestamp - market.forecast_timestamp) / 3600.0)
                    if market.expiry_timestamp is not None
                    else math.inf
                ),
            },
            calibration_context={
                "market_status_active": 1.0 if market.market_status == "active" else 0.0,
                "has_orderbook": 1.0 if market.best_bid is not None and market.best_ask is not None else 0.0,
            },
        )


class LivePolymarketDataSource:
    def __init__(
        self,
        discovery: Optional[GammaDiscoveryAdapter] = None,
        executable: Optional[ClobMarketStateAdapter] = None,
        evidence_store: Optional[EvidenceStore] = None,
        feature_store: Optional[FeatureStore] = None,
    ):
        self.discovery = discovery or GammaDiscoveryAdapter()
        self.executable = executable or ClobMarketStateAdapter()
        self.evidence_store = evidence_store or EvidenceStore()
        self.feature_store = feature_store or FeatureStore()

    def fetch_markets(self, limit: int = 1000) -> List[ReplayFrame]:
        discovery_payloads = self.discovery.fetch_markets(limit=limit)
        executable_state = self.executable.fetch_market_state(discovery_payloads)
        frames = []
        for payload in discovery_payloads:
            market = normalize_market_snapshot(
                payload,
                executable_state.get(payload["market_id"], {}),
            )
            evidence = self.evidence_store.get_replay_safe_evidence(
                market_id=market.market_id,
                event_id=market.event_id,
                as_of_timestamp=market.forecast_timestamp,
            )
            features = self.feature_store.build(market, evidence)
            frames.append(
                ReplayFrame(
                    snapshot_id=_make_id("snap"),
                    market=market,
                    evidence=evidence,
                    features=features,
                    resolution=None,
                    raw_payload={"discovery": payload, "executable": executable_state.get(payload["market_id"], {})},
                )
            )
        frames.sort(
            key=lambda frame: frame.features.metadata.get("hours_to_expiry", math.inf)
            if frame.features
            else math.inf
        )
        return frames


class ReplayDataSource:
    def __init__(self, replay_file: str):
        self.replay_file = replay_file
        self.feature_store = FeatureStore()

    def iter_frames(self) -> Iterable[ReplayFrame]:
        with open(self.replay_file, "r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                payload = json.loads(stripped)
                if not isinstance(payload, dict):
                    continue
                yield self._build_frame(payload, line_number=line_number)

    def iter_markets(self) -> Iterable[Dict]:
        for frame in self.iter_frames():
            yield frame.market.to_dict()

    def _build_frame(self, payload: Dict, *, line_number: int) -> ReplayFrame:
        snapshot_id = str(payload.get("snapshot_id") or f"replay-{line_number}")

        if "market" in payload:
            market_payload = payload["market"]
            evidence_payload = payload.get("evidence", [])
            resolution = payload.get("resolution")
        else:
            market_payload = payload
            evidence_payload = payload.get("evidence", [])
            resolution = (
                {"resolved_outcome": payload.get("resolved_outcome")}
                if payload.get("resolved_outcome") is not None
                else None
            )

        market = normalize_market_snapshot(
            market_payload,
            market_payload.get("orderbook")
            or market_payload.get("executable")
            or {
                key: market_payload.get(key)
                for key in (
                    "token_id",
                    "best_bid",
                    "best_ask",
                    "last_trade_price",
                    "spread",
                    "depth_bid",
                    "depth_ask",
                    "tick_size",
                    "fee_schedule",
                    "open_interest",
                    "market_status",
                    "orderbook_timestamp",
                )
                if key in market_payload
            },
            forecast_timestamp=market_payload.get("forecast_timestamp"),
        )
        evidence = [self._normalize_evidence(item, market) for item in evidence_payload]
        feature_payload = payload.get("features")
        features = (
            FeatureSnapshot(**feature_payload)
            if isinstance(feature_payload, dict) and "market_microstructure" in feature_payload
            else self.feature_store.build(market, evidence)
        )

        if resolution and isinstance(resolution, dict):
            outcome = resolution.get("resolved_outcome")
            if outcome is not None:
                market.resolved_outcome = outcome

        return ReplayFrame(
            snapshot_id=snapshot_id,
            market=market,
            evidence=evidence,
            features=features,
            resolution=resolution,
            raw_payload=payload,
        )

    @staticmethod
    def _normalize_evidence(payload: Dict, market: MarketObservation) -> EvidenceRecord:
        return EvidenceRecord(
            evidence_id=str(payload.get("evidence_id") or _make_id("evidence")),
            source_url=payload.get("source_url", ""),
            source_type=payload.get("source_type", payload.get("type", "unknown")),
            publication_timestamp=float(payload.get("publication_timestamp", market.forecast_timestamp)),
            ingestion_timestamp=float(payload.get("ingestion_timestamp", market.forecast_timestamp)),
            source_credibility=_safe_float(payload.get("source_credibility"), 0.5),
            source_credibility_metadata=payload.get("source_credibility_metadata", {}),
            extracted_claims=list(payload.get("extracted_claims", [])),
            summary=payload.get("summary", ""),
            linked_event_id=payload.get("linked_event_id", market.event_id),
            linked_market_id=payload.get("linked_market_id", market.market_id),
            version=payload.get("version", "v1"),
            raw_payload=payload,
        )
