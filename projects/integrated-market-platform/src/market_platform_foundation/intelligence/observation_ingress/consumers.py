"""Built-in ingress consumer handlers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol, runtime_checkable

from ..contracts.event import EventV1
from ..opportunity.congressional_disclosure import (
    accepts_congressional_disclosure_event,
    run_congressional_disclosure_vertical,
)
from ..opportunity.sec_insider import accepts_sec_insider_event, run_sec_insider_vertical
from ..persistence.errors import RepositoryConflictError
from ..persistence.repository import IntelligenceRepository, RepositoryPutResult
from ..opportunity.sec_insider.canonical_snapshot import build_sec_insider_canonical_detection_snapshot
from ..opportunity.sec_insider.persistence import persist_sec_insider_vertical
from .congressional_disclosure_snapshot import build_congressional_disclosure_ingress_snapshot
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
        try:
            result = repository.put_event(event)
        except RepositoryConflictError:
            return IngressConsumerOutcome(
                consumer_id=consumer_id,
                kind=kind,
                status=IngressConsumerStatus.FAILED,
                detail="EVENT_PERSIST_CONFLICT",
            )
        if result == RepositoryPutResult.ALREADY_PRESENT:
            return IngressConsumerOutcome(
                consumer_id=consumer_id,
                kind=kind,
                status=IngressConsumerStatus.DUPLICATE,
                detail=RepositoryPutResult.ALREADY_PRESENT.value,
            )
        return IngressConsumerOutcome(
            consumer_id=consumer_id,
            kind=kind,
            status=IngressConsumerStatus.OK,
            detail=RepositoryPutResult.INSERTED.value,
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
    sec_vertical_enrichment: dict[str, dict[str, str]] | None = None,
) -> IngressConsumerHandler:
    kind = validate_consumer_kind(IngressConsumerKind.OE_EVIDENCE)

    def _consume(event: EventV1, context: IngressDispatchContext) -> IngressConsumerOutcome:
        row: dict[str, str] = {
            "dispatch_time_ns": str(context.dispatch_time_ns),
            "event_id": event.event_id,
            "event_type": event.event_type,
        }
        if sec_vertical_enrichment is not None:
            row.update(sec_vertical_enrichment.get(event.event_id, {}))
        evidence_rows.append(row)
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
    repository: IntelligenceRepository | None = None,
    oe_evidence_enrichment: dict[str, dict[str, str]] | None = None,
) -> IngressConsumerHandler:
    """DETECTOR lane: observe all events; SEC / congressional rows run canonical verticals."""

    kind = validate_consumer_kind(IngressConsumerKind.DETECTOR)

    def _consume(event: EventV1, context: IngressDispatchContext) -> IngressConsumerOutcome:
        seen.add(event.event_id)
        if repository is not None and accepts_congressional_disclosure_event(event):
            decision_time_ns = max(context.dispatch_time_ns, event.available_time_ns + 1)
            snapshot = build_congressional_disclosure_ingress_snapshot(
                event,
                decision_time_ns=decision_time_ns,
            )
            repository.put_snapshot(snapshot)
            vertical = run_congressional_disclosure_vertical(event=event, snapshot=snapshot)
            if not vertical.ok:
                return IngressConsumerOutcome(
                    consumer_id=consumer_id,
                    kind=kind,
                    status=IngressConsumerStatus.OK,
                    detail=f"CONGRESSIONAL_VERTICAL_SKIPPED:{','.join(vertical.reason_codes)}",
                )
            assert vertical.detection is not None
            assert vertical.evidence is not None
            repository.put_detection(vertical.detection)
            repository.put_evidence(vertical.evidence)
            if oe_evidence_enrichment is not None and vertical.candidate is not None:
                oe_evidence_enrichment[event.event_id] = {
                    "dispatch_time_ns": str(context.dispatch_time_ns),
                    "event_id": event.event_id,
                    "event_type": event.event_type,
                    "detection_id": vertical.detection.detection_id,
                    "evidence_id": vertical.evidence.evidence_id,
                    "opportunity_candidate_id": str(vertical.candidate.get("opportunity_id", "")),
                    "strategy_family": str(vertical.candidate.get("strategy_family", "")),
                }
            return IngressConsumerOutcome(
                consumer_id=consumer_id,
                kind=kind,
                status=IngressConsumerStatus.OK,
                detail="CONGRESSIONAL_PTR_VERTICAL_OK",
            )
        if repository is None or not accepts_sec_insider_event(event):
            return IngressConsumerOutcome(
                consumer_id=consumer_id,
                kind=kind,
                status=IngressConsumerStatus.OK,
                detail="OBSERVED",
            )
        snapshot = build_sec_insider_canonical_detection_snapshot(event)
        vertical = run_sec_insider_vertical(event=event, snapshot=snapshot)
        if not vertical.ok:
            return IngressConsumerOutcome(
                consumer_id=consumer_id,
                kind=kind,
                status=IngressConsumerStatus.OK,
                detail=f"SEC_VERTICAL_SKIPPED:{','.join(vertical.reason_codes)}",
            )
        assert vertical.detection is not None
        assert vertical.evidence is not None
        persist_sec_insider_vertical(repository, vertical, snapshot=snapshot)
        if oe_evidence_enrichment is not None and vertical.candidate is not None:
            oe_evidence_enrichment[event.event_id] = {
                "dispatch_time_ns": str(context.dispatch_time_ns),
                "event_id": event.event_id,
                "event_type": event.event_type,
                "detection_id": vertical.detection.detection_id,
                "evidence_id": vertical.evidence.evidence_id,
                "opportunity_candidate_id": str(vertical.candidate.get("opportunity_id", "")),
                "strategy_family": str(vertical.candidate.get("strategy_family", "")),
            }
        return IngressConsumerOutcome(
            consumer_id=consumer_id,
            kind=kind,
            status=IngressConsumerStatus.OK,
            detail="SEC_INSIDER_VERTICAL_OK",
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
