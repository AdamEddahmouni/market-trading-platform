from collections.abc import Iterable, Mapping
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import ValidationError

from squeeze_core.adapters.base import AdapterContext, NormalizationResult, RejectedRecord
from squeeze_core.adapters.diagnostics import (
    DiagnosticCode,
    DiagnosticSeverity,
    NormalizationDiagnostic,
)
from squeeze_core.contracts import (
    AssetClass,
    Completeness,
    DataFreshness,
    EventType,
    Observation,
    ObservationKind,
    PayloadType,
    Provenance,
    Quality,
    QualityState,
    QuotePayload,
    TradePayload,
)
from squeeze_core.replay.engine import observation_order_key
from squeeze_core.serialization import canonical_hash

from .conditions import normalize_conditions
from .models import (
    TradeQuoteLifecycleStatus,
    TradeQuoteRecord,
    TradeQuoteRecordType,
    UnknownAvailabilityPolicy,
)
from .parsing import parse_trade_quote_timestamp
from .semantics import quote_market_state
from .validation import TradeQuoteValidationError


_TRADE_STATUS_CODE = {
    TradeQuoteLifecycleStatus.ORIGINAL: DiagnosticCode.TRADE_ORIGINAL_RECORD,
    TradeQuoteLifecycleStatus.CORRECTED: DiagnosticCode.TRADE_CORRECTED_RECORD,
    TradeQuoteLifecycleStatus.CANCELLED: DiagnosticCode.TRADE_CANCELLED_RECORD,
    TradeQuoteLifecycleStatus.DELETED: DiagnosticCode.TRADE_DELETED_RECORD,
    TradeQuoteLifecycleStatus.UNKNOWN: DiagnosticCode.TRADE_UNKNOWN_STATUS,
}

_QUOTE_STATUS_CODE = {
    TradeQuoteLifecycleStatus.ORIGINAL: DiagnosticCode.QUOTE_ORIGINAL_RECORD,
    TradeQuoteLifecycleStatus.CORRECTED: DiagnosticCode.QUOTE_CORRECTED_RECORD,
    TradeQuoteLifecycleStatus.CANCELLED: DiagnosticCode.QUOTE_CANCELLED_RECORD,
    TradeQuoteLifecycleStatus.DELETED: DiagnosticCode.QUOTE_DELETED_RECORD,
    TradeQuoteLifecycleStatus.UNKNOWN: DiagnosticCode.QUOTE_UNKNOWN_STATUS,
}

_QUOTE_STATE_CODE = {
    "NORMAL": DiagnosticCode.QUOTE_NORMAL_MARKET,
    "LOCKED": DiagnosticCode.QUOTE_LOCKED_MARKET,
    "CROSSED": DiagnosticCode.QUOTE_CROSSED_MARKET,
    "UNKNOWN": DiagnosticCode.QUOTE_UNKNOWN_MARKET_STATE,
}


def _diagnostic(
    code: DiagnosticCode,
    severity: DiagnosticSeverity,
    field: str | None,
    message: str,
    continued: bool,
    record_id: str | None,
) -> NormalizationDiagnostic:
    return NormalizationDiagnostic(
        code=code,
        severity=severity,
        field=field,
        message=message,
        normalization_continued=continued,
        context={} if record_id is None else {"source_record_id": record_id},
    )


def _sorted_diagnostics(
    items: Iterable[NormalizationDiagnostic],
) -> tuple[NormalizationDiagnostic, ...]:
    return tuple(
        sorted(
            items,
            key=lambda item: (
                item.code.value,
                item.field or "",
                str(item.context.get("source_record_id", "")),
                item.message,
            ),
        )
    )


def _rejected(
    code: DiagnosticCode,
    message: str,
    raw_hash: str,
    record_id: str | None,
    field: str | None = None,
) -> NormalizationResult:
    return NormalizationResult(
        diagnostics=(
            _diagnostic(code, DiagnosticSeverity.ERROR, field, message, False, record_id),
        ),
        rejection=RejectedRecord(
            code=code,
            message=message,
            raw_record_hash=raw_hash,
            source_record_id=record_id,
        ),
    )


def _positive_decimal(value: object) -> Decimal:
    if value is None:
        raise ValueError("missing decimal")
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, AttributeError) as exc:
        raise ValueError("invalid decimal") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise ValueError("decimal must be positive")
    return parsed


