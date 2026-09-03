from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any, Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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
    MarketSession,
    MarketSnapshotPayload,
    Observation,
    ObservationKind,
    PayloadType,
    Provenance,
    Quality,
    QualityState,
)
from squeeze_core.serialization import canonical_hash
from squeeze_core.serialization.canonical_json import canonicalize

from .models import FinvizSnapshotRecord
from .parsing import (
    FinvizParseError,
    ParsedQuantity,
    parse_earnings,
    parse_percentage,
    parse_price,
    parse_quantity,
    parse_ratio,
)
from .semantics import DelayStatus, PROVIDER_SOURCE, SNAPSHOT_SCOPE, PercentageUnit


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


def _timezone(value: str):
    if value == "UTC":
        return UTC
    if len(value) == 6 and value[0] in "+-" and value[3] == ":":
        hours = int(value[1:3])
        minutes = int(value[4:6])
        if hours > 23 or minutes > 59:
            raise ValueError("invalid UTC offset")
        offset = timedelta(hours=hours, minutes=minutes)
        return timezone(-offset if value[0] == "-" else offset)
    return ZoneInfo(value)


def _timestamp(raw: str, timezone_name: str | None) -> tuple[datetime, str]:
    if len(raw) == 10:
        if timezone_name is None:
            raise ZoneInfoNotFoundError("timezone is absent")
        parsed = datetime.combine(date.fromisoformat(raw), time.min, tzinfo=_timezone(timezone_name))
        return parsed.astimezone(UTC), timezone_name
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        if timezone_name is None:
            raise ZoneInfoNotFoundError("timezone is absent")
        parsed = parsed.replace(tzinfo=_timezone(timezone_name))
        return parsed.astimezone(UTC), timezone_name
    return parsed.astimezone(UTC), timezone_name or "EMBEDDED_OFFSET"


def _structural_code(error: ValidationError) -> DiagnosticCode:
    details = error.errors()
    if any(item["type"] == "extra_forbidden" for item in details):
        return DiagnosticCode.FINVIZ_UNSUPPORTED_FIELD_ALIAS
    locations = {str(item["loc"][0]) for item in details if item.get("loc")}
    if "provider_schema" in locations:
        return DiagnosticCode.FINVIZ_UNSUPPORTED_SCHEMA
    if "record_type" in locations:
        return DiagnosticCode.FINVIZ_UNSUPPORTED_RECORD_TYPE
    if "fixture_origin" in locations:
        return DiagnosticCode.FINVIZ_INVALID_FIXTURE_ORIGIN
    if "symbol" in locations:
        return DiagnosticCode.FINVIZ_MISSING_SYMBOL
    return DiagnosticCode.INVALID_NUMERIC_VALUE


