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
    BarPayload,
    Completeness,
    DataFreshness,
    EventType,
    MarketSession,
    Observation,
    ObservationKind,
    PayloadType,
    Provenance,
    Quality,
    QualityState,
)
from squeeze_core.replay.engine import observation_order_key
from squeeze_core.serialization import canonical_hash

from .models import MarketBarRecord
from .parsing import BarParseError, parse_bar_timestamp, resolve_bar_boundaries
from .semantics import (
    PROVIDER_SOURCE,
    BarCompletionStatus,
    BarSession,
)
from .validation import structural_diagnostic_code


_SESSION_MAP = {
    BarSession.PREMARKET: MarketSession.PRE_MARKET,
    BarSession.REGULAR: MarketSession.REGULAR,
    BarSession.AFTER_HOURS: MarketSession.AFTER_HOURS,
    BarSession.CLOSED_SESSION: MarketSession.CLOSED,
    BarSession.OVERNIGHT: MarketSession.UNKNOWN,
    BarSession.EXTENDED: MarketSession.UNKNOWN,
    BarSession.UNKNOWN: MarketSession.UNKNOWN,
}

_STATUS_CODE = {
    BarCompletionStatus.PARTIAL: DiagnosticCode.BAR_PARTIAL_RECORD,
    BarCompletionStatus.COMPLETED: DiagnosticCode.BAR_COMPLETED_RECORD,
    BarCompletionStatus.CORRECTED: DiagnosticCode.BAR_CORRECTED_RECORD,
    BarCompletionStatus.CANCELLED: DiagnosticCode.BAR_CANCELLED_RECORD,
    BarCompletionStatus.UNKNOWN: DiagnosticCode.BAR_UNKNOWN_STATUS,
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


def _sorted_diagnostics(items: Iterable[NormalizationDiagnostic]) -> tuple[NormalizationDiagnostic, ...]:
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


def _decimal(value: object, *, field: str) -> Decimal:
    if value is None:
        raise ValueError(f"missing {field}")
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, AttributeError) as error:
        raise ValueError(f"invalid {field}") from error
    if not parsed.is_finite() or parsed <= 0:
        raise ValueError(f"invalid {field}")
    return parsed


def _optional_count(value: object, *, field: str) -> int | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, ValueError, AttributeError) as error:
        raise ValueError(f"invalid {field}") from error
    if not parsed.is_finite() or parsed < 0 or parsed != parsed.to_integral_value():
        raise ValueError(f"invalid {field}")
    return int(parsed)


def _record_date_representation(record: MarketBarRecord) -> str | None:
    raw = record.bar_start or (
        record.provider_timestamp
        if record.timestamp_meaning.value == "START"
        else None
    )
    if raw is None:
        return None
    value = raw.strip()
    return value[:10] if len(value) >= 10 and value[4:5] == "-" else None