def _structural_code(raw: Mapping[str, Any], error: ValidationError) -> DiagnosticCode:
    locations = {str(item) for detail in error.errors() for item in detail.get("loc", ())}
    record_type = str(raw.get("record_type", ""))
    if record_type == "TRADE" and "size" in locations:
        return DiagnosticCode.TRADE_INVALID_SIZE
    if record_type == "QUOTE" and {"bid_size", "ask_size"} & locations:
        return DiagnosticCode.QUOTE_INVALID_SIZE
    return DiagnosticCode.TRADE_QUOTE_INVALID_RECORD


def _optional_positive_decimal(value: object) -> Decimal | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    return _positive_decimal(value)


def _timestamps(
    record: TradeQuoteRecord,
    context: AdapterContext,
    raw_hash: str,
) -> tuple[datetime, datetime | None, datetime, list[NormalizationDiagnostic]] | NormalizationResult:
    if record.event_timestamp is None:
        return _rejected(
            DiagnosticCode.TRADE_QUOTE_MISSING_EVENT_TIMESTAMP,
            "Trade/quote event timestamp is required.",
            raw_hash,
            record.provider_record_id,
            "event_timestamp",
        )
    try:
        event = parse_trade_quote_timestamp(
            record.event_timestamp, source_timezone=context.source_timezone
        )
        capture = (
            None
            if record.capture_timestamp is None
            else parse_trade_quote_timestamp(
                record.capture_timestamp, source_timezone=context.source_timezone
            )
        )
        publication = (
            None
            if record.publication_timestamp is None
            else parse_trade_quote_timestamp(
                record.publication_timestamp, source_timezone=context.source_timezone
            )
        )
    except TradeQuoteValidationError:
        return _rejected(
            DiagnosticCode.TRADE_QUOTE_INVALID_TIMESTAMP,
            "Trade/quote timestamp is invalid or lacks timezone meaning.",
            raw_hash,
            record.provider_record_id,
        )
    diagnostics: list[NormalizationDiagnostic] = []
    source_boundary = publication
    if source_boundary is None:
        if record.unknown_availability_policy is UnknownAvailabilityPolicy.STRICT:
            return _rejected(
                DiagnosticCode.TRADE_QUOTE_UNKNOWN_AVAILABILITY,
                "Provider publication is unknown under STRICT policy.",
                raw_hash,
                record.provider_record_id,
                "publication_timestamp",
            )
        if (
            record.unknown_availability_policy
            is UnknownAvailabilityPolicy.CAPTURE_AS_UNCERTAIN_PLACEHOLDER
        ):
            if capture is None:
                return _rejected(
                    DiagnosticCode.TRADE_QUOTE_UNKNOWN_AVAILABILITY,
                    "Capture placeholder policy requires capture time.",
                    raw_hash,
                    record.provider_record_id,
                    "capture_timestamp",
                )
            source_boundary = capture
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.TRADE_QUOTE_CAPTURE_PLACEHOLDER,
                    DiagnosticSeverity.WARNING,
                    "publication_timestamp",
                    "Capture time is an uncertain availability placeholder, not publication time.",
                    True,
                    record.provider_record_id,
                )
            )
        else:
            source_boundary = context.ingested_at
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.TRADE_QUOTE_RECEIPT_PLACEHOLDER,
                    DiagnosticSeverity.WARNING,
                    "publication_timestamp",
                    "Receipt time is an uncertain availability placeholder, not publication time.",
                    True,
                    record.provider_record_id,
                )
            )
    if source_boundary > context.ingested_at:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.TRADE_QUOTE_PUBLICATION_AFTER_RECEIPT,
                DiagnosticSeverity.WARNING,
                "publication_timestamp",
                "Claimed publication follows local receipt; effective time waits for publication.",
                True,
                record.provider_record_id,
            )
        )
    return event, capture, source_boundary, diagnostics


