"""Snapshot content identity tests (BUILD 05)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.intelligence.contracts import (  # noqa: E402
    ContractReference,
    IntelligenceScope,
    QualityState,
    QualitySummary,
)
from market_platform_foundation.intelligence.snapshots import (  # noqa: E402
    SNAPSHOT_ID_PREFIX,
    compose_snapshot,
    fingerprint_from_snapshot_parts,
    semantic_payload,
    snapshot_id_from_fingerprint,
)
from market_platform_foundation.intelligence.snapshots.canonical import sort_references  # noqa: E402
from tests.intelligence.test_snapshot_fixtures import (  # noqa: E402
    T,
    INSTRUMENT,
    SCOPE,
    default_request,
    sample_event,
    use_quality_decision,
)


class SnapshotIdentityTests(unittest.TestCase):
    def test_fingerprint_excludes_created_at(self) -> None:
        request = default_request()
        events = (sample_event("evt-1", available_time_ns=T),)
        snap_a, fp = compose_snapshot(
            request=request,
            quality_decision=use_quality_decision(),
            selected_events=events,
            selected_signals=(),
        )
        object.__setattr__(snap_a, "created_at_ns", T + 999)
        self.assertEqual(snap_a.metadata["content_fingerprint"], fp)

    def test_reference_sort_determinism(self) -> None:
        refs = (
            ContractReference(kind="event", id="b"),
            ContractReference(kind="event", id="a"),
        )
        self.assertEqual(
            [ref.id for ref in sort_references(refs)],
            ["a", "b"],
        )

    def test_hash_changes_on_source_set(self) -> None:
        request = default_request()
        fp_one = compose_snapshot(
            request=request,
            quality_decision=use_quality_decision(),
            selected_events=(sample_event("evt-1", available_time_ns=T),),
            selected_signals=(),
        )[1]
        fp_two = compose_snapshot(
            request=request,
            quality_decision=use_quality_decision(),
            selected_events=(
                sample_event("evt-1", available_time_ns=T),
                sample_event("evt-2", available_time_ns=T - 1),
            ),
            selected_signals=(),
        )[1]
        self.assertNotEqual(fp_one, fp_two)

    def test_hash_changes_on_quality_semantics(self) -> None:
        request = default_request()
        good = compose_snapshot(
            request=request,
            quality_decision=use_quality_decision(),
            selected_events=(sample_event(),),
            selected_signals=(),
        )[1]
        degraded = compose_snapshot(
            request=request,
            quality_decision=__import__(
                "tests.intelligence.test_snapshot_fixtures",
                fromlist=["degrade_quality_decision"],
            ).degrade_quality_decision(),
            selected_events=(sample_event(),),
            selected_signals=(),
        )[1]
        self.assertNotEqual(good, degraded)

    def test_snapshot_id_prefix(self) -> None:
        payload = semantic_payload(
            decision_time_ns=T,
            scope=SCOPE,
            quality=QualitySummary(state=QualityState.GOOD),
            source_event_refs=(),
            source_signal_refs=(),
            component_refs=(),
            composition_policy=default_request().composition_policy,
        )
        fingerprint = fingerprint_from_snapshot_parts(
            decision_time_ns=T,
            scope=SCOPE,
            quality=QualitySummary(state=QualityState.GOOD),
            source_event_refs=(),
            source_signal_refs=(),
            component_refs=(),
            composition_policy=default_request().composition_policy,
        )
        snapshot_id = snapshot_id_from_fingerprint(fingerprint)
        self.assertTrue(snapshot_id.startswith(SNAPSHOT_ID_PREFIX))

    def test_kind_distinguishes_colliding_ids(self) -> None:
        request = default_request()
        event_fp = compose_snapshot(
            request=request,
            quality_decision=use_quality_decision(),
            selected_events=(sample_event("shared-id", available_time_ns=T),),
            selected_signals=(),
        )[1]
        from market_platform_foundation.intelligence.contracts import SignalV1  # noqa: E402
        from tests.intelligence.test_snapshot_fixtures import QUALITY  # noqa: E402

        signal = SignalV1(
            signal_id="shared-id",
            schema_version="1",
            signal_type="TEST",
            scope=SCOPE,
            as_of_time_ns=T,
            value=1.0,
            quality=QUALITY,
        )
        signal_fp = compose_snapshot(
            request=request,
            quality_decision=use_quality_decision(),
            selected_events=(),
            selected_signals=(signal,),
        )[1]
        self.assertNotEqual(event_fp, signal_fp)

    def test_scope_in_payload(self) -> None:
        payload = semantic_payload(
            decision_time_ns=T,
            scope=IntelligenceScope(instrument_ids=(INSTRUMENT,)),
            quality=QualitySummary(state=QualityState.GOOD),
            source_event_refs=(),
            source_signal_refs=(),
            component_refs=(),
            composition_policy=default_request().composition_policy,
        )
        self.assertEqual(payload["scope"]["instrument_ids"], [INSTRUMENT])


if __name__ == "__main__":
    unittest.main()
