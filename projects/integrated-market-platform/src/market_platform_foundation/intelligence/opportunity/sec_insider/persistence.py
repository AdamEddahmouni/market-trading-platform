"""Idempotent persistence for SEC insider vertical artifacts."""

from __future__ import annotations

from ...contracts import SnapshotV1
from ...persistence import IntelligenceRepository, RepositoryPutResult
from .pipeline import SecInsiderVerticalResult


def persist_sec_insider_vertical(
    repository: IntelligenceRepository,
    vertical: SecInsiderVerticalResult,
    *,
    snapshot: SnapshotV1,
) -> tuple[RepositoryPutResult, RepositoryPutResult]:
    """Persist canonical snapshot, detection, and evidence (ingress/replay safe)."""
    if not vertical.ok or vertical.detection is None or vertical.evidence is None:
        raise ValueError("SEC_INSIDER_VERTICAL_NOT_OK")
    repository.put_snapshot(snapshot)
    detection_put = repository.put_detection(vertical.detection)
    evidence_put = repository.put_evidence(vertical.evidence)
    return detection_put, evidence_put


__all__ = ["persist_sec_insider_vertical"]
