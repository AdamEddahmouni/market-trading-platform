"""Admitted live observation → provider normalizer → EventV1 production ingress.

Bridge only. Does not enable Live, does not submit orders, and does not invent
a parallel event bus. Callers attach an ``ObservationIngressRouter`` explicitly.
"""

from __future__ import annotations

from typing import Any, Mapping

from ..normalization.core import normalize_event
from ..normalization.errors import NormalizationDiagnostic, NormalizationErrorCode
from ..normalization.models import IngestionMode, NormalizationContext, NormalizationResult
from .normalization_bridge import dispatch_normalization_result
from .router import ObservationIngressRouter
from .types import IngressDispatchContext, IngressDispatchReceiptV1

_MOOMOO_CAPTURE_CAPABILITIES = frozenset({"QUOTE", "TICKER", "ORDER_BOOK", "MARKET_DATA_EVENT"})

# OpenD / live push vocabulary → BUILD 03 moomoo.capture normalizer vocabulary.
_LIVE_CAPABILITY_ALIASES: dict[str, str] = {
    "US_EQUITY_L1": "QUOTE",
    "US_EQUITY_SNAPSHOT": "QUOTE",
    "US_EQUITY_TICKS": "TICKER",
    "US_EQUITY_DEPTH": "ORDER_BOOK",
    "QUOTE": "QUOTE",
    "TICKER": "TICKER",
    "ORDER_BOOK": "ORDER_BOOK",
    "MARKET_DATA_EVENT": "MARKET_DATA_EVENT",
}

_SNAPSHOT_BBO_CAPABILITY = "SNAPSHOT_BBO"

# Capture fields only — strip runtime/RT01 instrumentation that is not deepcopy-safe.
_CAPTURE_FIELD_KEYS = frozenset(
    {
        "available_time_ns",
        "capability",
        "clocks",
        "first_push_class",
        "ingest_run_id",
        "instrument_id",
        "is_cached",
        "is_first_push",
        "lifecycle",
        "provider",
        "provider_generation",
        "provider_symbol",
        "quality_flags",
        "raw_payload",
        "schema_version",
        "sequence",
        "source_capability",
    }
)


def capture_record_for_normalization(record: Mapping[str, Any]) -> dict[str, Any]:
    """Project an admitted live record onto deepcopy-safe capture fields."""
    return {key: record[key] for key in _CAPTURE_FIELD_KEYS if key in record}


def canonicalize_live_observation_record(record: Mapping[str, Any]) -> dict[str, Any]:
    """Map live/OpenD capability names onto the moomoo.capture normalizer vocabulary."""
    body = capture_record_for_normalization(record)
    capability = str(body.get("capability") or "").upper()
    if capability == _SNAPSHOT_BBO_CAPABILITY:
        quality = body.get("quality_flags") or ()
        if "BBO_VALID" in {str(flag) for flag in quality}:
            body["source_capability"] = body.get("capability") or _SNAPSHOT_BBO_CAPABILITY
            body["capability"] = "QUOTE"
        return body
    alias = _LIVE_CAPABILITY_ALIASES.get(capability)
    if alias is not None:
        if capability != alias:
            body["source_capability"] = body.get("capability")
        body["capability"] = alias
    return body


def resolve_live_observation_source_key(
    record: Mapping[str, Any],
    *,
    envelope: Mapping[str, Any] | None = None,
) -> str | None:
    """Select existing BUILD 03 normalizer key for an admitted live observation."""
    prepared = canonicalize_live_observation_record(record)
    capability = str(prepared.get("capability") or "").upper()
    if capability in _MOOMOO_CAPTURE_CAPABILITIES:
        return "moomoo.capture"
    if envelope is not None and envelope.get("normalized_event_id") and envelope.get("event_type"):
        return "envelope"
    if prepared.get("normalized_event_id") and prepared.get("event_type"):
        return "envelope"
    return None


def _received_time_ns(
    record: Mapping[str, Any],
    *,
    envelope: Mapping[str, Any] | None,
    context: NormalizationContext | None,
) -> int:
    if context is not None:
        return int(context.received_time_ns)
    clocks = record.get("clocks") if isinstance(record.get("clocks"), dict) else {}
    if clocks.get("received_time_ns") is not None:
        return int(clocks["received_time_ns"])
    if envelope is not None and envelope.get("live_received_time") is not None:
        return int(envelope["live_received_time"])
    if envelope is not None and envelope.get("available_time") is not None:
        return int(envelope["available_time"])
    raise ValueError("LIVE_OBSERVATION_RECEIVED_TIME_REQUIRED")


