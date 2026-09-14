"""In-process EventV1 observation ingress router (multi-consumer, idempotent)."""

from __future__ import annotations

from collections import OrderedDict

from ...canonical import canonical_bytes, sha256_bytes
from ..contracts.event import EventV1
from .consumers import IngressConsumerHandler
from .errors import IngressDispatchError
from .identity import derive_ingress_dispatch_id
from .journal import IngressDispatchJournal
from .types import (
    IngressConsumerKind,
    IngressConsumerOutcome,
    IngressConsumerStatus,
    IngressDispatchContext,
    IngressDispatchReceiptV1,
    IngressEnrichmentTriggerV1,
    IngressRouterPolicyV1,
    validate_consumer_kind,
    validate_event_for_dispatch,
)


class ObservationIngressRouter:
    """Fan-out normalized EventV1 to typed consumers without broker side effects."""

    def __init__(
        self,
        consumers: tuple[IngressConsumerHandler, ...] | list[IngressConsumerHandler],
        *,
        policy: IngressRouterPolicyV1 | None = None,
        journal: IngressDispatchJournal | None = None,
    ) -> None:
        self.policy = policy or IngressRouterPolicyV1()
        self.journal = journal or IngressDispatchJournal(max_entries=self.policy.max_journal_entries)
        self._consumers = self._normalize_consumers(consumers)
        self._idempotency: OrderedDict[str, IngressDispatchReceiptV1] = OrderedDict()
        self._enrichment_triggers: list[IngressEnrichmentTriggerV1] = []
        self._metrics: dict[str, int] = {
            "dispatched": 0,
            "duplicates": 0,
            "failed": 0,
        }

    @property
    def consumer_ids(self) -> tuple[str, ...]:
        return tuple(row.consumer_id for row in self._consumers)

    @property
    def enrichment_triggers(self) -> tuple[IngressEnrichmentTriggerV1, ...]:
        return tuple(self._enrichment_triggers)

    def metrics(self) -> dict[str, int]:
        return dict(self._metrics)

    def dispatch(
        self,
        event: EventV1,
        *,
        context: IngressDispatchContext,
        allow_duplicate_replay: bool = False,
    ) -> IngressDispatchReceiptV1:
        validate_event_for_dispatch(event)
        existing = self._idempotency.get(event.event_id)
        if existing is not None and not allow_duplicate_replay:
            self._metrics["duplicates"] += 1
            return IngressDispatchReceiptV1(
                dispatch_id=existing.dispatch_id,
                schema_version="1",
                event_id=event.event_id,
                dispatch_time_ns=existing.dispatch_time_ns,
                duplicate=True,
                outcomes=tuple(
                    IngressConsumerOutcome(
                        consumer_id=row.consumer_id,
                        kind=row.kind,
                        status=IngressConsumerStatus.DUPLICATE,
                        detail="IDEMPOTENT_SKIP",
                    )
                    for row in existing.outcomes
                ),
                metadata={"router_policy_identity": self.policy.identity},
            )

        dispatch_id = derive_ingress_dispatch_id(
            event_id=event.event_id,
            router_policy_identity=self.policy.identity,
            consumer_ids=self.consumer_ids,
        )
        outcomes: list[IngressConsumerOutcome] = []
        for index, consumer in enumerate(self._consumers):
            try:
                outcome = consumer.consume(event, context=context)
            except Exception as exc:  # noqa: BLE001 — fail-closed surface
                outcome = IngressConsumerOutcome(
                    consumer_id=consumer.consumer_id,
                    kind=consumer.kind,
                    status=IngressConsumerStatus.FAILED,
                    detail=str(exc),
                )
            outcomes.append(outcome)
            if outcome.status == IngressConsumerStatus.FAILED and consumer.required and self.policy.fail_closed:
                for remaining in self._consumers[index + 1 :]:
                    outcomes.append(
                        IngressConsumerOutcome(
                            consumer_id=remaining.consumer_id,
                            kind=remaining.kind,
                            status=IngressConsumerStatus.SKIPPED,
                            detail="FAIL_CLOSED_PRIOR_REQUIRED_FAILURE",
                        )
                    )
                self._metrics["failed"] += 1
                raise IngressDispatchError(
                    code="INGRESS_REQUIRED_CONSUMER_FAILED",
                    message=f"consumer {consumer.consumer_id} failed",
                    event_id=event.event_id,
                    partial_outcomes=tuple(row.to_dict() for row in outcomes),
                )
            if consumer.kind == IngressConsumerKind.ENRICHMENT_TRIGGER and outcome.status == IngressConsumerStatus.OK:
                self._record_enrichment_trigger(
                    event,
                    consumer_id=consumer.consumer_id,
                    scheduled_at_ns=context.dispatch_time_ns,
                )

        receipt = IngressDispatchReceiptV1(
            dispatch_id=dispatch_id,
            schema_version="1",
            event_id=event.event_id,
            dispatch_time_ns=context.dispatch_time_ns,
            duplicate=False,
            outcomes=tuple(outcomes),
            metadata={
                "router_policy_identity": self.policy.identity,
                "source_label": context.source_label,
            },
        )
        self._remember_idempotent(receipt)
        self.journal.append(receipt)
        self._metrics["dispatched"] += 1
        return receipt

    def replay_from_journal(self, events_by_id: dict[str, EventV1], *, dispatch_time_ns: int) -> tuple[IngressDispatchReceiptV1, ...]:
        """Re-dispatch journal event_ids in order (for deterministic replay tests)."""
        receipts: list[IngressDispatchReceiptV1] = []
        for event_id in self.journal.replay_event_ids():
            event = events_by_id.get(event_id)
            if event is None:
                raise ValueError(f"INGRESS_REPLAY_EVENT_MISSING:{event_id}")
            receipts.append(
                self.dispatch(
                    event,
                    context=IngressDispatchContext(dispatch_time_ns=dispatch_time_ns, source_label="journal_replay"),
                    allow_duplicate_replay=True,
                )
            )
        return tuple(receipts)

    def _record_enrichment_trigger(self, event: EventV1, *, consumer_id: str, scheduled_at_ns: int) -> None:
        if len(self._enrichment_triggers) >= self.policy.max_enrichment_triggers:
            raise ValueError("INGRESS_ENRICHMENT_TRIGGER_BOUND_EXCEEDED")
        payload = {
            "consumer_id": consumer_id,
            "event_id": event.event_id,
            "scheduled_at_ns": scheduled_at_ns,
        }
        trigger_id = f"ENR-{sha256_bytes(canonical_bytes(payload))}"
        self._enrichment_triggers.append(
            IngressEnrichmentTriggerV1(
                trigger_id=trigger_id,
                event_id=event.event_id,
                scheduled_at_ns=scheduled_at_ns,
                consumer_id=consumer_id,
            )
        )

    def _remember_idempotent(self, receipt: IngressDispatchReceiptV1) -> None:
        self._idempotency[receipt.event_id] = receipt
        while len(self._idempotency) > self.policy.max_idempotency_keys:
            self._idempotency.popitem(last=False)

    @staticmethod
    def _normalize_consumers(
        consumers: tuple[IngressConsumerHandler, ...] | list[IngressConsumerHandler],
    ) -> tuple[IngressConsumerHandler, ...]:
        unique: dict[str, IngressConsumerHandler] = {}
        for row in consumers:
            validate_consumer_kind(row.kind)
            if row.consumer_id in unique:
                raise ValueError(f"INGRESS_DUPLICATE_CONSUMER_ID:{row.consumer_id}")
            unique[row.consumer_id] = row
        return tuple(unique[key] for key in sorted(unique))


__all__ = ["ObservationIngressRouter"]