def _normalize_quote(
    record: TradeQuoteRecord,
    context: AdapterContext,
    raw_hash: str,
    event: datetime,
    capture: datetime | None,
    source_boundary: datetime,
    diagnostics: list[NormalizationDiagnostic],
) -> NormalizationResult:
    try:
        bid_price = _optional_positive_decimal(record.bid_price)
        ask_price = _optional_positive_decimal(record.ask_price)
    except ValueError:
        return _rejected(
            DiagnosticCode.QUOTE_INVALID_PRICE,
            "Present quote prices must be positive exact decimals.",
            raw_hash,
            record.provider_record_id,
            "bid_price/ask_price",
        )
    if (
        bid_price is None
        and ask_price is None
        and record.bid_size is None
        and record.ask_size is None
    ):
        return _rejected(
            DiagnosticCode.QUOTE_MISSING_BOTH_SIDES,
            "Quote must preserve at least one reported side field.",
            raw_hash,
            record.provider_record_id,
            "bid/ask",
        )
    partial = bid_price is None or ask_price is None
    if partial:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.QUOTE_ONE_SIDED,
                DiagnosticSeverity.WARNING,
                "bid/ask",
                "One-sided quote is preserved without fabricating the missing side.",
                True,
                record.provider_record_id,
            )
        )
    for side, size in (("bid", record.bid_size), ("ask", record.ask_size)):
        if size is None:
            partial = True
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.QUOTE_MISSING_BID_SIZE
                    if side == "bid"
                    else DiagnosticCode.QUOTE_MISSING_ASK_SIZE,
                    DiagnosticSeverity.INFO,
                    f"{side}_size",
                    f"{side.title()} size is missing and remains null.",
                    True,
                    record.provider_record_id,
                )
            )
        elif size == 0:
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.QUOTE_ZERO_BID_SIZE
                    if side == "bid"
                    else DiagnosticCode.QUOTE_ZERO_ASK_SIZE,
                    DiagnosticSeverity.INFO,
                    f"{side}_size",
                    f"Observed zero {side} size is preserved as zero.",
                    True,
                    record.provider_record_id,
                )
            )
    if (bid_price is None and record.bid_size is not None) or (
        ask_price is None and record.ask_size is not None
    ):
        partial = True
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.QUOTE_SIZE_WITHOUT_PRICE,
                DiagnosticSeverity.WARNING,
                "bid/ask",
                "A side size without its side price is preserved as structurally unusual.",
                True,
                record.provider_record_id,
            )
        )
    state = quote_market_state(bid_price, ask_price)
    diagnostics.append(
        _diagnostic(
            _QUOTE_STATE_CODE[state.value],
            DiagnosticSeverity.WARNING if state.value in {"CROSSED", "UNKNOWN"} else DiagnosticSeverity.INFO,
            "bid_price/ask_price",
            f"Objective quote market state is {state.value}.",
            True,
            record.provider_record_id,
        )
    )
    if record.market_scope.value == "UNKNOWN":
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.QUOTE_UNKNOWN_MARKET_SCOPE,
                DiagnosticSeverity.WARNING,
                "market_scope",
                "Quote market scope is unknown and is not synthesized.",
                True,
                record.provider_record_id,
            )
        )
    if record.venue is None:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.QUOTE_MISSING_VENUE,
                DiagnosticSeverity.WARNING,
                "venue",
                "Quote venue is unknown and remains null.",
                True,
                record.provider_record_id,
            )
        )
    if record.quote_source is None:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.QUOTE_MISSING_SOURCE,
                DiagnosticSeverity.WARNING,
                "quote_source",
                "Provider quote-source label is missing and remains null.",
                True,
                record.provider_record_id,
            )
        )
    if record.quote_condition and record.quote_condition.upper().startswith("PROVIDER_"):
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.QUOTE_UNKNOWN_CONDITION,
                DiagnosticSeverity.INFO,
                "quote_condition",
                "Unknown provider quote condition is preserved without interpretation.",
                True,
                record.provider_record_id,
            )
        )
    diagnostics.append(
        _diagnostic(
            _QUOTE_STATUS_CODE[record.status],
            DiagnosticSeverity.WARNING
            if record.status is TradeQuoteLifecycleStatus.UNKNOWN
            else DiagnosticSeverity.INFO,
            "status",
            f"Objective quote lifecycle status is {record.status.value}.",
            True,
            record.provider_record_id,
        )
    )
    completeness = Completeness.PARTIAL if partial else Completeness.COMPLETE
    metadata = {
        "adapter_version": context.adapter_version,
        "normalization_version": context.normalization_version,
        "fixture_origin": record.fixture_origin.value,
        "provider": record.provider,
        "provider_record_id": record.provider_record_id,
        "record_type": record.record_type.value,
        "event_timestamp": event,
        "publication_timestamp": None
        if record.publication_timestamp is None
        else source_boundary,
        "availability_boundary": source_boundary,
        "availability_policy": record.unknown_availability_policy.value,
        "capture_timestamp": capture,
        "venue": record.venue,
        "market_scope": record.market_scope.value,
        "quote_condition": record.quote_condition,
        "quote_source": record.quote_source,
        "quote_market_state": state.value,
        "bid_side_id": record.bid_side_id,
        "ask_side_id": record.ask_side_id,
        "sequence_number": record.sequence_number,
        "sequence_scope": record.sequence_scope.value,
        "sequence_channel": record.sequence_channel,
        "sequence_session": record.sequence_session,
        "sequence_reset": record.sequence_reset,
        "size_unit": record.size_unit.value,
        "status": record.status.value,
        "revision_number": record.revision_number,
        "supersedes_provider_record_id": record.supersedes_provider_record_id,
        "provider_metadata": record.provider_metadata,
        "source_endpoint_name": context.source_endpoint_name,
    }
    observation = Observation(
        schema_version="1.0.0",
        event_type=EventType.QUOTE,
        symbol=record.symbol,
        asset_class=AssetClass.EQUITY,
        source=f"trade_quote:{record.provider.lower()}",
        source_record_id=record.provider_record_id,
        source_timestamp=source_boundary,
        received_timestamp=context.ingested_at,
        effective_timestamp=max(source_boundary, context.ingested_at),
        market_session=record.market_session,
        data_freshness=DataFreshness.HISTORICAL,
        observation_kind=ObservationKind.MARKET_OBSERVED,
        quality=Quality(
            state=QualityState.KNOWN_VALUE,
            evaluated_at=context.ingested_at,
            completeness=completeness,
        ),
        payload_type=PayloadType.QUOTE,
        payload=QuotePayload(
            bid_price=bid_price,
            bid_size=record.bid_size,
            ask_price=ask_price,
            ask_size=record.ask_size,
            exchange=record.exchange,
        ),
        provenance=Provenance(
            provider=record.provider,
            ingestion_method=context.collection_method,
            origin_kind=ObservationKind.MARKET_OBSERVED,
            normalized=True,
            normalization_version=context.normalization_version,
            completeness=completeness,
            naming_modified=True,
            entitlement_state=context.entitlement_status,
            source_timezone=context.source_timezone,
            source_timestamp_representation=None
            if record.publication_timestamp is None
            else str(record.publication_timestamp),
            provider_metadata=metadata,
        ),
        sequence_number=record.sequence_number,
        exchange=record.exchange,
        timezone=context.source_timezone,
        raw_payload_hash=raw_hash,
        normalization_version=context.normalization_version,
    )
    return NormalizationResult(
        observations=(observation,), diagnostics=_sorted_diagnostics(diagnostics)
    )