def normalize_admitted_live_observation(
    record: Mapping[str, Any],
    *,
    envelope: Mapping[str, Any] | None = None,
    context: NormalizationContext | None = None,
    raw_payload_ref: str | None = None,
) -> NormalizationResult:
    """Normalize an admitted live snapshot/bar/quote via existing provider normalizers.

    Always uses ``IngestionMode.LIVE_OBSERVED`` for availability/PIT semantics unless
    the caller already supplied a ``NormalizationContext`` (which must itself use
    ``LIVE_OBSERVED`` — other modes are refused so replay/historical paths stay distinct).
    """
    if context is not None and context.ingestion_mode != IngestionMode.LIVE_OBSERVED:
        return NormalizationResult(
            event=None,
            diagnostics=(
                NormalizationDiagnostic(
                    code=NormalizationErrorCode.UNSUPPORTED_PROVIDER_RECORD,
                    message=(
                        "live observation bridge requires IngestionMode.LIVE_OBSERVED; "
                        f"got {context.ingestion_mode.value}"
                    ),
                ),
            ),
        )

    try:
        received = _received_time_ns(record, envelope=envelope, context=context)
    except ValueError:
        return NormalizationResult(
            event=None,
            diagnostics=(
                NormalizationDiagnostic(
                    code=NormalizationErrorCode.MISSING_REQUIRED_FIELD,
                    message="received_time_ns is required for LIVE_OBSERVED normalization",
                    field="received_time_ns",
                ),
            ),
        )

    effective_context = context or NormalizationContext(
        received_time_ns=received,
        ingestion_mode=IngestionMode.LIVE_OBSERVED,
        raw_payload_ref=raw_payload_ref,
    )
    if effective_context.raw_payload_ref is None and raw_payload_ref is not None:
        effective_context = NormalizationContext(
            received_time_ns=effective_context.received_time_ns,
            ingestion_mode=IngestionMode.LIVE_OBSERVED,
            adapter_version=effective_context.adapter_version,
            raw_payload_ref=raw_payload_ref,
            provider_reported_available_time_ns=effective_context.provider_reported_available_time_ns,
            historical_available_time_ns=effective_context.historical_available_time_ns,
            availability_basis=effective_context.availability_basis,
            availability_confidence=effective_context.availability_confidence,
            source_precision=effective_context.source_precision,
            provider_delay_ns=effective_context.provider_delay_ns,
            ingest_run_id=effective_context.ingest_run_id,
        )

    source_key = resolve_live_observation_source_key(record, envelope=envelope)
    if source_key is None:
        return NormalizationResult(
            event=None,
            diagnostics=(
                NormalizationDiagnostic(
                    code=NormalizationErrorCode.UNSUPPORTED_PROVIDER_RECORD,
                    message="No BUILD 03 normalizer for admitted live observation",
                    details={
                        "capability": str(record.get("capability") or ""),
                        "has_envelope": envelope is not None,
                    },
                ),
            ),
        )

    if source_key == "moomoo.capture":
        payload: Mapping[str, Any] = canonicalize_live_observation_record(record)
    else:
        payload = envelope if envelope is not None else record

    return normalize_event(dict(payload), context=effective_context, source_key=source_key)


def dispatch_admitted_live_observation(
    router: ObservationIngressRouter,
    record: Mapping[str, Any],
    *,
    envelope: Mapping[str, Any] | None = None,
    context: NormalizationContext | None = None,
    dispatch_context: IngressDispatchContext | None = None,
    raw_payload_ref: str | None = None,
) -> IngressDispatchReceiptV1 | None:
    """Canonical live ingress: admitted observation → normalize → production router."""
    result = normalize_admitted_live_observation(
        record,
        envelope=envelope,
        context=context,
        raw_payload_ref=raw_payload_ref,
    )
    if result.event is None:
        return None
    dispatch = dispatch_context or IngressDispatchContext(
        dispatch_time_ns=result.event.available_time_ns,
        ingestion_mode=IngestionMode.LIVE_OBSERVED,
        source_label="live.observational",
    )
    return dispatch_normalization_result(router, result, context=dispatch)


__all__ = [
    "canonicalize_live_observation_record",
    "capture_record_for_normalization",
    "dispatch_admitted_live_observation",
    "normalize_admitted_live_observation",
    "resolve_live_observation_source_key",
]
