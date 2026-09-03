import hashlib
import json
from pathlib import Path

from squeeze_core.contracts import ReplayMode
from squeeze_core.replay import ReplayEngine, load_fixture

from tests.provider_fixture_builders import build_ibkr_normalized_session


FIXTURE_ROOT = Path("tests/fixtures/providers/ibkr")


def test_generated_normalized_fixture_matches_committed_bytes_and_hash() -> None:
    generated = build_ibkr_normalized_session()
    committed = (FIXTURE_ROOT / "normalized_session.jsonl").read_bytes()
    expected = json.loads((FIXTURE_ROOT / "expected_artifact_hashes.json").read_text())

    assert generated == committed
    assert hashlib.sha256(committed).hexdigest() == expected["normalized_session_sha256"]


def test_normalized_fixture_validates_and_replays_deterministically() -> None:
    observations = load_fixture(FIXTURE_ROOT / "normalized_session.jsonl")
    first = ReplayEngine(mode=ReplayMode.STRICT).replay(observations)
    second = ReplayEngine(mode=ReplayMode.STRICT).replay(observations)
    expected = json.loads((FIXTURE_ROOT / "expected_artifact_hashes.json").read_text())

    assert len(observations) == 6
    assert first.to_bytes() == second.to_bytes()
    assert first.result_hash == expected["strict_replay_sha256"]
