import math

from polybot.calibration import CalibrationManager, UncertaintyEngine
from polybot.config import CalibrationConfig, StrategyConfig, UncertaintyConfig
from polybot.data_layer import EvidenceStore, normalize_market_snapshot
from polybot.types import EvidenceRecord, ForecastRecord


def test_normalize_market_snapshot_merges_discovery_and_executable_payloads():
    market = normalize_market_snapshot(
        {
            "market_id": "m1",
            "event_id": "e1",
            "title": "Will normalization work?",
            "description": "desc",
            "resolution_criteria": "rules",
            "category": "Crypto",
            "volume": 1250,
            "forecast_timestamp": 1000,
        },
        {
            "token_id": "tok-1",
            "best_bid": 0.41,
            "best_ask": 0.45,
            "depth_bid": 120,
            "depth_ask": 90,
            "tick_size": 0.01,
            "fee_schedule": {"maker_bps": 5, "taker_bps": 80},
        },
    )

    assert market.market_id == "m1"
    assert market.event_id == "e1"
    assert market.token_id == "tok-1"
    assert math.isclose(market.mid_price, 0.43)
    assert math.isclose(market.spread, 0.04)
    assert market.raw_provider_payloads["discovery"]["title"] == "Will normalization work?"
    assert market.raw_provider_payloads["executable"]["token_id"] == "tok-1"


def test_evidence_store_blocks_future_evidence():
    store = EvidenceStore(
        records=[
            EvidenceRecord(
                evidence_id="old",
                source_url="https://example.com/old",
                source_type="news",
                publication_timestamp=100.0,
                ingestion_timestamp=105.0,
                source_credibility=0.9,
                source_credibility_metadata={},
                extracted_claims=["old"],
                summary="old summary",
                linked_event_id="e1",
                linked_market_id="m1",
            ),
            EvidenceRecord(
                evidence_id="future",
                source_url="https://example.com/future",
                source_type="news",
                publication_timestamp=500.0,
                ingestion_timestamp=505.0,
                source_credibility=0.95,
                source_credibility_metadata={},
                extracted_claims=["future"],
                summary="future summary",
                linked_event_id="e1",
                linked_market_id="m1",
            ),
        ]
    )

    evidence = store.get_replay_safe_evidence(
        market_id="m1",
        event_id="e1",
        as_of_timestamp=200.0,
        max_items=10,
    )

    assert [item.evidence_id for item in evidence] == ["old"]


def test_calibration_artifact_contains_version_and_predicts():
    manager = CalibrationManager(
        CalibrationConfig(
            methods_priority=["beta", "logistic"],
            min_isotonic_samples=1000,
            artifact_version="cal-test",
        )
    )
    records = [
        ForecastRecord("m1", "e1", 1.0, "crypto", 0.20, 0.20, 0.25, "NO", 0.1, 0, "identity"),
        ForecastRecord("m2", "e2", 2.0, "crypto", 0.80, 0.80, 0.70, "YES", 0.1, 0, "identity"),
        ForecastRecord("m3", "e3", 3.0, "crypto", 0.70, 0.70, 0.55, "YES", 0.1, 0, "identity"),
        ForecastRecord("m4", "e4", 4.0, "crypto", 0.30, 0.30, 0.40, "NO", 0.1, 0, "identity"),
    ]

    artifact = manager.fit(records, category="crypto", as_of_timestamp=10.0)
    calibrated = manager.calibrate(0.76, artifact)

    assert artifact.version == "cal-test"
    assert artifact.sample_count == 4
    assert artifact.method in {"beta", "logistic"}
    assert 0.0 < calibrated < 1.0


def test_uncertainty_rises_with_dispersion():
    engine = UncertaintyEngine(UncertaintyConfig())

    low_dispersion = engine.estimate(
        market_id="m1",
        sample_probabilities=[0.60, 0.61, 0.59],
        rationales=["same thesis", "same thesis", "same thesis"],
        calibration_residual=0.02,
    )
    high_dispersion = engine.estimate(
        market_id="m2",
        sample_probabilities=[0.20, 0.55, 0.85],
        rationales=["bull thesis", "different bear thesis", "another angle entirely"],
        calibration_residual=0.20,
    )

    assert high_dispersion.uncertainty_score > low_dispersion.uncertainty_score
    assert high_dispersion.forecast_variance > low_dispersion.forecast_variance

