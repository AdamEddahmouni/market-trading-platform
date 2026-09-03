from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime, time, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
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
    BorrowAvailabilityPayload,
    BorrowFeePayload,
    Completeness,
    DataFreshness,
    EventType,
    MarketSession,
    Observation,
    ObservationKind,
    PayloadType,
    Quality,
    QualityState,
    Provenance,
)
from squeeze_core.serialization import canonical_hash

from .models import IbkrBorrowRecord
from .semantics import DelayStatus, FEE_TYPE, PROVIDER_SOURCE, PercentUnit


def _diagnostic(
    code: DiagnosticCode,
    severity: DiagnosticSeverity,
    field: str | None,
    message: str,
    continued: bool,
    record_id: str | None,
) -> NormalizationDiagnostic:
    context = {} if record_id is None else {"source_record_id": record_id}
    return NormalizationDiagnostic(
        code=code,
        severity=severity,
        field=field,
        message=message,
        normalization_continued=continued,
        context=context,
    )


def _decimal(value: Any) -> Decimal:
    if isinstance(value, bool):
        raise InvalidOperation
    converted = Decimal(str(value))
    if not converted.is_finite():
        raise InvalidOperation
    return converted


def _nonnegative_integer(value: Any) -> int:
    converted = _decimal(value)
    if converted < 0 or converted != converted.to_integral_value():
        raise InvalidOperation
    return int(converted)


def _timezone(value: str):
    if value == "UTC":
        return UTC
    if len(value) == 6 and value[0] in "+-" and value[3] == ":":
        hours = int(value[1:3])
        minutes = int(value[4:6])
        if hours > 23 or minutes > 59:
            raise ValueError("invalid UTC offset")
        offset = timedelta(hours=hours, minutes=minutes)
        if value[0] == "-":
            offset = -offset
        return timezone(offset)
    return ZoneInfo(value)


def _timestamp(
    record: IbkrBorrowRecord,
    context: AdapterContext,
) -> tuple[datetime | None, str | None, list[NormalizationDiagnostic]]:
    diagnostics: list[NormalizationDiagnostic] = []
    raw = record.provider_timestamp
    if raw is None:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.MISSING_PROVIDER_TIMESTAMP,
                DiagnosticSeverity.WARNING,
                "provider_timestamp",
                "Provider timestamp is absent; ingestion time is used only as an uncertain placeholder.",
                True,
                record.source_record_id,
            )
        )
        return context.ingested_at, None, diagnostics

    try:
        if len(raw) == 10:
            parsed_date = date.fromisoformat(raw)
            timezone_name = record.provider_timezone or context.source_timezone
            if timezone_name is None:
                raise ZoneInfoNotFoundError("timezone is absent")
            parsed = datetime.combine(parsed_date, time.min, tzinfo=_timezone(timezone_name))
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.DATE_ONLY_PROVIDER_TIMESTAMP,
                    DiagnosticSeverity.WARNING,
                    "provider_timestamp",
                    "Date-only provider observation is normalized to start-of-day in the supplied timezone.",
                    True,
                    record.source_record_id,
                )
            )
            return parsed.astimezone(UTC), timezone_name, diagnostics

        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            timezone_name = record.provider_timezone or context.source_timezone
            if timezone_name is None:
                raise ZoneInfoNotFoundError("timezone is absent")
            parsed = parsed.replace(tzinfo=_timezone(timezone_name))
            return parsed.astimezone(UTC), timezone_name, diagnostics
        return parsed.astimezone(UTC), record.provider_timezone or "EMBEDDED_OFFSET", diagnostics
    except (ValueError, ZoneInfoNotFoundError) as error:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.UNKNOWN_TIMEZONE,
                DiagnosticSeverity.ERROR,
                "provider_timestamp",
                f"Provider timestamp cannot be normalized without a valid explicit timezone: {error}.",
                False,
                record.source_record_id,
            )
        )
        return None, None, diagnostics