def normalize_market_bar_record(
    provider_record: MarketBarRecord | Mapping[str, Any],
    context: AdapterContext,
) -> NormalizationResult:
    raw_hash = canonical_hash(provider_record)
    try:
        record = (
            provider_record
            if isinstance(provider_record, MarketBarRecord)
            else MarketBarRecord.model_validate(provider_record)
        )
    except ValidationError as error:
        raw = provider_record if isinstance(provider_record, Mapping) else {}
        code = DiagnosticCode(structural_diagnostic_code(raw, error))
        raw_id = raw.get("source_record_id")
        return _rejected(
            code,
            "Market-bar provider record failed structural validation.",
            raw_hash,
            None if raw_id is None else str(raw_id),
        )

    if record.asset_class.value != "EQUITY":
        return _rejected(
            DiagnosticCode.BAR_UNSUPPORTED_ASSET_CLASS,
            "Phase 1H fixtures support equity share-volume bars only.",
            raw_hash,
            record.source_record_id,
            "asset_class",
        )

    try:
        boundaries = resolve_bar_boundaries(record)
    except BarParseError as error:
        return _rejected(
            DiagnosticCode(error.code), str(error), raw_hash, record.source_record_id
        )

    represented_date = _record_date_representation(record)
    if (
        record.session_date is not None
        and represented_date is not None
        and represented_date != record.session_date.isoformat()
    ):
        return _rejected(
            DiagnosticCode.BAR_SESSION_DATE_MISMATCH,
            "Bar start date does not match the supplied session date.",
            raw_hash,
            record.source_record_id,
            "session_date",
        )

    try:
        publication = parse_bar_timestamp(
            record.publication_timestamp,
            session_date=record.session_date,
            timezone_name=record.timezone or context.source_timezone,
            field="publication_timestamp",
        )
        capture = parse_bar_timestamp(
            record.capture_timestamp,
            session_date=record.session_date,
            timezone_name=record.timezone or context.source_timezone,
            field="capture_timestamp",
        )
    except BarParseError as error:
        return _rejected(
            DiagnosticCode(error.code), str(error), raw_hash, record.source_record_id
        )
    if publication is None:
        return _rejected(
            DiagnosticCode.BAR_UNKNOWN_AVAILABILITY,
            "No defensible provider publication timestamp exists.",
            raw_hash,
            record.source_record_id,
            "publication_timestamp",
        )

    prices: dict[str, Decimal] = {}
    for field in ("open", "high", "low", "close"):
        value = getattr(record, field)
        if value is None or (isinstance(value, str) and not value.strip()):
            return _rejected(
                DiagnosticCode[f"BAR_MISSING_{field.upper()}"],
                f"Required canonical {field} is missing; it is not calculated.",
                raw_hash,
                record.source_record_id,
                field,
            )
        try:
            prices[field] = _decimal(value, field=field)
        except ValueError:
            return _rejected(
                DiagnosticCode.BAR_INVALID_OHLC,
                f"Bar {field} must be a positive exact decimal.",
                raw_hash,
                record.source_record_id,
                field,
            )
    if (
        prices["high"] < max(prices["open"], prices["close"], prices["low"])
        or prices["low"] > min(prices["open"], prices["close"], prices["high"])
    ):
        return _rejected(
            DiagnosticCode.BAR_INVALID_OHLC,
            "Bar OHLC relationships are impossible.",
            raw_hash,
            record.source_record_id,
        )

    diagnostics: list[NormalizationDiagnostic] = []
    try:
        volume = _optional_count(record.volume, field="volume")
    except ValueError:
        return _rejected(
            DiagnosticCode.BAR_INVALID_VOLUME,
            "Volume must be a non-negative integer.",
            raw_hash,
            record.source_record_id,
            "volume",
        )
    if volume is None:
        diagnostics.append(_diagnostic(DiagnosticCode.BAR_MISSING_VOLUME, DiagnosticSeverity.WARNING, "volume", "Volume is missing and remains null.", True, record.source_record_id))
    elif volume == 0:
        diagnostics.append(_diagnostic(DiagnosticCode.BAR_ZERO_VOLUME, DiagnosticSeverity.INFO, "volume", "Observed zero volume is preserved as zero.", True, record.source_record_id))

    try:
        trade_count = _optional_count(record.trade_count, field="trade_count")
    except ValueError:
        return _rejected(DiagnosticCode.BAR_INVALID_TRADE_COUNT, "Trade count must be a non-negative integer.", raw_hash, record.source_record_id, "trade_count")
    if trade_count is None:
        diagnostics.append(_diagnostic(DiagnosticCode.BAR_MISSING_TRADE_COUNT, DiagnosticSeverity.INFO, "trade_count", "Trade count is missing and remains null.", True, record.source_record_id))
    elif trade_count == 0:
        diagnostics.append(_diagnostic(DiagnosticCode.BAR_ZERO_TRADE_COUNT, DiagnosticSeverity.INFO, "trade_count", "Observed zero trade count is preserved as zero.", True, record.source_record_id))

    vwap = None
    if record.vwap is None or (isinstance(record.vwap, str) and not record.vwap.strip()):
        diagnostics.append(_diagnostic(DiagnosticCode.BAR_MISSING_VWAP, DiagnosticSeverity.INFO, "vwap", "VWAP is missing and is not calculated.", True, record.source_record_id))
    else:
        try:
            vwap = _decimal(record.vwap, field="vwap")
        except ValueError:
            return _rejected(DiagnosticCode.BAR_INVALID_VWAP, "VWAP must be a positive exact decimal.", raw_hash, record.source_record_id, "vwap")

    status_code = _STATUS_CODE[record.status]
    diagnostics.append(
        _diagnostic(
            status_code,
            DiagnosticSeverity.WARNING if record.status in {BarCompletionStatus.PARTIAL, BarCompletionStatus.UNKNOWN} else DiagnosticSeverity.INFO,
            "status",
            f"Objective market-bar lifecycle status is {record.status.value}.",
            True,
            record.source_record_id,
        )
    )
    if record.session is BarSession.UNKNOWN:
        diagnostics.append(_diagnostic(DiagnosticCode.BAR_SESSION_UNKNOWN, DiagnosticSeverity.WARNING, "session", "Source session is unknown and remains representable.", True, record.source_record_id))
    if publication.timestamp > context.ingested_at:
        diagnostics.append(_diagnostic(DiagnosticCode.BAR_PUBLICATION_AFTER_RECEIPT, DiagnosticSeverity.WARNING, "publication_timestamp", "Claimed provider publication follows local receipt; effective time waits for publication.", True, record.source_record_id))
        diagnostics.append(_diagnostic(DiagnosticCode.BAR_RECEIVED_BEFORE_PUBLICATION, DiagnosticSeverity.WARNING, "received_timestamp", "Local receipt precedes claimed provider publication.", True, record.source_record_id))

    partial = record.status is BarCompletionStatus.PARTIAL
    completeness = Completeness.PARTIAL if partial else Completeness.COMPLETE
    source_record_id = record.provider_record_id or f"derived:{canonical_hash({'provider': record.provider, 'symbol': record.symbol, 'interval': record.interval, 'start': boundaries.start, 'raw_hash': raw_hash})[:24]}"
    metadata = {
        "adapter_version": context.adapter_version,
        "normalization_version": context.normalization_version,
        "fixture_origin": record.fixture_origin,
        "fixture_source_record_id": record.source_record_id,
        "provider": record.provider,
        "provider_record_id": record.provider_record_id,
        "bar_start": boundaries.start,
        "bar_end": boundaries.end,
        "bar_end_exclusive": boundaries.end_exclusive,
        "interval": record.interval,
        "interval_magnitude": record.interval.magnitude,
        "interval_unit": record.interval.unit,
        "interval_kind": record.interval.kind,
        "provider_timestamp": record.provider_timestamp,
        "timestamp_meaning": record.timestamp_meaning,
        "publication_timestamp": publication.timestamp,
        "publication_timestamp_representation": publication.representation,
        "capture_timestamp": None if capture is None else capture.timestamp,
        "capture_timestamp_representation": record.capture_timestamp,
        "session": record.session,
        "session_date": None if record.session_date is None else record.session_date.isoformat(),
        "volume_unit": record.volume_unit,
        "status": record.status,
        "revision_number": record.revision_number,
        "supersedes_provider_record_id": record.supersedes_provider_record_id,
        "provider_metadata": record.provider_metadata,
        "source_endpoint_name": context.source_endpoint_name,
    }
    observation = Observation(
        schema_version="1.0.0",
        event_type=EventType.BAR,
        symbol=record.symbol,
        asset_class=record.asset_class,
        source=f"{PROVIDER_SOURCE}:{record.provider.lower()}",
        source_record_id=source_record_id,
        source_timestamp=publication.timestamp,
        received_timestamp=context.ingested_at,
        effective_timestamp=max(publication.timestamp, context.ingested_at),
        market_session=_SESSION_MAP[record.session],
        data_freshness=DataFreshness.HISTORICAL,
        observation_kind=ObservationKind.MARKET_OBSERVED,
        quality=Quality(
            state=QualityState.KNOWN_VALUE,
            evaluated_at=context.ingested_at,
            completeness=completeness,
        ),
        payload_type=PayloadType.BAR,
        payload=BarPayload(
            timeframe=record.interval.value,
            open=prices["open"],
            high=prices["high"],
            low=prices["low"],
            close=prices["close"],
            volume=volume,
            trade_count=trade_count,
            vwap=vwap,
        ),
        provenance=Provenance(
            provider=context.provider,
            ingestion_method=context.collection_method,
            origin_kind=ObservationKind.MARKET_OBSERVED,
            normalized=True,
            normalization_version=context.normalization_version,
            completeness=completeness,
            naming_modified=True,
            entitlement_state=context.entitlement_status,
            source_timezone=publication.timezone_label,
            source_timestamp_representation=publication.representation,
            provider_metadata=metadata,
        ),
        exchange=record.exchange,
        timezone=publication.timezone_label,
        raw_payload_hash=raw_hash,
        normalization_version=context.normalization_version,
    )
    return NormalizationResult(
        observations=(observation,), diagnostics=_sorted_diagnostics(diagnostics)
    )