def normalize_finviz_snapshot_record(
    provider_record: FinvizSnapshotRecord | Mapping[str, Any],
    context: AdapterContext,
) -> NormalizationResult:
    raw_hash = canonical_hash(provider_record)
    try:
        record = (
            provider_record
            if isinstance(provider_record, FinvizSnapshotRecord)
            else FinvizSnapshotRecord.model_validate(provider_record)
        )
    except ValidationError as error:
        code = _structural_code(error)
        record_id = (
            provider_record.get("source_record_id")
            if isinstance(provider_record, Mapping)
            else None
        )
        diagnostic = _diagnostic(
            code,
            DiagnosticSeverity.ERROR,
            None,
            "Finviz-shaped provider record failed structural validation.",
            False,
            str(record_id) if record_id is not None else None,
        )
        return NormalizationResult(
            diagnostics=(diagnostic,),
            rejection=RejectedRecord(
                code=code,
                message=str(error),
                raw_record_hash=raw_hash,
                source_record_id=str(record_id) if record_id is not None else None,
            ),
        )

    diagnostics: list[NormalizationDiagnostic] = []
    capture_time: datetime | None = None
    capture_timezone: str | None = None
    if record.capture_timestamp is not None:
        try:
            capture_time, capture_timezone = _timestamp(
                record.capture_timestamp,
                record.capture_timezone or context.source_timezone,
            )
        except (ValueError, ZoneInfoNotFoundError) as error:
            diagnostic = _diagnostic(
                DiagnosticCode.UNKNOWN_TIMEZONE,
                DiagnosticSeverity.ERROR,
                "capture_timestamp",
                f"Capture timestamp cannot be normalized: {error}.",
                False,
                record.source_record_id,
            )
            return NormalizationResult(
                diagnostics=(diagnostic,),
                rejection=RejectedRecord(
                    code=DiagnosticCode.UNKNOWN_TIMEZONE,
                    message="Capture timestamp timezone is unknown or invalid.",
                    raw_record_hash=raw_hash,
                    source_record_id=record.source_record_id,
                ),
            )

    provider_time: datetime | None = None
    provider_timezone: str | None = None
    if record.provider_timestamp is not None:
        try:
            provider_time, provider_timezone = _timestamp(
                record.provider_timestamp,
                record.provider_timezone or context.source_timezone,
            )
        except (ValueError, ZoneInfoNotFoundError) as error:
            diagnostic = _diagnostic(
                DiagnosticCode.UNKNOWN_TIMEZONE,
                DiagnosticSeverity.ERROR,
                "provider_timestamp",
                f"Provider timestamp cannot be normalized: {error}.",
                False,
                record.source_record_id,
            )
            return NormalizationResult(
                diagnostics=(diagnostic,),
                rejection=RejectedRecord(
                    code=DiagnosticCode.UNKNOWN_TIMEZONE,
                    message="Provider timestamp timezone is unknown or invalid.",
                    raw_record_hash=raw_hash,
                    source_record_id=record.source_record_id,
                ),
            )

    timestamp_missing = provider_time is None
    if provider_time is not None:
        effective_time = provider_time
        effective_basis = "PROVIDER_TIMESTAMP"
    elif capture_time is not None:
        effective_time = capture_time
        effective_basis = "CAPTURE_TIME_UNCERTAIN_PLACEHOLDER"
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.FINVIZ_CAPTURE_TIME_PLACEHOLDER,
                DiagnosticSeverity.WARNING,
                "provider_timestamp",
                "Provider timestamp is absent; capture time is only an uncertain effective-time placeholder and is not provider publication time.",
                True,
                record.source_record_id,
            )
        )
    else:
        effective_time = context.ingested_at
        effective_basis = "INGESTION_TIME_UNCERTAIN_PLACEHOLDER"
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.FINVIZ_MISSING_TIMESTAMP,
                DiagnosticSeverity.WARNING,
                "provider_timestamp",
                "Provider and capture timestamps are absent; ingestion time is only an uncertain effective-time placeholder.",
                True,
                record.source_record_id,
            )
        )

    invalid_fields: list[str] = []
    approximate_fields: list[str] = []

    def parsed(field: str, parser: Callable[[], Any]) -> Any:
        try:
            return parser()
        except FinvizParseError as error:
            invalid_fields.append(field)
            diagnostics.append(
                _diagnostic(
                    error.code,
                    DiagnosticSeverity.ERROR,
                    field,
                    str(error),
                    True,
                    record.source_record_id,
                )
            )
            return None

    def quantity(field: str, value: Any) -> int | None:
        result: ParsedQuantity | None = parsed(field, lambda: parse_quantity(value))
        if result is None:
            return None
        if result.approximate:
            approximate_fields.append(field)
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.FINVIZ_APPROXIMATE_QUANTITY,
                    DiagnosticSeverity.WARNING,
                    field,
                    "Abbreviated decimal quantity is provider-formatted and treated as estimated precision.",
                    True,
                    record.source_record_id,
                )
            )
        return result.value

    last_price = parsed("price", lambda: parse_price(record.price))
    if last_price == 0:
        invalid_fields.append("price")
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.FINVIZ_ZERO_PRICE,
                DiagnosticSeverity.ERROR,
                "price",
                "Provider explicitly supplied zero price; value is preserved but invalid for this snapshot.",
                True,
                record.source_record_id,
            )
        )
    previous_close = parsed("previous_close", lambda: parse_price(record.previous_close))
    change_percent = parsed(
        "change_percent",
        lambda: parse_percentage(
            record.change_percent, record.change_percent_unit, allow_negative=True
        ),
    )
    volume = quantity("volume", record.volume)
    average_volume = quantity("average_volume", record.average_volume)
    relative_volume = parsed("relative_volume", lambda: parse_ratio(record.relative_volume))
    if relative_volume is not None:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.FINVIZ_RELATIVE_VOLUME_REFERENCE_UNKNOWN,
                DiagnosticSeverity.INFO,
                "relative_volume",
                "Relative volume is provider-published; its reference period is provider-defined or unknown and was not recalculated.",
                True,
                record.source_record_id,
            )
        )
    float_shares = quantity("float_shares", record.float_shares)
    shares_outstanding = quantity("shares_outstanding", record.shares_outstanding)
    short_float_percent = parsed(
        "short_float_percent",
        lambda: parse_percentage(
            record.short_float_percent, record.short_float_percent_unit
        ),
    )
    short_ratio_days = parsed(
        "short_ratio_days", lambda: parse_ratio(record.short_ratio_days)
    )
    market_cap = quantity("market_cap", record.market_cap)
    earnings = parsed("earnings", lambda: parse_earnings(record.earnings))
    if earnings is not None and earnings.earnings_date is not None:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.FINVIZ_DATE_ONLY_EARNINGS,
                DiagnosticSeverity.INFO,
                "earnings",
                "Earnings is retained as a date and session qualifier; no timestamp or timezone was invented.",
                True,
                record.source_record_id,
            )
        )

    payload = MarketSnapshotPayload(
        last_price=last_price,
        previous_close=previous_close,
        change_percent=change_percent,
        volume=volume,
        average_volume=average_volume,
        relative_volume=relative_volume,
        float_shares=float_shares,
        shares_outstanding=shares_outstanding,
        short_float_percent=short_float_percent,
        short_ratio_days=short_ratio_days,
        market_cap=market_cap,
        sector=record.sector,
        industry=record.industry,
        country=record.country,
        exchange=record.exchange,
        earnings_date=None if earnings is None else earnings.earnings_date,
        earnings_session=None if earnings is None else earnings.session,
        snapshot_scope=SNAPSHOT_SCOPE,
    )
    payload_values = payload.model_dump(mode="python")
    descriptive_fields = [key for key in payload_values if key != "snapshot_scope"]
    partial = any(payload_values[key] is None for key in descriptive_fields)
    if invalid_fields:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.FINVIZ_PARTIAL_RECORD,
                DiagnosticSeverity.WARNING,
                None,
                "Usable descriptive fields were normalized; invalid fields were not defaulted.",
                True,
                record.source_record_id,
            )
        )

    delayed = record.delay_status is DelayStatus.KNOWN_DELAYED
    if invalid_fields:
        quality = Quality(
            state=QualityState.INVALID,
            reasons=tuple(f"invalid provider field: {field}" for field in sorted(set(invalid_fields))),
            evaluated_at=context.ingested_at,
            completeness=Completeness.PARTIAL,
        )
    elif timestamp_missing:
        quality = Quality(
            state=QualityState.MISSING,
            reasons=("provider timestamp is missing",),
            evaluated_at=context.ingested_at,
            completeness=Completeness.PARTIAL,
        )
    elif approximate_fields:
        quality = Quality(
            state=QualityState.ESTIMATED,
            reasons=("one or more abbreviated provider quantities have estimated precision",),
            evaluated_at=context.ingested_at,
            completeness=Completeness.PARTIAL if partial else Completeness.COMPLETE,
        )
    elif delayed:
        quality = Quality(
            state=QualityState.DELAYED,
            reasons=("provider record is marked as delayed",),
            evaluated_at=context.ingested_at,
            expected_delay_ms=context.expected_delay_ms,
            completeness=Completeness.PARTIAL if partial else Completeness.COMPLETE,
        )
    else:
        quality = Quality(
            state=QualityState.KNOWN_VALUE,
            evaluated_at=context.ingested_at,
            completeness=Completeness.PARTIAL if partial else Completeness.COMPLETE,
        )

    freshness = (
        DataFreshness.DELAYED
        if delayed
        else DataFreshness.HISTORICAL
        if record.delay_status is DelayStatus.HISTORICAL
        else DataFreshness.UNKNOWN
    )
    provider_metadata = {
        "adapter_version": context.adapter_version,
        "normalization_version": context.normalization_version,
        "source_endpoint_name": context.source_endpoint_name,
        "source_record_id": record.source_record_id,
        "fixture_origin": record.fixture_origin,
        "delay_status": record.delay_status,
        "capture_timestamp": record.capture_timestamp,
        "capture_timestamp_utc": None if capture_time is None else canonicalize(capture_time),
        "capture_timezone": capture_timezone,
        "effective_time_basis": effective_basis,
        "screener_name": record.screener_name,
        "applied_filters": record.applied_filters,
        "change_percent_unit": record.change_percent_unit,
        "short_float_percent_unit": record.short_float_percent_unit,
        "approximate_quantity_fields": tuple(sorted(approximate_fields)),
    }
    observation = Observation(
        schema_version="1.0.0",
        event_type=EventType.MARKET_SNAPSHOT,
        symbol=record.symbol,
        asset_class=AssetClass.EQUITY,
        source=PROVIDER_SOURCE,
        source_record_id=f"{record.source_record_id}:market_snapshot",
        source_timestamp=effective_time,
        received_timestamp=context.ingested_at,
        effective_timestamp=effective_time,
        market_session=MarketSession.UNKNOWN,
        data_freshness=freshness,
        observation_kind=ObservationKind.PROVIDER_PUBLISHED,
        quality=quality,
        payload_type=PayloadType.MARKET_SNAPSHOT,
        payload=payload,
        provenance=Provenance(
            provider=context.provider,
            ingestion_method=context.collection_method,
            origin_kind=ObservationKind.PROVIDER_PUBLISHED,
            normalized=True,
            normalization_version=context.normalization_version,
            completeness=Completeness.PARTIAL if partial else Completeness.COMPLETE,
            units_modified=bool(approximate_fields)
            or record.change_percent_unit is PercentageUnit.DECIMAL_FRACTION
            or record.short_float_percent_unit is PercentageUnit.DECIMAL_FRACTION,
            naming_modified=True,
            entitlement_state=context.entitlement_status,
            source_timezone=provider_timezone if provider_time is not None else None,
            source_timestamp_representation=record.provider_timestamp,
            provider_metadata=provider_metadata,
        ),
        sequence_number=0,
        exchange=record.exchange,
        currency="USD",
        timezone=provider_timezone if provider_time is not None else None,
        raw_payload_hash=raw_hash,
        normalization_version=context.normalization_version,
    )
    return NormalizationResult(observations=(observation,), diagnostics=tuple(diagnostics))


