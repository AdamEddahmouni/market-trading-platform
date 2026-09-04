"""Public OF-02 attribution adapter contract."""

from __future__ import annotations

from .adapters import (
    attribute_benchmark,
    attribute_drift,
    attribute_evaluation,
    attribute_operational_drill,
    attribute_promotion,
    attribute_provider_smoke,
    attribute_research,
    attribute_training,
    attribute_validation,
)
from .contracts import AttributionRequest, AttributionResult, AttributionStatus
from .lifecycle import attribute
from .operations import CAPABILITY_IDS, adapter_status_payload, execute

__all__ = [
    "CAPABILITY_IDS",
    "AttributionRequest",
    "AttributionResult",
    "AttributionStatus",
    "adapter_status_payload",
    "attribute",
    "attribute_benchmark",
    "attribute_drift",
    "attribute_evaluation",
    "attribute_operational_drill",
    "attribute_promotion",
    "attribute_provider_smoke",
    "attribute_research",
    "attribute_training",
    "attribute_validation",
    "execute",
]
