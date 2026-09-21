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
from .congressional_disclosure_dispatch import (
    dispatch_congressional_disclosure_row,
    normalize_congressional_disclosure_row_for_ingress,
)
from .live_observation_dispatch import (
    canonicalize_live_observation_record,
    dispatch_admitted_live_observation,
    normalize_admitted_live_observation,
    resolve_live_observation_source_key,
)
from .production_wire import (
    build_production_observation_ingress_router,
    resolve_production_ingress_router,
)
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
    "resolve_production_ingress_router",
    "detector_stub_consumer",
    "canonicalize_live_observation_record",
    "dispatch_admitted_live_observation",
    "dispatch_congressional_disclosure_row",
    "dispatch_normalization_result",
    "dispatch_sec_insider_row",
    "enrichment_trigger_consumer",
    "normalize_admitted_live_observation",
    "normalize_congressional_disclosure_row_for_ingress",
    "normalize_sec_insider_row_for_ingress",
    "oe_evidence_consumer",
    "resolve_live_observation_source_key",
    "store_consumer",
]
