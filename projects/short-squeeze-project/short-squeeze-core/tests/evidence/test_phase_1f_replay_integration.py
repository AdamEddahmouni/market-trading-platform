import json
from pathlib import Path

from phase_1f_fixture_builders import build_phase_1f_artifacts
from squeeze_core.contracts import EventType, ReplayMode
from squeeze_core.evidence import CoverageDomain, HaltState
from squeeze_core.replay import ReplayEngine, load_fixture
from squeeze_core.serialization import canonical_json_bytes


ROOT = Path(__file__).parents[1] / "fixtures"


def test_phase_1f_mixed_fixture_replays_all_independent_domains() -> None:
    fixture = ROOT / "evidence" / "normalized_phase_1f_point_in_time.jsonl"
    observations = load_fixture(fixture)
    replay = ReplayEngine(mode=ReplayMode.STRICT).replay(observations)
    event_types = {item.event_type for item in replay.observations}
    assert {
        EventType.MARKET_SNAPSHOT,
        EventType.BORROW_FEE,
        EventType.BORROW_AVAILABILITY,
        EventType.PUBLISHED_SHORT_INTEREST,
        EventType.SEC_FILING,
        EventType.TRADING_HALT,
    } <= event_types


def test_phase_1f_artifacts_match_committed_hashes_and_repeat() -> None:
    first = build_phase_1f_artifacts()
    second = build_phase_1f_artifacts()
    expected = json.loads(
        (ROOT / "evidence" / "expected_phase_1f_bundle_metadata.json").read_text(
            encoding="utf-8"
        )
    )
    assert first["metadata"] == expected
    assert second["metadata"] == expected
    assert first["jsonl_bytes"] == second["jsonl_bytes"]
    assert canonical_json_bytes(first["timeline_bundles"]) == canonical_json_bytes(
        second["timeline_bundles"]
    )


def test_timeline_states_and_halt_coverage_are_objective() -> None:
    artifacts = build_phase_1f_artifacts()
    states = {
        label: bundle.halt_state.state
        for label, bundle in artifacts["timeline_bundles"].items()
    }
    assert states == {
        "before_announcement": HaltState.NOT_OBSERVED,
        "after_announcement_receipt": HaltState.HALTED,
        "after_quote_schedule": HaltState.QUOTE_RESUMPTION_SCHEDULED,
        "after_quotes_resumed": HaltState.QUOTES_RESUMED,
        "after_trade_schedule": HaltState.TRADE_RESUMPTION_SCHEDULED,
        "after_trading_resumed": HaltState.TRADING_RESUMED,
    }
    final = artifacts["timeline_bundles"]["after_trading_resumed"]
    halt_coverage = next(
        item for item in final.source_coverage if item.domain is CoverageDomain.TRADING_HALTS
    )
    assert halt_coverage.observation_ids == final.halt_state.supporting_observation_ids
    serialized = canonical_json_bytes(final).decode("utf-8").lower()
    for forbidden in ("bullish", "bearish", "buy signal", "sell signal", "recommendation"):
        assert forbidden not in serialized


def test_mixed_case_manifest_has_all_fifteen_nondirectional_cases() -> None:
    document = json.loads(
        (ROOT / "evidence" / "mixed_phase_1f_cases.json").read_text(encoding="utf-8")
    )
    assert len(document["cases"]) == 15
    assert not document["contains_credentials"]
    assert not document["contains_account_data"]
    assert not document["contains_real_symbols"]
    assert document["directional_interpretation"] is False