def _quality(
    *,
    value_missing: bool,
    timestamp_missing: bool,
    delayed: bool,
    context: AdapterContext,
    missing_reason: str,
) -> Quality:
    if timestamp_missing:
        return Quality(
            state=QualityState.MISSING,
            reasons=("provider timestamp is missing",),
            evaluated_at=context.ingested_at,
            expected_delay_ms=context.expected_delay_ms,
            completeness=Completeness.PARTIAL,
        )
    if value_missing:
        return Quality(
            state=QualityState.MISSING,
            reasons=(missing_reason,),
            evaluated_at=context.ingested_at,
            expected_delay_ms=context.expected_delay_ms,
            completeness=Completeness.PARTIAL,
        )
    if delayed:
        return Quality(
            state=QualityState.DELAYED,
            reasons=("provider record is marked as delayed",),
            evaluated_at=context.ingested_at,
            expected_delay_ms=context.expected_delay_ms,
        )
    return Quality(state=QualityState.KNOWN_VALUE, evaluated_at=context.ingested_at)


def _provenance(
    record: IbkrBorrowRecord,
    context: AdapterContext,
    *,
    source_timezone: str | None,
    units_modified: bool,
    complete: bool,
) -> Provenance:
    return Provenance(
        provider=context.provider,
        ingestion_method=context.collection_method,
        origin_kind=ObservationKind.PROVIDER_PUBLISHED,
        normalized=True,
        normalization_version=context.normalization_version,
        completeness=Completeness.COMPLETE if complete else Completeness.PARTIAL,
        units_modified=units_modified,
        naming_modified=True,
        entitlement_state=context.entitlement_status,
        source_timezone=source_timezone,
        source_timestamp_representation=record.provider_timestamp,
        provider_metadata={
            "adapter_version": context.adapter_version,
            "normalization_version": context.normalization_version,
            "source_endpoint_name": context.source_endpoint_name,
            "source_record_id": record.source_record_id,
            "delay_status": record.delay_status,
            "fee_input_unit": record.fee_rate_unit,
        },
    )


def _observation(
    record: IbkrBorrowRecord,
    context: AdapterContext,
    *,
    raw_hash: str,
    source_timestamp: datetime,
    source_timezone: str | None,
    event_type: EventType,
    payload_type: PayloadType,
    payload: BorrowFeePayload | BorrowAvailabilityPayload,
    quality: Quality,
    sequence_number: int,
    units_modified: bool = False,
) -> Observation:
    delayed = record.delay_status == DelayStatus.KNOWN_DELAYED
    return Observation(
        schema_version="1.0.0",
        event_type=event_type,
        symbol=record.symbol,
        asset_class=AssetClass.EQUITY,
        source=PROVIDER_SOURCE,
        source_record_id=f"{record.source_record_id}:{payload_type.value}",
        source_timestamp=source_timestamp,
        received_timestamp=context.ingested_at,
        effective_timestamp=source_timestamp,
        market_session=MarketSession.UNKNOWN,
        data_freshness=DataFreshness.DELAYED if delayed else DataFreshness.UNKNOWN,
        observation_kind=ObservationKind.PROVIDER_PUBLISHED,
        quality=quality,
        payload_type=payload_type,
        payload=payload,
        provenance=_provenance(
            record,
            context,
            source_timezone=source_timezone,
            units_modified=units_modified,
            complete=quality.state in (QualityState.KNOWN_VALUE, QualityState.DELAYED),
        ),
        sequence_number=sequence_number,
        currency="USD",
        timezone=source_timezone,
        raw_payload_hash=raw_hash,
        normalization_version=context.normalization_version,
    )