def normalize_trade_quote_record(
    provider_record: TradeQuoteRecord | Mapping[str, Any],
    context: AdapterContext,
) -> NormalizationResult:
    raw_hash = canonical_hash(provider_record)
    try:
        record = (
            provider_record
            if isinstance(provider_record, TradeQuoteRecord)
            else TradeQuoteRecord.model_validate(provider_record)
        )
    except ValidationError as error:
        raw = provider_record if isinstance(provider_record, Mapping) else {}
        record_id = raw.get("provider_record_id")
        return _rejected(
            _structural_code(raw, error),
            "Trade/quote provider record failed structural validation.",
            raw_hash,
            None if record_id is None else str(record_id),
        )
    times = _timestamps(record, context, raw_hash)
    if isinstance(times, NormalizationResult):
        return times
    event, capture, source_boundary, diagnostics = times
    if record.record_type is TradeQuoteRecordType.QUOTE:
        return _normalize_quote(
            record,
            context,
            raw_hash,
            event,
            capture,
            source_boundary,
            diagnostics,
        )
    try:
        price = _positive_decimal(record.price)
    except ValueError:
        return _rejected(
            DiagnosticCode.TRADE_INVALID_PRICE,
            "Trade price must be a positive exact decimal.",
            raw_hash,
            record.provider_record_id,
            "price",
        )
    if record.size is None:
        completeness = Completeness.PARTIAL
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.TRADE_MISSING_SIZE,
                DiagnosticSeverity.WARNING,
                "size",
                "Trade size is missing and remains null.",
                True,
                record.provider_record_id,
            )
        )
    else:
        completeness = Completeness.COMPLETE
        if record.size == 0:
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.TRADE_ZERO_SIZE,
                    DiagnosticSeverity.INFO,
                    "size",
                    "Observed zero trade size is preserved as zero.",
                    True,
                    record.provider_record_id,
                )
            )
    conditions = normalize_conditions(record.trade_conditions)
    if any(item.upper().startswith("PROVIDER_") for item in conditions):
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.TRADE_UNKNOWN_CONDITION,
                DiagnosticSeverity.INFO,
                "trade_conditions",
                "Unknown provider trade condition is preserved without interpretation.",
                True,
                record.provider_record_id,
            )
        )
    if record.venue is None:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.TRADE_MISSING_VENUE,
                DiagnosticSeverity.WARNING,
                "venue",
                "Trade venue is unknown and remains null.",
                True,
                record.provider_record_id,
            )
        )
    diagnostics.append(
        _diagnostic(
            _TRADE_STATUS_CODE[record.status],
            DiagnosticSeverity.WARNING
            if record.status is TradeQuoteLifecycleStatus.UNKNOWN
            else DiagnosticSeverity.INFO,
            "status",
            f"Objective trade lifecycle status is {record.status.value}.",
            True,
            record.provider_record_id,
        )
    )
    metadata = {
        "adapter_version": context.adapter_version,
        "normalization_version": context.normalization_version,
        "fixture_origin": record.fixture_origin.value,
        "provider": record.provider,
        "provider_record_id": record.provider_record_id,
        "record_type": record.record_type.value,
        "event_timestamp": event,
        "publication_timestamp": None
        if record.publication_timestamp is None
        else source_boundary,
        "availability_boundary": source_boundary,
        "availability_policy": record.unknown_availability_policy.value,
        "capture_timestamp": capture,
        "venue": record.venue,
        "market_scope": record.market_scope.value,
        "sequence_number": record.sequence_number,
        "sequence_scope": record.sequence_scope.value,
        "sequence_channel": record.sequence_channel,
        "sequence_session": record.sequence_session,
        "sequence_reset": record.sequence_reset,
        "size_unit": record.size_unit.value,
        "sale_condition": record.sale_condition,
        "status": record.status.value,
        "revision_number": record.revision_number,
        "supersedes_provider_record_id": record.supersedes_provider_record_id,
        "provider_metadata": record.provider_metadata,
        "source_endpoint_name": context.source_endpoint_name,
    }
    observation = Observation(
        schema_version="1.0.0",
        event_type=EventType.TRADE,
        symbol=record.symbol,
        asset_class=AssetClass.EQUITY,
        source=f"trade_quote:{record.provider.lower()}",
        source_record_id=record.provider_record_id,
        source_timestamp=source_boundary,
        received_timestamp=context.ingested_at,
        effective_timestamp=max(source_boundary, context.ingested_at),
        market_session=record.market_session,
        data_freshness=DataFreshness.HISTORICAL,
        observation_kind=ObservationKind.MARKET_OBSERVED,
        quality=Quality(
            state=QualityState.KNOWN_VALUE,
            evaluated_at=context.ingested_at,
            completeness=completeness,
        ),
        payload_type=PayloadType.TRADE,
        payload=TradePayload(
            price=price,
            size=record.size,
            exchange=record.exchange,
            conditions=conditions,
        ),
        provenance=Provenance(
            provider=record.provider,
            ingestion_method=context.collection_method,
            origin_kind=ObservationKind.MARKET_OBSERVED,
            normalized=True,
            normalization_version=context.normalization_version,
            completeness=completeness,
            naming_modified=True,
            entitlement_state=context.entitlement_status,
            source_timezone=context.source_timezone,
            source_timestamp_representation=None
            if record.publication_timestamp is None
            else str(record.publication_timestamp),
            provider_metadata=metadata,
        ),
        sequence_number=record.sequence_number,
        exchange=record.exchange,
        timezone=context.source_timezone,
        raw_payload_hash=raw_hash,
        normalization_version=context.normalization_version,
    )
    return NormalizationResult(
        observations=(observation,), diagnostics=_sorted_diagnostics(diagnostics)
    )


