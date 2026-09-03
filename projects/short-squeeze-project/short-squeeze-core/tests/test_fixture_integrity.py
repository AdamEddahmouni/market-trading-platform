import hashlib
import re
from pathlib import Path

from squeeze_core.contracts import BorrowFeePayload, EventType, QualityState, ReplayMode
from squeeze_core.replay import ReplayEngine, ReplayValidationError, load_fixture


FIXTURE_DIR = Path(__file__).parent / "fixtures"
EXPECTED = {
    "minimal_session.jsonl": (13, "ceeba255e569c3efc61c92f60a763057a9b68bb4c19cea4b12999f95ec8aabec"),
    "quality_edge_cases.jsonl": (9, "475e5a6eb0070ae7586cecf3055fbec779b0f5ab410a1e8b070d1f6792289025"),
    "out_of_order_session.jsonl": (3, "1d22c176cacbb6e46210d458a4bdbb7b371aa13386db89c7c83072d788e8a18c"),
}
SECRET_PATTERN = re.compile(
    rb"(?i)(api[_-]?key|secret|password|token|account[_-]?id)\s*[:=]\s*[^,}\s]+"
)


def test_every_fixture_validates_and_matches_documented_count_and_hash() -> None:
    for name, (expected_count, expected_hash) in EXPECTED.items():
        path = FIXTURE_DIR / name
        observations = load_fixture(path)
        assert len(observations) == expected_count
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected_hash


def test_minimal_fixture_covers_every_required_event_type() -> None:
    observations = load_fixture(FIXTURE_DIR / "minimal_session.jsonl")
    assert {item.event_type for item in observations} == set(EventType) - {
        EventType.MARKET_SNAPSHOT
    }
    ReplayEngine(mode=ReplayMode.STRICT).replay(observations)


def test_quality_fixture_covers_required_edge_semantics() -> None:
    observations = load_fixture(FIXTURE_DIR / "quality_edge_cases.jsonl")
    states = {item.quality.state for item in observations}
    assert {
        QualityState.KNOWN_VALUE,
        QualityState.MISSING,
        QualityState.STALE,
        QualityState.DELAYED,
        QualityState.INVALID,
        QualityState.CONFLICTED,
    } <= states
    assert any(item.symbol is None and item.event_type is EventType.NEWS_ITEM for item in observations)
    assert sum(item.quality.state is QualityState.CONFLICTED for item in observations) == 2
    zero_fee, missing_fee = observations[:2]
    assert isinstance(zero_fee.payload, BorrowFeePayload)
    assert isinstance(missing_fee.payload, BorrowFeePayload)
    assert zero_fee.payload.annualized_fee_percent == 0
    assert missing_fee.payload.annualized_fee_percent is None


def test_out_of_order_fixture_is_rejected_strictly_and_normalized_with_diagnostic() -> None:
    observations = load_fixture(FIXTURE_DIR / "out_of_order_session.jsonl")
    try:
        ReplayEngine(mode=ReplayMode.STRICT).replay(observations)
    except ReplayValidationError:
        pass
    else:
        raise AssertionError("strict replay accepted the out-of-order fixture")
    result = ReplayEngine(mode=ReplayMode.NORMALIZED).replay(observations)
    assert [item.source_record_id for item in result.observations] == ["ooo-1", "ooo-2", "ooo-3"]
    assert result.diagnostics[0].code == "INPUT_ORDER_NORMALIZED"


def test_fixtures_are_synthetic_and_contain_no_secret_like_values() -> None:
    for name in EXPECTED:
        raw = (FIXTURE_DIR / name).read_bytes()
        assert SECRET_PATTERN.search(raw) is None
        observations = load_fixture(FIXTURE_DIR / name)
        assert all(item.symbol in {None, "TESTA", "TESTB"} for item in observations)
        assert b"localhost" not in raw
        assert b"@" not in raw


def test_minimal_fixture_replay_is_byte_identical_across_runs() -> None:
    observations = load_fixture(FIXTURE_DIR / "minimal_session.jsonl")
    first = ReplayEngine(mode=ReplayMode.STRICT).replay(observations)
    second = ReplayEngine(mode=ReplayMode.STRICT).replay(observations)
    assert first.to_bytes() == second.to_bytes()
    assert first.result_hash == second.result_hash