def normalize_ibkr_borrow_record(
    provider_record: IbkrBorrowRecord | Mapping[str, Any],
    context: AdapterContext,
) -> NormalizationResult:
    raw_hash = canonical_hash(provider_record)
    try:
        record = (
            provider_record
            if isinstance(provider_record, IbkrBorrowRecord)
            else IbkrBorrowRecord.model_validate(provider_record)
        )
    except ValidationError as error:
        diagnostic = _diagnostic(
            DiagnosticCode.INVALID_NUMERIC_VALUE,
            DiagnosticSeverity.ERROR,
            None,
            "Provider record failed structural validation.",
            False,
            provider_record.get("source_record_id") if isinstance(provider_record, Mapping) else None,
        )
        return NormalizationResult(
            diagnostics=(diagnostic,),
            rejection=RejectedRecord(
                code=DiagnosticCode.INVALID_NUMERIC_VALUE,
                message=str(error),
                raw_record_hash=raw_hash,
                source_record_id=diagnostic.context.get("source_record_id"),
            ),
        )

    source_timestamp, source_timezone, diagnostics = _timestamp(record, context)
    if source_timestamp is None:
        return NormalizationResult(
            diagnostics=tuple(diagnostics),
            rejection=RejectedRecord(
                code=DiagnosticCode.UNKNOWN_TIMEZONE,
                message="Provider timestamp timezone is unknown or invalid.",
                raw_record_hash=raw_hash,
                source_record_id=record.source_record_id,
            ),
        )

    if context.entitlement_status.value == "UNKNOWN":
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.ENTITLEMENT_UNKNOWN,
                DiagnosticSeverity.WARNING,
                "entitlement_status",
                "Provider entitlement status is unknown.",
                True,
                record.source_record_id,
            )
        )
    if record.delay_status == DelayStatus.UNKNOWN:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.DELAY_STATUS_UNKNOWN,
                DiagnosticSeverity.WARNING,
                "delay_status",
                "Provider delay status is unknown.",
                True,
                record.source_record_id,
            )
        )

    timestamp_missing = record.provider_timestamp is None
    delayed = record.delay_status == DelayStatus.KNOWN_DELAYED
    observations: list[Observation] = []

    fee: Decimal | None = None
    fee_valid = True
    units_modified = False
    if record.fee_rate is None:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.MISSING_BORROW_FEE,
                DiagnosticSeverity.WARNING,
                "fee_rate",
                "Borrow fee is missing and remains null.",
                True,
                record.source_record_id,
            )
        )
    elif record.fee_rate_unit not in (PercentUnit.PERCENT_POINTS, PercentUnit.DECIMAL_FRACTION):
        fee_valid = False
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.UNSUPPORTED_PERCENT_UNIT,
                DiagnosticSeverity.ERROR,
                "fee_rate_unit",
                "Borrow fee unit must be PERCENT_POINTS or DECIMAL_FRACTION.",
                True,
                record.source_record_id,
            )
        )
    else:
        try:
            fee = _decimal(record.fee_rate)
            if fee < 0:
                raise InvalidOperation
            if record.fee_rate_unit == PercentUnit.DECIMAL_FRACTION:
                fee *= Decimal("100")
                units_modified = True
            if fee == 0:
                diagnostics.append(
                    _diagnostic(
                        DiagnosticCode.EXPLICIT_ZERO_BORROW_FEE,
                        DiagnosticSeverity.INFO,
                        "fee_rate",
                        "Provider explicitly reported a zero borrow fee.",
                        True,
                        record.source_record_id,
                    )
                )
        except (InvalidOperation, ValueError):
            fee_valid = False
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.INVALID_NUMERIC_VALUE,
                    DiagnosticSeverity.ERROR,
                    "fee_rate",
                    "Borrow fee must be a finite nonnegative numeric value.",
                    True,
                    record.source_record_id,
                )
            )

    if fee_valid:
        observations.append(
            _observation(
                record,
                context,
                raw_hash=raw_hash,
                source_timestamp=source_timestamp,
                source_timezone=source_timezone,
                event_type=EventType.BORROW_FEE,
                payload_type=PayloadType.BORROW_FEE,
                payload=BorrowFeePayload(annualized_fee_percent=fee, fee_type=FEE_TYPE),
                quality=_quality(
                    value_missing=fee is None,
                    timestamp_missing=timestamp_missing,
                    delayed=delayed,
                    context=context,
                    missing_reason="provider omitted borrow fee",
                ),
                sequence_number=0,
                units_modified=units_modified,
            )
        )

    available: int | None = None
    lender_count: int | None = None
    availability_valid = True
    if record.available_shares is None:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.MISSING_AVAILABLE_SHARES,
                DiagnosticSeverity.WARNING,
                "available_shares",
                "Available shares are missing and remain null.",
                True,
                record.source_record_id,
            )
        )
    else:
        try:
            available = _nonnegative_integer(record.available_shares)
            if available == 0:
                diagnostics.append(
                    _diagnostic(
                        DiagnosticCode.EXPLICIT_ZERO_AVAILABLE_SHARES,
                        DiagnosticSeverity.INFO,
                        "available_shares",
                        "Provider explicitly reported zero available shares.",
                        True,
                        record.source_record_id,
                    )
                )
        except (InvalidOperation, ValueError):
            availability_valid = False
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.INVALID_NUMERIC_VALUE,
                    DiagnosticSeverity.ERROR,
                    "available_shares",
                    "Available shares must be a nonnegative whole number.",
                    True,
                    record.source_record_id,
                )
            )
    if record.lender_count is not None:
        try:
            lender_count = _nonnegative_integer(record.lender_count)
        except (InvalidOperation, ValueError):
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.INVALID_NUMERIC_VALUE,
                    DiagnosticSeverity.WARNING,
                    "lender_count",
                    "Lender count must be a nonnegative whole number and was omitted.",
                    True,
                    record.source_record_id,
                )
            )

    if availability_valid:
        observations.append(
            _observation(
                record,
                context,
                raw_hash=raw_hash,
                source_timestamp=source_timestamp,
                source_timezone=source_timezone,
                event_type=EventType.BORROW_AVAILABILITY,
                payload_type=PayloadType.BORROW_AVAILABILITY,
                payload=BorrowAvailabilityPayload(
                    available_shares=available,
                    lender_count=lender_count,
                    hard_to_borrow=record.hard_to_borrow,
                ),
                quality=_quality(
                    value_missing=available is None,
                    timestamp_missing=timestamp_missing,
                    delayed=delayed,
                    context=context,
                    missing_reason="provider omitted available shares",
                ),
                sequence_number=1,
            )
        )

    if len(observations) != 2:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.PARTIAL_RECORD,
                DiagnosticSeverity.WARNING,
                None,
                "Only valid lending fields were normalized; invalid fields were not defaulted.",
                True,
                record.source_record_id,
            )
        )
    return NormalizationResult(observations=tuple(observations), diagnostics=tuple(diagnostics))