def normalize_finviz_snapshot_records(
    provider_records: Iterable[FinvizSnapshotRecord | Mapping[str, Any]],
    context: AdapterContext,
) -> NormalizationResult:
    observations: list[Observation] = []
    diagnostics: list[NormalizationDiagnostic] = []
    seen_ids: set[str] = set()
    seen_hashes: set[str] = set()
    first_rejection: RejectedRecord | None = None

    for provider_record in provider_records:
        raw_hash = canonical_hash(provider_record)
        record_id = (
            provider_record.source_record_id
            if isinstance(provider_record, FinvizSnapshotRecord)
            else provider_record.get("source_record_id")
        )
        if raw_hash in seen_hashes or (record_id is not None and str(record_id) in seen_ids):
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.FINVIZ_DUPLICATE_RECORD,
                    DiagnosticSeverity.WARNING,
                    "source_record_id",
                    "Duplicate Finviz-shaped provider record was not emitted twice.",
                    True,
                    str(record_id) if record_id is not None else None,
                )
            )
            continue
        seen_hashes.add(raw_hash)
        if record_id is not None:
            seen_ids.add(str(record_id))
        result = normalize_finviz_snapshot_record(provider_record, context)
        observations.extend(result.observations)
        diagnostics.extend(result.diagnostics)
        if result.rejection is not None and first_rejection is None:
            first_rejection = result.rejection

    grouped: dict[tuple[str | None, datetime], list[int]] = {}
    for index, observation in enumerate(observations):
        grouped.setdefault((observation.symbol, observation.effective_timestamp), []).append(index)
    for key, indexes in grouped.items():
        if len({canonical_hash(observations[index].payload) for index in indexes}) <= 1:
            continue
        correlation_id = f"finviz-conflict-{canonical_hash([str(part) for part in key])[:16]}"
        for index in indexes:
            current = observations[index]
            observations[index] = current.model_copy(
                update={
                    "quality": Quality(
                        state=QualityState.CONFLICTED,
                        reasons=("provider snapshots conflict at the same symbol and effective time",),
                        evaluated_at=context.ingested_at,
                    ),
                    "correlation_id": correlation_id,
                }
            )
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.FINVIZ_CONFLICTING_RECORD,
                DiagnosticSeverity.ERROR,
                "market_snapshot",
                "Conflicting Finviz-shaped snapshots were preserved; no winner was selected.",
                True,
                None,
            )
        )

    observations.sort(
        key=lambda item: (
            item.effective_timestamp,
            item.source_timestamp,
            item.sequence_number is None,
            item.sequence_number or 0,
            item.observation_id,
        )
    )
    if not observations and first_rejection is not None:
        return NormalizationResult(diagnostics=tuple(diagnostics), rejection=first_rejection)
    return NormalizationResult(observations=tuple(observations), diagnostics=tuple(diagnostics))
