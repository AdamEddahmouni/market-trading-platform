import json
from pathlib import Path

from phase_1i_fixture_builders import build_phase_1i_artifacts
from squeeze_core.contracts import EventType, ReplayMode
from squeeze_core.evidence import CoverageDomain
from squeeze_core.replay import ReplayEngine, load_fixture
from squeeze_core.serialization import canonical_json_bytes


ROOT = Path(__file__).parents[1] / "fixtures"


def test_phase_1i_mixed_fixture_replays_all_prior_domains_plus_trades_quotes():
    observations = load_fixture(ROOT / "evidence" / "normalized_phase_1i_point_in_time.jsonl")
    replay = ReplayEngine(mode=ReplayMode.STRICT).replay(observations)
    event_types = {item.event_type for item in replay.observations}
    assert {
        EventType.MARKET_SNAPSHOT, EventType.BORROW_FEE, EventType.BORROW_AVAILABILITY,
        EventType.PUBLISHED_SHORT_INTEREST, EventType.SEC_FILING, EventType.TRADING_HALT,
        EventType.NEWS_ITEM, EventType.BAR, EventType.TRADE, EventType.QUOTE,
    } <= event_types


def test_phase_1i_artifacts_match_committed_hashes_and_repeat():
    first = build_phase_1i_artifacts()
    second = build_phase_1i_artifacts()
    expected = json.loads(
        (ROOT / "evidence" / "expected_phase_1i_bundle_metadata.json").read_text(encoding="utf-8")
    )
    assert first["metadata"] == expected == second["metadata"]
    assert first["jsonl_bytes"] == second["jsonl_bytes"]
    assert canonical_json_bytes(first["timeline_bundles"]) == canonical_json_bytes(second["timeline_bundles"])
    assert first["series"] == second["series"]


def test_timeline_keeps_originals_then_correction_and_cancellation_immutable():
    bundles = build_phase_1i_artifacts()["timeline_bundles"]
    expected = {
        "before_original_publication": [],
        "after_publication_before_receipt": [],
        "after_original_receipt": ["phase1i-quote-original", "phase1i-trade-original"],
        "before_correction_receipt": ["phase1i-quote-original", "phase1i-trade-original"],
        "after_correction_receipt": ["phase1i-quote-corrected", "phase1i-quote-original", "phase1i-trade-corrected", "phase1i-trade-original"],
        "before_cancellation_receipt": ["phase1i-quote-corrected", "phase1i-quote-original", "phase1i-trade-corrected", "phase1i-trade-original"],
        "after_cancellation_receipt": ["phase1i-quote-cancelled", "phase1i-quote-corrected", "phase1i-quote-original", "phase1i-trade-corrected", "phase1i-trade-original"],
    }
    for label, source_ids in expected.items():
        actual = sorted(
            item.source_record_id for item in bundles[label].observations
            if item.event_type in {EventType.TRADE, EventType.QUOTE}
            and item.source_record_id.startswith("phase1i-")
            and "provider-b" not in item.source_record_id
        )
        assert actual == source_ids
    final = bundles["final"]
    coverage = {item.domain: item for item in final.source_coverage}
    assert coverage[CoverageDomain.TRADES].observation_ids
    assert coverage[CoverageDomain.QUOTES].observation_ids


def test_mixed_manifest_is_objective_and_contains_required_structural_cases():
    document = json.loads((ROOT / "evidence" / "mixed_phase_1i_cases.json").read_text(encoding="utf-8"))
    assert document["contains_credentials"] is False
    assert document["contains_account_data"] is False
    assert document["contains_real_symbols"] is False
    assert document["analytics"] is False
    names = {item["case_id"] for item in document["cases"]}
    assert {
        "locked-quote", "crossed-quote", "one-sided-quote", "missing-sequence",
        "out-of-order-sequence", "active-halt-interaction", "cross-provider-same-event",
        "conflicting-quote", "unknown-venue", "unknown-scope", "future-publication",
        "future-receipt", "correction-after-as-of", "cancellation-after-as-of",
    } <= names


def test_phase_1h_anchors_are_embedded_unchanged():
    phase_1i = build_phase_1i_artifacts()["metadata"]
    phase_1h = json.loads(
        (ROOT / "evidence" / "expected_phase_1h_bundle_metadata.json").read_text(encoding="utf-8")
    )
    assert phase_1i["phase_1h_mixed_jsonl_sha256"] == phase_1h["mixed_jsonl_sha256"]
    assert phase_1i["phase_1h_strict_replay_sha256"] == phase_1h["strict_replay_sha256"]
    assert phase_1i["phase_1h_final_bundle_sha256"] == phase_1h["final_bundle_sha256"]
    assert phase_1i["phase_1h_serialized_final_bundle_sha256"] == phase_1h["serialized_final_bundle_sha256"]


def test_replayed_metadata_retains_trade_quote_event_and_capture_ages():
    observations = load_fixture(ROOT / "evidence" / "normalized_phase_1i_point_in_time.jsonl")
    from datetime import datetime
    from squeeze_core.evidence import PointInTimeEvidencePolicy, build_point_in_time_evidence

    bundle = build_point_in_time_evidence(
        "TESTA",
        observations,
        PointInTimeEvidencePolicy(
            as_of=datetime.fromisoformat("2026-01-31T14:36:01+00:00"),
            include_trades_domain=True,
            include_quotes_domain=True,
        ),
    )
    trade = next(item for item in bundle.observations if item.source_record_id == "phase1i-trade-original")
    age = next(item for item in bundle.observation_ages if item.observation_id == trade.observation_id)
    assert age.event_age_ms is not None
    assert age.capture_age_ms is not None
