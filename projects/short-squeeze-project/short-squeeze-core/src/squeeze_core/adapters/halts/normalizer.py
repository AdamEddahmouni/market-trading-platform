from collections.abc import Iterable, Mapping
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
    MarketSession,
    Observation,
    ObservationKind,
    PayloadType,
    Provenance,
    Quality,
    QualityState,
    TradingHaltPayload,
)
from squeeze_core.replay.engine import observation_order_key
from squeeze_core.serialization import canonical_hash

from .models import TradingHaltRecord
from .parsing import (
    HaltParseError,
    HaltTimestamp,
    halt_event_key,
    parse_halt_code,
    parse_halt_timestamp,
    parse_public_availability,
    parse_session_date,
)
from .semantics import (
    HaltLifecycleStatus,
    HaltRevisionStatus,
    KNOWN_HALT_CODES,
    PROVIDER_SOURCE,
)
from .validation import structural_diagnostic_code


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
    diagnostics: Iterable[NormalizationDiagnostic],
) -> tuple[NormalizationDiagnostic, ...]:
    return tuple(
        sorted(
            diagnostics,
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


def _parse_optional_time(
    record: TradingHaltRecord,
    field: str,
    session_date,
) -> HaltTimestamp | None:
    return parse_halt_timestamp(
        getattr(record, field),
        session_date=session_date,
        timezone_name=record.timezone,
        field=field,
    )


_STATUS_DIAGNOSTIC = {
    HaltLifecycleStatus.QUOTE_RESUMPTION_SCHEDULED: DiagnosticCode.HALT_QUOTE_RESUMPTION_SCHEDULED,
    HaltLifecycleStatus.QUOTE_RESUMED: DiagnosticCode.HALT_QUOTE_RESUMED,
    HaltLifecycleStatus.TRADE_RESUMPTION_SCHEDULED: DiagnosticCode.HALT_TRADE_RESUMPTION_SCHEDULED,
    HaltLifecycleStatus.TRADING_RESUMED: DiagnosticCode.HALT_TRADING_RESUMED,
    HaltLifecycleStatus.HALT_CANCELLED: DiagnosticCode.HALT_RESUMPTION_CANCELLED,
    HaltLifecycleStatus.HALT_UPDATED: DiagnosticCode.HALT_RESUMPTION_CHANGED,
}


_STATUS_TIME_FIELD = {
    HaltLifecycleStatus.QUOTE_RESUMPTION_SCHEDULED: "quote_resumption_scheduled_at",
    HaltLifecycleStatus.QUOTE_RESUMED: "quote_resumed_at",
    HaltLifecycleStatus.TRADE_RESUMPTION_SCHEDULED: "trade_resumption_scheduled_at",
    HaltLifecycleStatus.TRADING_RESUMED: "trading_resumed_at",
}


def normalize_trading_halt_record(
    provider_record: TradingHaltRecord | Mapping[str, Any],
    context: AdapterContext,
) -> NormalizationResult:
    raw_hash = canonical_hash(provider_record)
    try:
        record = (
            provider_record
            if isinstance(provider_record, TradingHaltRecord)
            else TradingHaltRecord.model_validate(provider_record)
        )
    except ValidationError as error:
        raw = provider_record if isinstance(provider_record, Mapping) else {}
        code = structural_diagnostic_code(raw, error)
        raw_id = raw.get("source_record_id")
        return _rejected(
            code,
            "Trading-halt provider record failed structural validation.",
            raw_hash,
            None if raw_id is None else str(raw_id),
        )

    try:
        session_date = parse_session_date(record.session_date)
        availability = parse_public_availability(
            publication_at=record.publication_at,
            announcement_at=record.announcement_at,
            timezone_name=record.timezone or context.source_timezone,
        )
        halt_code = parse_halt_code(record.halt_code)
        halt_at = _parse_optional_time(record, "halt_at", session_date)
        quote_scheduled = _parse_optional_time(
            record, "quote_resumption_scheduled_at", session_date
        )
        quote_resumed = _parse_optional_time(record, "quote_resumed_at", session_date)
        trade_scheduled = _parse_optional_time(
            record, "trade_resumption_scheduled_at", session_date
        )
        trading_resumed = _parse_optional_time(
            record, "trading_resumed_at", session_date
        )
    except HaltParseError as error:
        return _rejected(error.code, str(error), raw_hash, record.source_record_id)

    diagnostics: list[NormalizationDiagnostic] = []
    missing: list[str] = []
    if record.exchange is None:
        missing.append("exchange")
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.HALT_MISSING_EXCHANGE,
                DiagnosticSeverity.WARNING,
                "exchange",
                "Exchange or market is missing and remains null.",
                True,
                record.source_record_id,
            )
        )
    if halt_code is None:
        missing.append("halt_code")
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.HALT_MISSING_CODE,
                DiagnosticSeverity.WARNING,
                "halt_code",
                "Halt code is missing and remains null.",
                True,
                record.source_record_id,
            )
        )
    elif halt_code not in KNOWN_HALT_CODES:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.HALT_UNKNOWN_CODE,
                DiagnosticSeverity.INFO,
                "halt_code",
                "Halt code is preserved but is not in the fixture-documented known set.",
                True,
                record.source_record_id,
            )
        )
    if not record.reason_text:
        missing.append("reason_text")
    if halt_at is None:
        missing.append("halt_at")
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.HALT_MISSING_EFFECTIVE_TIMESTAMP,
                DiagnosticSeverity.WARNING,
                "halt_at",
                "Halt-effective time is missing and remains null.",
                True,
                record.source_record_id,
            )
        )

    lifecycle_code = _STATUS_DIAGNOSTIC.get(record.status)
    if lifecycle_code is not None:
        diagnostics.append(
            _diagnostic(
                lifecycle_code,
                DiagnosticSeverity.INFO,
                _STATUS_TIME_FIELD.get(record.status),
                f"Objective halt lifecycle status is {record.status.value}.",
                True,
                record.source_record_id,
            )
        )
    expected_time_field = _STATUS_TIME_FIELD.get(record.status)
    if expected_time_field is not None and getattr(record, expected_time_field) is None:
        missing.append(expected_time_field)
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.HALT_MISSING_RESUMPTION_TIME,
                DiagnosticSeverity.WARNING,
                expected_time_field,
                "Lifecycle status lacks its corresponding resumption time.",
                True,
                record.source_record_id,
            )
        )
    if record.status is HaltLifecycleStatus.HALT_ACTIVE and not any(
        (quote_scheduled, quote_resumed, trade_scheduled, trading_resumed)
    ):
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.HALT_INDEFINITE,
                DiagnosticSeverity.INFO,
                None,
                "No resumption time is known; the halt remains indefinite in this record.",
                True,
                record.source_record_id,
            )
        )
    if record.revision_status is not HaltRevisionStatus.ORIGINAL:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.HALT_REVISION_RECORD,
                DiagnosticSeverity.INFO,
                "revision_status",
                "Lifecycle update is preserved as an immutable observation.",
                True,
                record.source_record_id,
            )
        )
        if not record.supersedes_source_record_id:
            missing.append("supersedes_source_record_id")
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.HALT_REVISION_LINK_MISSING,
                    DiagnosticSeverity.WARNING,
                    "supersedes_source_record_id",
                    "Revision does not identify its prior provider record.",
                    True,
                    record.source_record_id,
                )
            )
    if context.ingested_at < availability.timestamp:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.HALT_RECEIVED_BEFORE_PUBLICATION,
                DiagnosticSeverity.WARNING,
                "received_timestamp",
                "Receipt precedes claimed public availability; effective time waits for publication.",
                True,
                record.source_record_id,
            )
        )

    partial = bool(missing)
    if partial:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.HALT_PARTIAL_RECORD,
                DiagnosticSeverity.WARNING,
                None,
                "Record was normalized only where halt metadata was defensible.",
                True,
                record.source_record_id,
            )
        )
        quality = Quality(
            state=QualityState.MISSING,
            reasons=tuple(f"missing {field}" for field in sorted(set(missing))),
            evaluated_at=context.ingested_at,
            completeness=Completeness.PARTIAL,
        )
    else:
        quality = Quality(
            state=QualityState.KNOWN_VALUE,
            evaluated_at=context.ingested_at,
            completeness=Completeness.COMPLETE,
        )

    event_key = halt_event_key(
        symbol=record.symbol,
        exchange=record.exchange,
        provider_halt_id=record.provider_halt_id,
        session_date=session_date,
        halt_at=None if halt_at is None else halt_at.timestamp,
    )
    time_values = {
        "quote_resumption_scheduled_at": quote_scheduled,
        "quote_resumed_at": quote_resumed,
        "trade_resumption_scheduled_at": trade_scheduled,
        "trading_resumed_at": trading_resumed,
    }
    metadata = {
        "adapter_version": context.adapter_version,
        "normalization_version": context.normalization_version,
        "fixture_origin": record.fixture_origin,
        "provider_halt_id": record.provider_halt_id,
        "provider_record_id": record.provider_record_id,
        "halt_event_key": event_key,
        "halt_code": halt_code,
        "halt_code_status": (
            "MISSING"
            if halt_code is None
            else "KNOWN"
            if halt_code in KNOWN_HALT_CODES
            else "UNKNOWN"
        ),
        "announcement_timestamp_representation": record.announcement_at,
        "publication_timestamp_representation": record.publication_at,
        "public_availability_basis": availability.basis,
        "halt_timestamp_representation": record.halt_at,
        "halt_at": None if halt_at is None else halt_at.timestamp,
        "session_date": None if session_date is None else session_date.isoformat(),
        "status": record.status,
        "revision_status": record.revision_status,
        "revision_number": record.revision_number,
        "supersedes_source_record_id": record.supersedes_source_record_id,
        "capture_timestamp_representation": record.capture_timestamp,
        "provider_metadata": record.provider_metadata,
        **{
            field: None if value is None else value.timestamp
            for field, value in time_values.items()
        },
        **{
            f"{field}_representation": getattr(record, field)
            for field in time_values
        },
    }
    actual_resume = trading_resumed or quote_resumed
    observation = Observation(
        schema_version="1.0.0",
        event_type=EventType.TRADING_HALT,
        symbol=record.symbol,
        asset_class=AssetClass.EQUITY,
        source=PROVIDER_SOURCE,
        source_record_id=record.source_record_id,
        source_timestamp=availability.timestamp,
        received_timestamp=context.ingested_at,
        effective_timestamp=max(availability.timestamp, context.ingested_at),
        market_session=MarketSession.UNKNOWN,
        data_freshness=DataFreshness.HISTORICAL,
        observation_kind=ObservationKind.PROVIDER_PUBLISHED,
        quality=quality,
        payload_type=PayloadType.TRADING_HALT,
        payload=TradingHaltPayload(
            halt_status=record.status.value,
            halt_reason=record.reason_text,
            halt_time=None if halt_at is None else halt_at.timestamp,
            resume_time=None if actual_resume is None else actual_resume.timestamp,
        ),
        provenance=Provenance(
            provider=context.provider,
            ingestion_method=context.collection_method,
            origin_kind=ObservationKind.PROVIDER_PUBLISHED,
            normalized=True,
            normalization_version=context.normalization_version,
            completeness=Completeness.PARTIAL if partial else Completeness.COMPLETE,
            naming_modified=True,
            entitlement_state=context.entitlement_status,
            source_timezone=availability.timezone_label,
            source_timestamp_representation=availability.representation,
            provider_metadata=metadata,
        ),
        exchange=record.exchange,
        timezone=availability.timezone_label,
        raw_payload_hash=raw_hash,
        normalization_version=context.normalization_version,
    )
    return NormalizationResult(
        observations=(observation,), diagnostics=_sorted_diagnostics(diagnostics)
    )


