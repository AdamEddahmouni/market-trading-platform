"""Core normalization API (BUILD 03)."""

from __future__ import annotations

from typing import Any

from ..contracts.event import EventV1
from .errors import NormalizationError, NormalizationErrorCode
from .models import IngestionMode, NormalizationContext, NormalizationResult
from .registry import get_normalizer, registered_sources


def _detect_source_key(raw: Any, source_key: str | None) -> str | None:
    if source_key:
        return source_key
    if isinstance(raw, dict):
        explicit = raw.get("_normalization_source")
        if explicit:
            return str(explicit)
        if raw.get("capability") in {"QUOTE", "TICKER", "ORDER_BOOK"}:
            return "moomoo.capture"
        if raw.get("accession_number") or raw.get("accessionNumber"):
            return "sec.edgar.filing"
        if raw.get("screen_id") and (raw.get("provider_symbol") or raw.get("instrument_id")):
            return "finviz.candidate"
        if raw.get("normalized_event_id") and raw.get("event_type"):
            return "envelope"
        if raw.get("record_type", "").startswith("ibkr"):
            return "ibkr"
    type_name = type(raw).__name__
    if type_name == "FailsToDeliverObservation":
        return "sec.ftd"
    if type_name == "ShortInterestObservation":
        return "finra.short_interest"
    if type_name == "MacroObservation":
        return "fred.macro"
    return None


def normalize_event(
    raw: Any,
    *,
    context: NormalizationContext,
    source_key: str | None = None,
    **kwargs: Any,
) -> NormalizationResult:
    """Diagnostic normalization — returns result with diagnostics on failure."""
    key = _detect_source_key(raw, source_key)
    if key is None:
        from .errors import NormalizationDiagnostic

        return NormalizationResult(
            event=None,
            diagnostics=(
                NormalizationDiagnostic(
                    code=NormalizationErrorCode.UNSUPPORTED_PROVIDER_RECORD,
                    message="Could not detect normalization source",
                ),
            ),
        )
    normalizer = get_normalizer(key)
    if normalizer is None:
        from .errors import NormalizationDiagnostic

        return NormalizationResult(
            event=None,
            diagnostics=(
                NormalizationDiagnostic(
                    code=NormalizationErrorCode.UNSUPPORTED_PROVIDER_RECORD,
                    message=f"No normalizer registered for source_key={key}",
                ),
            ),
        )
    return normalizer(raw, context=context, **kwargs)


def require_normalized_event(
    raw: Any,
    *,
    context: NormalizationContext,
    source_key: str | None = None,
    **kwargs: Any,
) -> EventV1:
    """Strict normalization — returns EventV1 or raises NormalizationError."""
    result = normalize_event(raw, context=context, source_key=source_key, **kwargs)
    if result.event is not None and not result.diagnostics:
        return result.event
    primary = result.diagnostics[0] if result.diagnostics else None
    raise NormalizationError(
        code=primary.code if primary else NormalizationErrorCode.MALFORMED_PAYLOAD,
        message=primary.message if primary else "Normalization failed",
        diagnostics=result.diagnostics,
        provider_id=result.provenance.provider_id if result.provenance else None,
    )


__all__ = [
    "normalize_event",
    "registered_sources",
    "require_normalized_event",
]
