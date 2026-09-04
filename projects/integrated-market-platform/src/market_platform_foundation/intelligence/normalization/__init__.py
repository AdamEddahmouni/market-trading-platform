"""Provider normalization and provenance (BUILD 03)."""

from __future__ import annotations

from .core import normalize_event, require_normalized_event
from .errors import NormalizationDiagnostic, NormalizationError, NormalizationErrorCode
from .event_builder import provenance_from_event
from .models import (
    AvailabilityBasis,
    AvailabilityConfidence,
    AvailabilityDerivation,
    IngestionMode,
    NormalizationContext,
    NormalizationResult,
    ProviderProvenance,
    SourcePrecision,
)
from .registry import get_normalizer, register_normalizer, registered_sources

__all__ = [
    "AvailabilityBasis",
    "AvailabilityConfidence",
    "AvailabilityDerivation",
    "IngestionMode",
    "NormalizationContext",
    "NormalizationDiagnostic",
    "NormalizationError",
    "NormalizationErrorCode",
    "NormalizationResult",
    "ProviderProvenance",
    "SourcePrecision",
    "get_normalizer",
    "normalize_event",
    "provenance_from_event",
    "register_normalizer",
    "registered_sources",
    "require_normalized_event",
]