def normalize_ibkr_borrow_records(
    provider_records: Iterable[IbkrBorrowRecord | Mapping[str, Any]],
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
            if isinstance(provider_record, IbkrBorrowRecord)
            else provider_record.get("source_record_id")
        )
        if raw_hash in seen_hashes or (record_id is not None and record_id in seen_ids):
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.DUPLICATE_SOURCE_RECORD,
                    DiagnosticSeverity.WARNING,
                    "source_record_id",
                    "Duplicate provider record was not emitted twice.",
                    True,
                    str(record_id) if record_id is not None else None,
                )
            )
            continue
        seen_hashes.add(raw_hash)
        if record_id is not None:
            seen_ids.add(str(record_id))
        result = normalize_ibkr_borrow_record(provider_record, context)
        observations.extend(result.observations)
        diagnostics.extend(result.diagnostics)
        if result.rejection is not None and first_rejection is None:
            first_rejection = result.rejection

    grouped: dict[tuple[EventType, str | None, datetime], list[int]] = {}
    for index, observation in enumerate(observations):
        grouped.setdefault(
            (observation.event_type, observation.symbol, observation.effective_timestamp), []
        ).append(index)
    for key, indexes in grouped.items():
        payload_hashes = {canonical_hash(observations[index].payload) for index in indexes}
        if len(payload_hashes) <= 1:
            continue
        correlation_id = f"ibkr-conflict-{canonical_hash([str(part) for part in key])[:16]}"
        for index in indexes:
            current = observations[index]
            observations[index] = current.model_copy(
                update={
                    "quality": Quality(
                        state=QualityState.CONFLICTED,
                        reasons=("provider records conflict at the same symbol and effective time",),
                        evaluated_at=context.ingested_at,
                    ),
                    "correlation_id": correlation_id,
                }
            )
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.CONFLICTING_SOURCE_RECORD,
                DiagnosticSeverity.ERROR,
                key[0].value,
                "Conflicting records were preserved and marked CONFLICTED; no winner was selected.",
                True,
                None,
            )
        )

    if not observations and first_rejection is not None:
        return NormalizationResult(diagnostics=tuple(diagnostics), rejection=first_rejection)
    return NormalizationResult(observations=tuple(observations), diagnostics=tuple(diagnostics))
