"""Minimal SnapshotV1 for SEC insider ingress / detector hot path."""

from __future__ import annotations

from ..contracts.event import EventV1
from ..contracts.snapshot import SnapshotV1
from ..opportunity.sec_insider.canonical_snapshot import (
    build_sec_insider_canonical_detection_snapshot,
)


def build_sec_insider_ingress_snapshot(
    event: EventV1,
    *,
    decision_time_ns: int | None = None,
    snapshot_id: str | None = None,
) -> SnapshotV1:
    """Canonical detection snapshot (ingress and BUILD 09 share one identity anchor)."""
    canonical = build_sec_insider_canonical_detection_snapshot(event)
    if snapshot_id is not None or (
        decision_time_ns is not None
        and decision_time_ns != canonical.decision_time_ns
    ):
        raise ValueError("SEC_INSIDER_INGRESS_SNAPSHOT_MUST_USE_CANONICAL_ANCHOR")
    return canonical


__all__ = ["build_sec_insider_ingress_snapshot"]
