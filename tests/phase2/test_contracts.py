"""Phase 2 contract and assertion tests."""

from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
import sys

sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.canonical import load_json_strict
from market_platform_foundation.contracts.envelope import validate_envelope
from market_platform_foundation.contracts.identity import normalized_event_id, sort_events
from market_platform_foundation.contracts.temporal import check_tc001
from market_platform_foundation.phase2_assertions import MANDATORY_IDS, aggregate_status, build_registry
from market_platform_foundation.replay.lifecycle import run_replay, run_root_hash

FIXTURE_DIR = ROOT / "docs/research/fixtures/phase2-synthetic"


class Phase2ContractTests(unittest.TestCase):
    def test_registry_has_four_predicates(self) -> None:
        registry = build_registry(ROOT / "manifests/phase2/assertion-predicates.json")
        self.assertEqual(set(registry["mandatory_ids"]), set(MANDATORY_IDS))

    def test_historical_fixture_validates(self) -> None:
        event = load_json_strict(FIXTURE_DIR / "base-historical-bar.json")
        self.assertIsInstance(event, dict)
        timestamp_states = {k: str(v) for k, v in dict(event.pop("timestamp_states", {})).items()}
        acquisition_mode = str(event.pop("acquisition_mode"))
        reasons = validate_envelope(event, timestamp_states=timestamp_states, acquisition_mode=acquisition_mode)
        self.assertEqual(reasons, [])

    def test_tc001_pass_and_fail(self) -> None:
        consumed = [{"available_time": 10, "normalized_event_id": "a"}]
        status, reasons = check_tc001(consumed, 10)
        self.assertEqual(status, "PASS")
        self.assertEqual(reasons, [])
        status, reasons = check_tc001(consumed, 9)
        self.assertEqual(status, "FAIL")
        self.assertTrue(reasons)

    def test_deterministic_replay_root(self) -> None:
        events = [
            {
                "available_time": 100,
                "event_time": 90,
                "normalized_event_id": "00000000-0000-5000-8000-000000000001",
            },
            {
                "available_time": 200,
                "event_time": 190,
                "normalized_event_id": "00000000-0000-5000-8000-000000000002",
            },
        ]
        state_a = run_replay(events, clocks=[100, 200], decision_times=[200])
        state_b = run_replay(events, clocks=[100, 200], decision_times=[200])
        self.assertEqual(run_root_hash(state_a), run_root_hash(state_b))

    def test_normalized_event_id_is_deterministic(self) -> None:
        first = normalized_event_id(
            provider_id="P",
            venue_id="V",
            publisher_id="U",
            channel_id="C",
            source_instance_id="I",
            source_record_id="R",
            source_revision_id="REV",
            event_family="BAR",
        )
        second = normalized_event_id(
            provider_id="P",
            venue_id="V",
            publisher_id="U",
            channel_id="C",
            source_instance_id="I",
            source_record_id="R",
            source_revision_id="REV",
            event_family="BAR",
        )
        self.assertEqual(first, second)

    def test_aggregate_status_all_pass(self) -> None:
        results = [{"status": "PASS"}, {"status": "PASS"}]
        self.assertEqual(aggregate_status(results), "PASS")


if __name__ == "__main__":
    unittest.main()
