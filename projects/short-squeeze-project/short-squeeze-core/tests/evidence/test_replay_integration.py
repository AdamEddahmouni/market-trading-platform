import hashlib
import json
from pathlib import Path

from squeeze_core.contracts import ReplayMode
from squeeze_core.evidence import build_point_in_time_evidence
from squeeze_core.replay import ReplayEngine, load_fixture

from tests.phase_1c_fixture_builders import (
    build_phase_1c_artifacts,
    load_evidence_policy,
)


EVIDENCE_ROOT = Path("tests/fixtures/evidence")


def test_mixed_fixture_covers_required_point_in_time_cases() -> None:
    document = json.loads((EVIDENCE_ROOT / "mixed_finviz_ibkr_cases.json").read_text())
    types = {case["fixture_type"] for case in document["scenario_coverage"]}

    assert len(types) >= 18
    assert {
        "FINVIZ_ONLY",
        "IBKR_ONLY",
        "CURRENT_FINVIZ_STALE_IBKR",
        "STALE_FINVIZ_CURRENT_IBKR",
        "UNKNOWN_FRESHNESS_BOTH",
        "MISSING_FINVIZ_SHORT_FLOAT_KNOWN_IBKR_FEE",
        "HIGH_FINVIZ_SHORT_FLOAT_MISSING_BORROW",
        "ZERO_IBKR_AVAILABILITY_MISSING_FINVIZ_FLOAT",
        "CONFLICTING_DUPLICATE_FINVIZ",
        "FUTURE_FINVIZ",
        "FUTURE_IBKR",
        "SAME_VALUE_DIFFERENT_TIMES",
        "COMPATIBLE_FLOAT_CONFLICT",
        "INVALID_FINVIZ_PRICE_PARTIAL",
        "DUPLICATE_RAW_HASH",
        "MULTIPLE_EXCHANGES",
        "OTHER_SYMBOL_EXCLUDED",
        "DELAYED_POLICY",
    } <= types


def test_generated_mixed_jsonl_and_hash_metadata_match_committed_bytes() -> None:
    artifacts = build_phase_1c_artifacts()
    committed = (EVIDENCE_ROOT / "normalized_point_in_time.jsonl").read_bytes()
    expected = json.loads((EVIDENCE_ROOT / "expected_bundle_metadata.json").read_text())

    assert artifacts.jsonl == committed
    assert hashlib.sha256(committed).hexdigest() == expected["mixed_jsonl_sha256"]
    assert artifacts.replay.result_hash == expected["strict_replay_sha256"]
    assert artifacts.bundle.bundle_hash == expected["evidence_bundle_sha256"]


def test_mixed_replay_rebuilds_the_same_bundle_deterministically() -> None:
    observations = load_fixture(EVIDENCE_ROOT / "normalized_point_in_time.jsonl")
    replay = ReplayEngine(mode=ReplayMode.STRICT).replay(observations)
    policy = load_evidence_policy()
    first = build_point_in_time_evidence("TESTA", replay.observations, policy)
    second = build_point_in_time_evidence("TESTA", replay.observations, policy)
    expected = json.loads((EVIDENCE_ROOT / "expected_bundle_metadata.json").read_text())

    assert first == second
    assert first.bundle_hash == expected["evidence_bundle_sha256"]
    assert [item.event_type.value for item in first.observations] == [
        "MARKET_SNAPSHOT",
        "BORROW_FEE",
        "BORROW_AVAILABILITY",
    ]


def test_existing_phase_1a_and_1b_fixture_hashes_remain_unchanged() -> None:
    expected = json.loads((EVIDENCE_ROOT / "expected_bundle_metadata.json").read_text())
    paths = {
        "phase_1a_minimal_sha256": Path("tests/fixtures/minimal_session.jsonl"),
        "phase_1a_quality_sha256": Path("tests/fixtures/quality_edge_cases.jsonl"),
        "phase_1a_out_of_order_sha256": Path("tests/fixtures/out_of_order_session.jsonl"),
        "phase_1b_ibkr_jsonl_sha256": Path(
            "tests/fixtures/providers/ibkr/normalized_session.jsonl"
        ),
    }
    for key, path in paths.items():
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected[key]