def normalize_trade_quote_records(
    provider_records: Iterable[TradeQuoteRecord | Mapping[str, Any]],
    context: AdapterContext,
) -> NormalizationResult:
    observations: list[Observation] = []
    diagnostics: list[NormalizationDiagnostic] = []
    seen_hashes: set[str] = set()
    first_rejection: RejectedRecord | None = None
    for arrival_index, raw in enumerate(provider_records):
        raw_hash = canonical_hash(raw)
        raw_id_value = (
            raw.provider_record_id
            if isinstance(raw, TradeQuoteRecord)
            else raw.get("provider_record_id")
        )
        raw_id = None if raw_id_value is None else str(raw_id_value)
        if raw_hash in seen_hashes:
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.TRADE_QUOTE_DUPLICATE_RECORD,
                    DiagnosticSeverity.WARNING,
                    "provider_record_id",
                    "Exact duplicate trade/quote record was emitted only once.",
                    True,
                    raw_id,
                )
            )
            continue
        seen_hashes.add(raw_hash)
        result = normalize_trade_quote_record(raw, context)
        for observation in result.observations:
            metadata = dict(observation.provenance.provider_metadata)
            metadata["arrival_index"] = arrival_index
            provenance = observation.provenance.model_copy(
                update={"provider_metadata": metadata}
            )
            observations.append(observation.model_copy(update={"provenance": provenance}))
        diagnostics.extend(result.diagnostics)
        if result.rejection is not None and first_rejection is None:
            first_rejection = result.rejection

    grouped: dict[tuple[str, str, str], list[int]] = {}
    for index, observation in enumerate(observations):
        metadata = observation.provenance.provider_metadata
        grouped.setdefault(
            (
                str(metadata["provider"]),
                str(metadata["record_type"]),
                observation.source_record_id,
            ),
            [],
        ).append(index)
    for key, indexes in sorted(grouped.items()):
        if len(indexes) < 2:
            continue
        correlation_id = f"trade-quote-conflict-{canonical_hash(key)[:16]}"
        for index in indexes:
            current = observations[index]
            observations[index] = current.model_copy(
                update={
                    "correlation_id": correlation_id,
                    "quality": current.quality.model_copy(
                        update={
                            "state": QualityState.CONFLICTED,
                            "reasons": ("same provider record identity has changed content",),
                        }
                    ),
                }
            )
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.TRADE_QUOTE_CONFLICTING_RECORD,
                DiagnosticSeverity.ERROR,
                "provider_record_id",
                "Same provider record identity has changed content; all versions are preserved.",
                True,
                key[2],
            )
        )

    by_provider_id: dict[tuple[str, str], list[int]] = {}
    for index, observation in enumerate(observations):
        provider = str(observation.provenance.provider_metadata["provider"])
        by_provider_id.setdefault((provider, observation.source_record_id), []).append(index)
    for index, observation in enumerate(tuple(observations)):
        metadata = observation.provenance.provider_metadata
        supersedes = metadata.get("supersedes_provider_record_id")
        if not supersedes:
            continue
        candidates = by_provider_id.get((str(metadata["provider"]), str(supersedes)), [])
        if not candidates:
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.TRADE_QUOTE_REVISION_LINK_MISSING,
                    DiagnosticSeverity.WARNING,
                    "supersedes_provider_record_id",
                    "Prior trade/quote record was not present in this batch.",
                    True,
                    observation.source_record_id,
                )
            )
            continue
        prior_index = min(candidates, key=lambda item: observations[item].observation_id)
        prior = observations[prior_index]
        correlation_id = f"trade-quote-revision-{canonical_hash((prior.observation_id, observation.observation_id))[:16]}"
        observations[prior_index] = prior.model_copy(update={"correlation_id": correlation_id})
        observations[index] = observation.model_copy(
            update={
                "parent_observation_ids": (prior.observation_id,),
                "correlation_id": correlation_id,
            }
        )

    observations.sort(key=observation_order_key)
    return NormalizationResult(
        observations=tuple(observations),
        diagnostics=_sorted_diagnostics(diagnostics),
        rejection=first_rejection,
    )