def normalize_trading_halt_records(
    provider_records: Iterable[TradingHaltRecord | Mapping[str, Any]],
    context: AdapterContext,
) -> NormalizationResult:
    observations: list[Observation] = []
    diagnostics: list[NormalizationDiagnostic] = []
    seen_hashes: set[str] = set()
    first_rejection: RejectedRecord | None = None

    for raw in provider_records:
        raw_hash = canonical_hash(raw)
        source_value = (
            raw.source_record_id
            if isinstance(raw, TradingHaltRecord)
            else raw.get("source_record_id")
        )
        source_id = None if source_value is None else str(source_value)
        if raw_hash in seen_hashes:
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.HALT_DUPLICATE_RECORD,
                    DiagnosticSeverity.WARNING,
                    "source_record_id",
                    "Exact duplicate halt record was emitted only once.",
                    True,
                    source_id,
                )
            )
            continue
        seen_hashes.add(raw_hash)
        result = normalize_trading_halt_record(raw, context)
        observations.extend(result.observations)
        diagnostics.extend(result.diagnostics)
        if result.rejection is not None and first_rejection is None:
            first_rejection = result.rejection

    first_by_source_id: dict[str, Observation] = {}
    for index, observation in enumerate(tuple(observations)):
        supersedes = observation.provenance.provider_metadata.get(
            "supersedes_source_record_id"
        )
        if supersedes:
            prior = first_by_source_id.get(str(supersedes))
            if prior is None:
                diagnostics.append(
                    _diagnostic(
                        DiagnosticCode.HALT_REVISION_LINK_MISSING,
                        DiagnosticSeverity.WARNING,
                        "supersedes_source_record_id",
                        "Prior halt record was not present in this batch.",
                        True,
                        observation.source_record_id,
                    )
                )
            else:
                correlation_id = (
                    f"halt-revision-{canonical_hash((prior.observation_id, observation.observation_id))[:16]}"
                )
                prior_index = observations.index(prior)
                observations[prior_index] = prior.model_copy(
                    update={"correlation_id": correlation_id}
                )
                observations[index] = observation.model_copy(
                    update={
                        "parent_observation_ids": (prior.observation_id,),
                        "correlation_id": correlation_id,
                    }
                )
                first_by_source_id[prior.source_record_id] = observations[prior_index]
        first_by_source_id.setdefault(
            observation.source_record_id, observations[index]
        )

    grouped: dict[str, list[int]] = {}
    for index, observation in enumerate(observations):
        grouped.setdefault(observation.source_record_id, []).append(index)
    for source_id, indexes in grouped.items():
        if len(indexes) < 2:
            continue
        raw_hashes = {observations[index].raw_payload_hash for index in indexes}
        if len(raw_hashes) == 1:
            continue
        existing_correlation = next(
            (
                observations[index].correlation_id
                for index in indexes
                if observations[index].correlation_id is not None
            ),
            None,
        )
        correlation_id = existing_correlation or f"halt-conflict-{canonical_hash(source_id)[:16]}"
        for index in indexes:
            current = observations[index]
            observations[index] = current.model_copy(
                update={
                    "quality": Quality(
                        state=QualityState.CONFLICTED,
                        reasons=("same provider record ID has conflicting halt metadata",),
                        evaluated_at=context.ingested_at,
                        completeness=current.quality.completeness,
                    ),
                    "correlation_id": correlation_id,
                }
            )
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.HALT_CONFLICTING_RECORD,
                DiagnosticSeverity.ERROR,
                "source_record_id",
                "Conflicting same-ID halt records were preserved; no winner was selected.",
                True,
                source_id,
            )
        )

    observations.sort(key=observation_order_key)
    if not observations and first_rejection is not None:
        return NormalizationResult(
            diagnostics=_sorted_diagnostics(diagnostics), rejection=first_rejection
        )
    return NormalizationResult(
        observations=tuple(observations), diagnostics=_sorted_diagnostics(diagnostics)
    )
