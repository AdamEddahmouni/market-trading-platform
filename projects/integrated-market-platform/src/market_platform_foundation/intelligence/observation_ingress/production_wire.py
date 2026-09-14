"""Production observation ingress router wiring (store + audit + evidence lanes)."""

from __future__ import annotations

from ..contracts.event import EventV1
from ..persistence.repository import IntelligenceRepository
from .consumers import (
    audit_sink_consumer,
    detector_stub_consumer,
    enrichment_trigger_consumer,
    oe_evidence_consumer,
    store_consumer,
)
from .journal import IngressDispatchJournal
from .router import ObservationIngressRouter
from .types import IngressRouterPolicyV1


def build_production_observation_ingress_router(
    repository: IntelligenceRepository,
    *,
    audit_replay_sink: list[EventV1] | None = None,
    oe_evidence_sink: list[dict[str, str]] | None = None,
    detector_seen: set[str] | None = None,
    policy: IngressRouterPolicyV1 | None = None,
    journal: IngressDispatchJournal | None = None,
) -> ObservationIngressRouter:
    """Canonical production consumers — no broker or order-submit lanes."""
    audit = audit_replay_sink if audit_replay_sink is not None else []
    evidence = oe_evidence_sink if oe_evidence_sink is not None else []
    seen = detector_seen if detector_seen is not None else set()
    return ObservationIngressRouter(
        [
            store_consumer(repository),
            audit_sink_consumer(audit),
            oe_evidence_consumer(evidence),
            detector_stub_consumer(seen),
            enrichment_trigger_consumer(),
        ],
        policy=policy,
        journal=journal,
    )


__all__ = ["build_production_observation_ingress_router"]
