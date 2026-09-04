"""Snapshot resolution and integrity verification (BUILD 05)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..contracts.common import ContractReference, ContractKind
from ..contracts.event import EventV1
from ..contracts.signal import SignalV1
from ..contracts.snapshot import SnapshotV1
from ..persistence.repository import IntelligenceRepository
from ..temporal.policy import TemporalIntegrityPolicy
from ..temporal.snapshot import validate_snapshot_temporal_integrity
from .canonical import (
    FINGERPRINT_VERSION,
    fingerprint_from_snapshot_parts,
    verify_snapshot_fingerprint,
)
from .errors import SnapshotIntegrityError, SnapshotReferenceError
from .policy import SnapshotCompositionPolicy


@dataclass(frozen=True, slots=True)
class SnapshotResolvedState:
    """Exact records referenced by a persisted snapshot."""

    snapshot: SnapshotV1
    events: tuple[EventV1, ...]
    signals: tuple[SignalV1, ...]
    temporal_report: Any | None = None


class RepositoryTemporalResolver:
    """Resolve snapshot references through IntelligenceRepository."""

    def __init__(self, repository: IntelligenceRepository) -> None:
        self._repository = repository

    def resolve_event(self, ref: ContractReference) -> EventV1 | None:
        if ref.kind != ContractKind.EVENT.value:
            return None
        return self._repository.get_event(ref.id)

    def resolve_signal(self, ref: ContractReference) -> SignalV1 | None:
        if ref.kind != ContractKind.SIGNAL.value:
            return None
        return self._repository.get_signal(ref.id)


def _composition_policy_from_snapshot(snapshot: SnapshotV1) -> SnapshotCompositionPolicy:
    metadata = snapshot.metadata or {}
    stored = metadata.get("composition_policy")
    if isinstance(stored, dict):
        return SnapshotCompositionPolicy(
            policy_id=str(stored.get("policy_id", metadata.get("composition_policy_id", "default"))),
            policy_version=str(
                stored.get("policy_version", metadata.get("composition_policy_version", "1"))
            ),
            max_events=int(stored.get("max_events", 1000)),
            max_signals=int(stored.get("max_signals", 100)),
            lookback_ns=stored.get("lookback_ns"),
            event_types=tuple(stored.get("event_types") or ()),
            include_global_events=bool(stored.get("include_global_events", False)),
            include_signals=bool(stored.get("include_signals", True)),
            allow_degraded=bool(stored.get("allow_degraded", True)),
            require_usable_events=bool(stored.get("require_usable_events", False)),
        )
    policy_id = str(metadata.get("composition_policy_id", "default"))
    policy_version = str(metadata.get("composition_policy_version", "1"))
    return SnapshotCompositionPolicy(policy_id=policy_id, policy_version=policy_version)


def resolve_snapshot(
    snapshot: SnapshotV1,
    repository: IntelligenceRepository,
    *,
    strict: bool = True,
) -> SnapshotResolvedState:
    """Retrieve exactly the records referenced by a snapshot."""
    resolver = RepositoryTemporalResolver(repository)
    events: list[EventV1] = []
    signals: list[SignalV1] = []

    for ref in snapshot.source_event_refs:
        if ref.kind != ContractKind.EVENT.value:
            if strict:
                raise SnapshotReferenceError(
                    f"WRONG_REFERENCE_KIND:event expected, got {ref.kind}",
                    reference_kind=ref.kind,
                    reference_id=ref.id,
                )
            continue
        event = repository.get_event(ref.id)
        if event is None:
            if strict:
                raise SnapshotReferenceError(
                    f"MISSING_EVENT_REFERENCE:{ref.id}",
                    reference_kind=ref.kind,
                    reference_id=ref.id,
                )
            continue
        events.append(event)

    for ref in snapshot.source_signal_refs:
        if ref.kind != ContractKind.SIGNAL.value:
            if strict:
                raise SnapshotReferenceError(
                    f"WRONG_REFERENCE_KIND:signal expected, got {ref.kind}",
                    reference_kind=ref.kind,
                    reference_id=ref.id,
                )
            continue
        signal = repository.get_signal(ref.id)
        if signal is None:
            if strict:
                raise SnapshotReferenceError(
                    f"MISSING_SIGNAL_REFERENCE:{ref.id}",
                    reference_kind=ref.kind,
                    reference_id=ref.id,
                )
            continue
        signals.append(signal)

    temporal_report = validate_snapshot_temporal_integrity(snapshot, resolver=resolver)
    return SnapshotResolvedState(
        snapshot=snapshot,
        events=tuple(events),
        signals=tuple(signals),
        temporal_report=temporal_report,
    )


def verify_snapshot_integrity(
    snapshot: SnapshotV1,
    repository: IntelligenceRepository,
    *,
    composition_policy: SnapshotCompositionPolicy | None = None,
    temporal_policy: TemporalIntegrityPolicy | None = None,
) -> SnapshotResolvedState:
    """Resolve snapshot refs and verify semantic fingerprint plus temporal law."""
    policy = composition_policy or _composition_policy_from_snapshot(snapshot)
    metadata = snapshot.metadata or {}
    expected = metadata.get("content_fingerprint")
    if expected is not None:
        try:
            verify_snapshot_fingerprint(
                decision_time_ns=snapshot.decision_time_ns,
                scope=snapshot.scope,
                quality=snapshot.quality,
                source_event_refs=snapshot.source_event_refs,
                source_signal_refs=snapshot.source_signal_refs,
                component_refs=snapshot.component_refs,
                composition_policy=policy,
                expected_fingerprint=str(expected),
            )
        except ValueError as exc:
            observed = fingerprint_from_snapshot_parts(
                decision_time_ns=snapshot.decision_time_ns,
                scope=snapshot.scope,
                quality=snapshot.quality,
                source_event_refs=snapshot.source_event_refs,
                source_signal_refs=snapshot.source_signal_refs,
                component_refs=snapshot.component_refs,
                composition_policy=policy,
            )
            raise SnapshotIntegrityError(
                str(exc),
                expected_fingerprint=str(expected),
                observed_fingerprint=observed,
            ) from exc

    resolved = resolve_snapshot(snapshot, repository, strict=True)
    report = validate_snapshot_temporal_integrity(
        snapshot,
        resolver=RepositoryTemporalResolver(repository),
        policy=temporal_policy,
    )
    if not report.eligible or report.hard_failures:
        raise SnapshotIntegrityError(
            "SNAPSHOT_TEMPORAL_INTEGRITY_FAILED",
            details={
                "violations": [violation.message for violation in report.violations],
            },
        )
    return SnapshotResolvedState(
        snapshot=snapshot,
        events=resolved.events,
        signals=resolved.signals,
        temporal_report=report,
    )


def stored_fingerprint_version(snapshot: SnapshotV1) -> str | None:
    metadata = snapshot.metadata or {}
    value = metadata.get("fingerprint_version")
    return str(value) if value is not None else None


def snapshot_has_fingerprint_metadata(snapshot: SnapshotV1) -> bool:
    metadata = snapshot.metadata or {}
    return metadata.get("content_fingerprint") is not None


__all__ = [
    "FINGERPRINT_VERSION",
    "RepositoryTemporalResolver",
    "SnapshotResolvedState",
    "resolve_snapshot",
    "snapshot_has_fingerprint_metadata",
    "stored_fingerprint_version",
    "verify_snapshot_integrity",
]
