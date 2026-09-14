"""Observation ingress router — EventV1 multi-consumer production dispatch."""

from .consumers import (
    CallableIngressConsumer,
    IngressConsumerHandler,
    audit_sink_consumer,
    detector_stub_consumer,
    enrichment_trigger_consumer,
    oe_evidence_consumer,
    store_consumer,
)
from .errors import IngressDispatchError
from .journal import IngressDispatchJournal
from .normalization_bridge import dispatch_normalization_result
from .production_wire import build_production_observation_ingress_router
from .router import ObservationIngressRouter
from .sec_insider_dispatch import dispatch_sec_insider_row, normalize_sec_insider_row_for_ingress
from .types import (
    IngressConsumerKind,
    IngressConsumerOutcome,
    IngressConsumerStatus,
    IngressDispatchContext,
    IngressDispatchReceiptV1,
    IngressEnrichmentTriggerV1,
    IngressRouterPolicyV1,
)

__all__ = [
    "CallableIngressConsumer",
    "IngressConsumerHandler",
    "IngressConsumerKind",
    "IngressConsumerOutcome",
    "IngressConsumerStatus",
    "IngressDispatchContext",
    "IngressDispatchError",
    "IngressDispatchJournal",
    "IngressDispatchReceiptV1",
    "IngressEnrichmentTriggerV1",
    "IngressRouterPolicyV1",
    "ObservationIngressRouter",
    "audit_sink_consumer",
    "build_production_observation_ingress_router",
    "detector_stub_consumer",
    "dispatch_normalization_result",
    "dispatch_sec_insider_row",
    "enrichment_trigger_consumer",
    "normalize_sec_insider_row_for_ingress",
    "oe_evidence_consumer",
    "store_consumer",
]
