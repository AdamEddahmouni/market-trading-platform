"""Repository conformance tests (BUILD 04.5)."""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.intelligence.persistence import (  # noqa: E402
    InMemoryIntelligenceRepository,
    RepositoryConflictError,
    RepositoryPutResult,
)
from tests.intelligence.test_persistence_fixtures import (  # noqa: E402
    DECISION_NS,
    INSTRUMENT,
    populate_all_record_types,
    sample_event,
    sample_forecast,
    sample_outcome,
    sample_signal,
    sample_snapshot,
)
from tests.intelligence.test_routing_contracts import sample_detection, sample_route  # noqa: E402


class RepositoryConformanceTests(unittest.TestCase):
    backend_name = "in_memory"

    def setUp(self) -> None:
        self.repo = InMemoryIntelligenceRepository()

    def test_round_trip_all_record_types(self) -> None:
        populate_all_record_types(self.repo)
        self.repo.put_detection(sample_detection())
        self.repo.put_routing_decision(sample_route())
        self.assertEqual(self.repo.get_event("evt-1").event_id, "evt-1")
        self.assertEqual(self.repo.get_detection("DET-abc").detection_id, "DET-abc")
        self.assertEqual(
            self.repo.get_routing_decision("ROUTE-abc").routing_decision_id,
            "ROUTE-abc",
        )
        self.assertEqual(self.repo.get_snapshot("snap-1").snapshot_id, "snap-1")
        self.assertEqual(self.repo.get_signal("sig-1").signal_id, "sig-1")
        self.assertEqual(self.repo.get_evidence("ev-1").evidence_id, "ev-1")
        self.assertEqual(self.repo.get_hypothesis("hyp-1").hypothesis_id, "hyp-1")
        self.assertEqual(self.repo.get_forecast("fc-1").forecast_id, "fc-1")
        self.assertEqual(self.repo.get_opportunity("opp-1").opportunity_id, "opp-1")
        self.assertEqual(self.repo.get_outcome("out-1").outcome_id, "out-1")
        self.assertEqual(self.repo.get_run_manifest("run-1").run_id, "run-1")

    def test_idempotent_write_same_content(self) -> None:
        event = sample_event()
        self.assertEqual(self.repo.put_event(event), RepositoryPutResult.INSERTED)
        self.assertEqual(self.repo.put_event(event), RepositoryPutResult.ALREADY_PRESENT)

    def test_conflict_same_id_different_content(self) -> None:
        self.repo.put_forecast(sample_forecast(probability=0.60))
        with self.assertRaises(RepositoryConflictError):
            self.repo.put_forecast(sample_forecast(probability=0.70))
        stored = self.repo.get_forecast("fc-1")
        self.assertEqual(stored.estimate.probability, 0.60)

    def test_not_found_returns_none(self) -> None:
        self.assertIsNone(self.repo.get_event("missing"))

    def test_input_not_mutated_on_put(self) -> None:
        event = sample_event(payload={"px": 100})
        before = copy.deepcopy(event.payload)
        self.repo.put_event(event)
        self.assertEqual(event.payload, before)

    def test_event_as_of_boundary(self) -> None:
        t = DECISION_NS
        self.repo.put_event(sample_event("evt-before", available_time_ns=t - 1))
        self.repo.put_event(sample_event("evt-at", available_time_ns=t))
        self.repo.put_event(sample_event("evt-after", available_time_ns=t + 1))
        ids = [event.event_id for event in self.repo.query_events_as_of(t)]
        self.assertEqual(ids, ["evt-before", "evt-at"])

    def test_delayed_event_excluded(self) -> None:
        t = DECISION_NS
        self.repo.put_event(
            sample_event(
                "evt-delayed",
                event_time_ns=t - 1_000_000_000,
                available_time_ns=t + 1_000_000_000,
            )
        )
        ids = [event.event_id for event in self.repo.query_events_as_of(t)]
        self.assertEqual(ids, [])

    def test_iter_events_by_availability_range(self) -> None:
        t = DECISION_NS
        self.repo.put_event(sample_event("evt-early", available_time_ns=t - 5))
        self.repo.put_event(sample_event("evt-in", available_time_ns=t))
        self.repo.put_event(sample_event("evt-late", available_time_ns=t + 5))
        rows = self.repo.iter_events_by_availability(
            start_time_ns=t - 1,
            end_time_ns=t + 1,
        )
        self.assertEqual([event.event_id for event in rows], ["evt-in"])

    def test_input_order_independence(self) -> None:
        other = InMemoryIntelligenceRepository()
        events = [
            sample_event("evt-a", available_time_ns=DECISION_NS - 2),
            sample_event("evt-b", available_time_ns=DECISION_NS - 1),
            sample_event("evt-c", available_time_ns=DECISION_NS),
        ]
        for event in events:
            self.repo.put_event(event)
        for event in reversed(events):
            other.put_event(event)
        left = [event.event_id for event in self.repo.query_events_as_of(DECISION_NS)]
        right = [event.event_id for event in other.query_events_as_of(DECISION_NS)]
        self.assertEqual(left, right)

    def test_limit_enforced(self) -> None:
        for index in range(5):
            self.repo.put_event(
                sample_event(f"evt-{index}", available_time_ns=DECISION_NS - index)
            )
        ids = [event.event_id for event in self.repo.query_events_as_of(DECISION_NS, limit=2)]
        self.assertEqual(len(ids), 2)

    def test_invalid_limit_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.repo.query_events_as_of(DECISION_NS, limit=0)

    def test_snapshot_does_not_embed_events(self) -> None:
        self.repo.put_snapshot(sample_snapshot())
        snapshot = self.repo.get_snapshot("snap-1")
        self.assertEqual(len(snapshot.source_event_refs), 1)
        self.assertIsNone(self.repo.get_event("evt-1"))

    def test_secondary_queries(self) -> None:
        populate_all_record_types(self.repo)
        self.assertEqual(len(self.repo.get_evidence_by_snapshot("snap-1")), 1)
        self.assertEqual(len(self.repo.get_forecasts_by_instrument(INSTRUMENT)), 1)
        self.assertEqual(len(self.repo.get_outcomes_by_forecast("fc-1")), 1)
        self.assertEqual(len(self.repo.get_opportunities_by_instrument(INSTRUMENT)), 1)
        self.assertEqual(len(self.repo.query_signals_as_of(DECISION_NS, instrument_id=INSTRUMENT)), 1)

    def test_batch_getters(self) -> None:
        populate_all_record_types(self.repo)
        events = self.repo.get_events(("evt-1", "missing"))
        signals = self.repo.get_signals(("sig-1", "missing"))
        self.assertEqual([event.event_id for event in events], ["evt-1"])
        self.assertEqual([signal.signal_id for signal in signals], ["sig-1"])

    def test_health(self) -> None:
        health = self.repo.check_health()
        self.assertTrue(health["available"])
        self.assertEqual(health["backend"], "in_memory")


if __name__ == "__main__":
    unittest.main()