def normalize_market_bar_records(
    provider_records: Iterable[MarketBarRecord | Mapping[str, Any]],
    context: AdapterContext,
) -> NormalizationResult:
    observations: list[Observation] = []
    diagnostics: list[NormalizationDiagnostic] = []
    seen_hashes: set[str] = set()
    first_rejection: RejectedRecord | None = None
    for raw in provider_records:
        raw_hash = canonical_hash(raw)
        raw_id_value = raw.source_record_id if isinstance(raw, MarketBarRecord) else raw.get("source_record_id")
        raw_id = None if raw_id_value is None else str(raw_id_value)
        if raw_hash in seen_hashes:
            diagnostics.append(_diagnostic(DiagnosticCode.BAR_DUPLICATE_RECORD, DiagnosticSeverity.WARNING, "source_record_id", "Exact duplicate market-bar record was emitted only once.", True, raw_id))
            continue
        seen_hashes.add(raw_hash)
        result = normalize_market_bar_record(raw, context)
        observations.extend(result.observations)
        diagnostics.extend(result.diagnostics)
        if result.rejection is not None and first_rejection is None:
            first_rejection = result.rejection

    by_source_id = {item.source_record_id: item for item in observations}
    for index, observation in enumerate(tuple(observations)):
        supersedes = observation.provenance.provider_metadata.get("supersedes_provider_record_id")
        if not supersedes:
            continue
        prior = by_source_id.get(str(supersedes))
        if prior is None:
            diagnostics.append(_diagnostic(DiagnosticCode.BAR_REVISION_LINK_MISSING, DiagnosticSeverity.WARNING, "supersedes_provider_record_id", "Prior market-bar record was not present in this batch.", True, observation.source_record_id))
            continue
        correlation_id = f"bar-revision-{canonical_hash((prior.observation_id, observation.observation_id))[:16]}"
        prior_index = observations.index(prior)
        observations[prior_index] = prior.model_copy(update={"correlation_id": correlation_id})
        observations[index] = observation.model_copy(update={"parent_observation_ids": (prior.observation_id,), "correlation_id": correlation_id})
        by_source_id[prior.source_record_id] = observations[prior_index]
        by_source_id[observation.source_record_id] = observations[index]

    grouped: dict[str, list[int]] = {}
    for index, observation in enumerate(observations):
        grouped.setdefault(observation.source_record_id, []).append(index)
    for source_id, indexes in grouped.items():
        if len(indexes) < 2 or len({observations[index].raw_payload_hash for index in indexes}) == 1:
            continue
        correlation_id = f"bar-conflict-{canonical_hash(source_id)[:16]}"
        for index in indexes:
            current = observations[index]
            observations[index] = current.model_copy(
                update={
                    "quality": Quality(
                        state=QualityState.CONFLICTED,
                        reasons=("same provider record ID has conflicting market-bar content",),
                        evaluated_at=context.ingested_at,
                        completeness=current.quality.completeness,
                    ),
                    "correlation_id": correlation_id,
                }
            )
        diagnostics.append(_diagnostic(DiagnosticCode.BAR_CONFLICTING_RECORD, DiagnosticSeverity.ERROR, "provider_record_id", "Conflicting same-ID market-bar records were preserved; no winner was selected.", True, source_id))

    observations.sort(key=observation_order_key)
    if not observations and first_rejection is not None:
        return NormalizationResult(diagnostics=_sorted_diagnostics(diagnostics), rejection=first_rejection)
    return NormalizationResult(observations=tuple(observations), diagnostics=_sorted_diagnostics(diagnostics))
