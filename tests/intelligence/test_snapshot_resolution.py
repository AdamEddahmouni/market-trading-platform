"""Snapshot resolution and integrity tests (BUILD 05)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from market_platform_foundation.intelligence.contracts import ContractReference  # noqa: E402
from market_platform_foundation.intelligence.persistence import InMemoryIntelligenceRepository  # noqa: E402
from market_platform_foundation.intelligence.snapshots import (  # noqa: E402
    SnapshotIntegrityError,
    SnapshotReferenceError,
    build_snapshot,
    resolve_snapshot,
    verify_snapshot_integrity,
    verify_snapshot_reproducibility,
)
from tests.intelligence.test_snapshot_fixtures import (  # noqa: E402
    T,
    default_request,
    empty_repo_with_events,
    sample_event,
    sample_signal,
    use_quality_decision,
)


class IncompleteRepository(InMemoryIntelligenceRepository):
    """Repository missing specific records for reconstruction tests."""


class SnapshotResolutionTests(unittest.TestCase):
    def test_reconstruction_exactness(self) -> None:
        repo = empty_repo_with_events(sample_event("evt-1", available_time_ns=T))
        repo.put_signal(sample_signal("sig-1", as_of_time_ns=T))
        built = build_snapshot(repo, default_request(), quality_decision=use_quality_decision())
        resolved = resolve_snapshot(built.snapshot, repo)
        self.assertEqual(
            [event.event_id for event in resolved.events],
            [ref.id for ref in built.snapshot.source_event_refs],
        )
        self.assertEqual(
            [signal.signal_id for signal in resolved.signals],
            [ref.id for ref in built.snapshot.source_signal_refs],
        )

    def test_missing_reference_strict(self) -> None:
        repo = empty_repo_with_events(sample_event("evt-1", available_time_ns=T))
        built = build_snapshot(repo, default_request(), quality_decision=use_quality_decision())
        incomplete = InMemoryIntelligenceRepository()
        with self.assertRaises(SnapshotReferenceError):
            resolve_snapshot(built.snapshot, incomplete)

    def test_wrong_reference_kind(self) -> None:
        repo = InMemoryIntelligenceRepository()
        broken = build_snapshot(
            empty_repo_with_events(sample_event("evt-1", available_time_ns=T)),
            default_request(),
            quality_decision=use_quality_decision(),
        ).snapshot
        object.__setattr__(
            broken,
            "source_event_refs",
            (ContractReference(kind="signal", id="evt-1"),),
        )
        with self.assertRaises(SnapshotReferenceError):
            resolve_snapshot(broken, repo)

    def test_historical_quality_stable(self) -> None:
        repo = empty_repo_with_events(sample_event())
        from tests.intelligence.test_snapshot_fixtures import degrade_quality_decision  # noqa: E402

        built = build_snapshot(repo, default_request(), quality_decision=degrade_quality_decision())
        resolved = resolve_snapshot(built.snapshot, repo)
        self.assertEqual(resolved.snapshot.quality.state, built.snapshot.quality.state)

    def test_verify_integrity_passes(self) -> None:
        repo = empty_repo_with_events(sample_event("evt-1", available_time_ns=T))
        built = build_snapshot(repo, default_request(), quality_decision=use_quality_decision())
        verify_snapshot_integrity(built.snapshot, repo)

    def test_verify_integrity_fingerprint_mismatch(self) -> None:
        repo = empty_repo_with_events(sample_event("evt-1", available_time_ns=T))
        built = build_snapshot(repo, default_request(), quality_decision=use_quality_decision())
        metadata = dict(built.snapshot.metadata)
        metadata["content_fingerprint"] = "0" * 64
        object.__setattr__(built.snapshot, "metadata", metadata)
        with self.assertRaises(SnapshotIntegrityError):
            verify_snapshot_integrity(built.snapshot, repo)

    def test_reproducibility(self) -> None:
        repo = empty_repo_with_events(sample_event("evt-1", available_time_ns=T))
        request = default_request()
        built = build_snapshot(repo, request, quality_decision=use_quality_decision(), persist=False)
        fingerprint = verify_snapshot_reproducibility(
            repo,
            request=request,
            existing_snapshot=built.snapshot,
            quality_decision=use_quality_decision(),
        )
        self.assertEqual(fingerprint, built.content_fingerprint)


if __name__ == "__main__":
    unittest.main()
