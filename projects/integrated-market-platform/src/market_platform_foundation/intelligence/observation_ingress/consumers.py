"""Built-in ingress consumer handlers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol, runtime_checkable

from ..contracts.event import EventV1
from ..persistence.repository import IntelligenceRepository, RepositoryPutResult
from .types import (
    IngressConsumerKind,
    IngressConsumerOutcome,
    IngressConsumerStatus,
    IngressDispatchContext,
    validate_consumer_kind,
)


@runtime_checkable
class IngressConsumerHandler(Protocol):
    consumer_id: str
    kind: IngressConsumerKind
    required: bool

    def consume(
        self,
        event: EventV1,
        *,
        context: IngressDispatchContext,
    ) -> IngressConsumerOutcome: ...


@dataclass(frozen=True, slots=True)
class CallableIngressConsumer:
    consumer_id: str
    kind: IngressConsumerKind
    required: bool
    _handler: Callable[[EventV1, IngressDispatchContext], IngressConsumerOutcome]

    def consume(self, event: EventV1, *, context: IngressDispatchContext) -> IngressConsumerOutcome:
        return self._handler(event, context)


def store_consumer(
    repository: IntelligenceRepository,
    *,
    consumer_id: str = "ingress.store",
    required: bool = True,
) -> IngressConsumerHandler:
    kind = validate_consumer_kind(IngressConsumerKind.STORE)

    def _consume(event: EventV1, context: IngressDispatchContext) -> IngressConsumerOutcome:
        result = repository.put_event(event)
        detail = str(result)
        return IngressConsumerOutcome(
            consumer_id=consumer_id,
            kind=kind,
            status=IngressConsumerStatus.OK,
            detail=detail,
        )

    return CallableIngressConsumer(
        consumer_id=consumer_id,
        kind=kind,
        required=required,
        _handler=_consume,
    )


def audit_sink_consumer(
    sink: list[EventV1],
    *,
    consumer_id: str = "ingress.audit_replay",
    required: bool = False,
) -> IngressConsumerHandler:
    kind = validate_consumer_kind(IngressConsumerKind.AUDIT_REPLAY)

    def _consume(event: EventV1, context: IngressDispatchContext) -> IngressConsumerOutcome:
        sink.append(event)
        return IngressConsumerOutcome(
            consumer_id=consumer_id,
            kind=kind,
            status=IngressConsumerStatus.OK,
            detail="APPENDED",
        )

    return CallableIngressConsumer(
        consumer_id=consumer_id,
        kind=kind,
        required=required,
        _handler=_consume,
    )


def oe_evidence_consumer(
    evidence_rows: list[dict[str, str]],
    *,
    consumer_id: str = "ingress.oe_evidence",
    required: bool = False,
) -> IngressConsumerHandler:
    kind = validate_consumer_kind(IngressConsumerKind.OE_EVIDENCE)

    def _consume(event: EventV1, context: IngressDispatchContext) -> IngressConsumerOutcome:
        evidence_rows.append(
            {
                "dispatch_time_ns": str(context.dispatch_time_ns),
                "event_id": event.event_id,
                "event_type": event.event_type,
            }
        )
        return IngressConsumerOutcome(
            consumer_id=consumer_id,
            kind=kind,
            status=IngressConsumerStatus.OK,
            detail="RECORDED",
        )

    return CallableIngressConsumer(
        consumer_id=consumer_id,
        kind=kind,
        required=required,
        _handler=_consume,
    )


def enrichment_trigger_consumer(
    *,
    consumer_id: str = "ingress.enrichment_trigger",
    required: bool = False,
) -> IngressConsumerHandler:
    kind = validate_consumer_kind(IngressConsumerKind.ENRICHMENT_TRIGGER)

    def _consume(event: EventV1, context: IngressDispatchContext) -> IngressConsumerOutcome:
        return IngressConsumerOutcome(
            consumer_id=consumer_id,
            kind=kind,
            status=IngressConsumerStatus.OK,
            detail="SCHEDULED",
        )

    return CallableIngressConsumer(
        consumer_id=consumer_id,
        kind=kind,
        required=required,
        _handler=_consume,
    )


def detector_stub_consumer(
    seen: set[str],
    *,
    consumer_id: str = "ingress.detector_stub",
    required: bool = False,
) -> IngressConsumerHandler:
    kind = validate_consumer_kind(IngressConsumerKind.DETECTOR)

    def _consume(event: EventV1, context: IngressDispatchContext) -> IngressConsumerOutcome:
        seen.add(event.event_id)
        return IngressConsumerOutcome(
            consumer_id=consumer_id,
            kind=kind,
            status=IngressConsumerStatus.OK,
            detail="OBSERVED",
        )

    return CallableIngressConsumer(
        consumer_id=consumer_id,
        kind=kind,
        required=required,
        _handler=_consume,
    )


__all__ = [
    "CallableIngressConsumer",
    "IngressConsumerHandler",
    "audit_sink_consumer",
    "detector_stub_consumer",
    "enrichment_trigger_consumer",
    "oe_evidence_consumer",
    "store_consumer",
]
