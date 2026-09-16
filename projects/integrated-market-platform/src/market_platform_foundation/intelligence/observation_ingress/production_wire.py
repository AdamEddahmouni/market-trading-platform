"""Production observation ingress router wiring (store + audit + evidence lanes)."""

from __future__ import annotations

from ..contracts.event import EventV1
from ..persistence.repository import IntelligenceRepository
from .consumers import (
    audit_sink_consumer,
    detector_stub_consumer,
    enrichment_trigger_consumer,
    observational_news_detector_consumer,
    oe_evidence_consumer,
    store_consumer,
)
from .journal import IngressDispatchJournal
from .router import ObservationIngressRouter
from .types import IngressRouterPolicyV1

try:
    from ...hot_path_telemetry.collector import HotPathIngressDispatchObserver
except ImportError:  # pragma: no cover
    HotPathIngressDispatchObserver = None  # type: ignore[misc, assignment]


def resolve_production_ingress_router(
    repository: IntelligenceRepository,
    *,
    ingress_router: ObservationIngressRouter | None = None,
    use_production_ingress: bool = True,
) -> ObservationIngressRouter | None:
    """Return an ingress router for materialize/dispatch entrypoints.

    - Explicit ``ingress_router`` wins (caller-owned lifecycle).
    - When ``use_production_ingress`` and no router is passed, build the canonical
      production consumer set for ``repository``.
    - When ``use_production_ingress`` is false and no router is passed, return
      ``None`` (direct ``IntelligenceRepository.put_event`` store lane).
    """
    if ingress_router is not None:
        return ingress_router
    if not use_production_ingress:
        return None
    return build_production_observation_ingress_router(repository)


def build_production_observation_ingress_router(
    repository: IntelligenceRepository,
    *,
    audit_replay_sink: list[EventV1] | None = None,
    oe_evidence_sink: list[dict[str, str]] | None = None,
    detector_seen: set[str] | None = None,
    policy: IngressRouterPolicyV1 | None = None,
    journal: IngressDispatchJournal | None = None,
    dispatch_observer: HotPathIngressDispatchObserver | None = None,
) -> ObservationIngressRouter:
    """Canonical production consumers — no broker or order-submit lanes."""
    audit = audit_replay_sink if audit_replay_sink is not None else []
    evidence = oe_evidence_sink if oe_evidence_sink is not None else []
    seen = detector_seen if detector_seen is not None else set()
    sec_vertical_enrichment: dict[str, dict[str, str]] = {}
    return ObservationIngressRouter(
        [
            store_consumer(repository),
            audit_sink_consumer(audit),
            observational_news_detector_consumer(repository=repository),
            detector_stub_consumer(
                seen,
                repository=repository,
                oe_evidence_enrichment=sec_vertical_enrichment,
            ),
            oe_evidence_consumer(evidence, sec_vertical_enrichment=sec_vertical_enrichment),
            enrichment_trigger_consumer(),
        ],
        policy=policy,
        journal=journal,
        dispatch_observer=dispatch_observer,
    )


__all__ = [
    "build_production_observation_ingress_router",
    "resolve_production_ingress_router",
]
