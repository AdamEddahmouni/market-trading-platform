"""Observation ingress router contracts (EventV1 fan-out, not a new envelope)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from ..contracts.common import QualityState
from ..contracts.event import EventV1
from ..normalization.models import IngestionMode


class IngressConsumerKind(StrEnum):
    """Logical consumer lanes for normalized EventV1 production dispatch."""

    STORE = "STORE"
    DETECTOR = "DETECTOR"
    OE_EVIDENCE = "OE_EVIDENCE"
    AUDIT_REPLAY = "AUDIT_REPLAY"
    ENRICHMENT_TRIGGER = "ENRICHMENT_TRIGGER"


_FORBIDDEN_CONSUMER_KINDS = frozenset({"BROKER_ACTION", "EXECUTION", "ORDER_SUBMIT"})


class IngressConsumerStatus(StrEnum):
    OK = "OK"
    SKIPPED = "SKIPPED"
    FAILED = "FAILED"
    DUPLICATE = "DUPLICATE"


@dataclass(frozen=True, slots=True)
class IngressRouterPolicyV1:
    """Bounded, deterministic in-process ingress router policy."""

    policy_id: str = "observation-ingress/default"
    policy_version: str = "1"
    max_idempotency_keys: int = 10_000
    max_journal_entries: int = 5_000
    max_enrichment_triggers: int = 1_000
    fail_closed: bool = True

    @property
    def identity(self) -> str:
        return f"{self.policy_id}@{self.policy_version}"


@dataclass(frozen=True, slots=True)
class IngressDispatchContext:
    dispatch_time_ns: int
    ingestion_mode: IngestionMode | None = None
    source_label: str | None = None


@dataclass(frozen=True, slots=True)
class IngressConsumerOutcome:
    consumer_id: str
    kind: IngressConsumerKind
    status: IngressConsumerStatus
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "consumer_id": self.consumer_id,
            "detail": self.detail,
            "kind": self.kind.value,
            "status": self.status.value,
        }


@dataclass(frozen=True, slots=True)
class IngressDispatchReceiptV1:
    """Deterministic receipt for a single EventV1 ingress dispatch."""

    dispatch_id: str
    schema_version: str
    event_id: str
    dispatch_time_ns: int
    duplicate: bool
    outcomes: tuple[IngressConsumerOutcome, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "dispatch_id": self.dispatch_id,
            "dispatch_time_ns": self.dispatch_time_ns,
            "duplicate": self.duplicate,
            "event_id": self.event_id,
            "metadata": dict(self.metadata),
            "outcomes": [row.to_dict() for row in self.outcomes],
            "schema_version": self.schema_version,
        }


@dataclass(frozen=True, slots=True)
class IngressEnrichmentTriggerV1:
    """Bounded async enrichment schedule token (hot path does not await enrichment)."""

    trigger_id: str
    event_id: str
    scheduled_at_ns: int
    consumer_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "consumer_id": self.consumer_id,
            "event_id": self.event_id,
            "scheduled_at_ns": self.scheduled_at_ns,
            "trigger_id": self.trigger_id,
        }


def validate_consumer_kind(kind: IngressConsumerKind | str) -> IngressConsumerKind:
    raw = kind.value if isinstance(kind, IngressConsumerKind) else str(kind)
    upper = raw.upper()
    if upper in _FORBIDDEN_CONSUMER_KINDS:
        raise ValueError(f"INGRESS_FORBIDDEN_CONSUMER_KIND:{upper}")
    try:
        return IngressConsumerKind(upper)
    except ValueError:
        raise ValueError(f"INGRESS_UNKNOWN_CONSUMER_KIND:{raw}") from None


def validate_event_for_dispatch(event: EventV1) -> None:
    if event.quality.state == QualityState.INVALID:
        raise ValueError("INGRESS_EVENT_QUALITY_INVALID")


__all__ = [
    "IngressConsumerKind",
    "IngressConsumerOutcome",
    "IngressConsumerStatus",
    "IngressDispatchContext",
    "IngressDispatchReceiptV1",
    "IngressEnrichmentTriggerV1",
    "IngressRouterPolicyV1",
    "validate_consumer_kind",
    "validate_event_for_dispatch",
]
