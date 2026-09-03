from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any, Callable

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
    PublishedShortInterestPayload,
    Quality,
    QualityState,
)
from squeeze_core.replay.engine import observation_order_key
from squeeze_core.serialization import canonical_hash

from .models import FinraShortInterestRecord
from .parsing import (
    FinraParseError,
    PublicationAvailability,
    parse_nonnegative_decimal,
    parse_nonnegative_integer,
    parse_percentage,
    parse_publication_availability,
    parse_settlement_date,
    parse_timestamp,
)
from .semantics import (
    DateOnlyPublicationPolicy,
    PercentageUnit,
    PROVIDER_SOURCE,
    RevisionStatus,
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
    *,
    code: DiagnosticCode,
    message: str,
    raw_hash: str,
    record_id: str | None,
    field: str | None = None,
) -> NormalizationResult:
    diagnostic = _diagnostic(
        code,
        DiagnosticSeverity.ERROR,
        field,
        message,
        False,
        record_id,
    )
    return NormalizationResult(
        diagnostics=(diagnostic,),
        rejection=RejectedRecord(
            code=code,
            message=message,
            raw_record_hash=raw_hash,
            source_record_id=record_id,
        ),
    )


def _publication(
    record: FinraShortInterestRecord,
    context: AdapterContext,
    raw_hash: str,
) -> tuple[PublicationAvailability | None, NormalizationResult | None]:
    if record.publication_date is None:
        if record.provider_timestamp_is_publication and record.provider_timestamp:
            try:
                timestamp, label = parse_timestamp(
                    record.provider_timestamp,
                    record.provider_timezone or context.source_timezone,
                    field="publication_date",
                )
            except FinraParseError as error:
                return None, _rejected(
                    code=error.code,
                    message=str(error),
                    raw_hash=raw_hash,
                    record_id=record.source_record_id,
                    field="provider_timestamp",
                )
            return (
                PublicationAvailability(
                    timestamp=timestamp,
                    publication_date=timestamp.date(),
                    uncertain=False,
                    policy=None,
                    timezone_label=label,
                ),
                None,
            )
        code = (
            DiagnosticCode.FINRA_CAPTURE_TIMESTAMP_ONLY
            if record.capture_timestamp is not None
            else DiagnosticCode.FINRA_MISSING_PUBLICATION_DATE
        )
        message = (
            "Capture timestamp alone cannot establish publication availability."
            if record.capture_timestamp is not None
            else "Publication date is missing and no explicit publication timestamp exists."
        )
        return None, _rejected(
            code=code,
            message=message,
            raw_hash=raw_hash,
            record_id=record.source_record_id,
            field="publication_date",
        )
    try:
        return (
            parse_publication_availability(
                record.publication_date,
                timezone_name=record.publication_timezone or context.source_timezone,
                policy=record.date_only_publication_policy,
                received_at=context.ingested_at,
            ),
            None,
        )
    except FinraParseError as error:
        return None, _rejected(
            code=error.code,
            message=str(error),
            raw_hash=raw_hash,
            record_id=record.source_record_id,
            field="publication_date",
        )


def normalize_finra_short_interest_record(
    provider_record: FinraShortInterestRecord | Mapping[str, Any],
    context: AdapterContext,
) -> NormalizationResult:
    raw_hash = canonical_hash(provider_record)
    try:
        record = (
            provider_record
            if isinstance(provider_record, FinraShortInterestRecord)
            else FinraShortInterestRecord.model_validate(provider_record)
        )
    except ValidationError as error:
        raw = provider_record if isinstance(provider_record, Mapping) else {}
        code = structural_diagnostic_code(raw, error)
        record_id_value = raw.get("source_record_id")
        return _rejected(
            code=code,
            message="FINRA-shaped provider record failed structural validation.",
            raw_hash=raw_hash,
            record_id=None if record_id_value is None else str(record_id_value),
        )

    try:
        settlement_date = parse_settlement_date(record.settlement_date)
    except FinraParseError as error:
        return _rejected(
            code=error.code,
            message=str(error),
            raw_hash=raw_hash,
            record_id=record.source_record_id,
            field="settlement_date",
        )

    publication, rejection = _publication(record, context, raw_hash)
    if rejection is not None:
        return rejection
    assert publication is not None

    diagnostics: list[NormalizationDiagnostic] = []
    invalid_fields: list[str] = []
    missing_fields: list[str] = []

    if publication.uncertain:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.FINRA_DATE_ONLY_PUBLICATION,
                DiagnosticSeverity.WARNING,
                "publication_date",
                "Date-only publication used an explicit uncertain availability policy.",
                True,
                record.source_record_id,
            )
        )
    if context.ingested_at < publication.timestamp:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.FINRA_RECEIVED_BEFORE_PUBLICATION,
                DiagnosticSeverity.WARNING,
                "publication_date",
                "Record receipt precedes claimed publication; effective time waits for publication.",
                True,
                record.source_record_id,
            )
        )

    def parsed(
        field: str, value: Any, parser: Callable[[Any], Any], *, missing_code: DiagnosticCode | None = None
    ) -> Any:
        if value is None or value == "":
            missing_fields.append(field)
            if missing_code is not None:
                diagnostics.append(
                    _diagnostic(
                        missing_code,
                        DiagnosticSeverity.WARNING,
                        field,
                        f"{field} is missing and remains null.",
                        True,
                        record.source_record_id,
                    )
                )
            return None
        try:
            return parser(value)
        except FinraParseError as error:
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

    short_shares = parsed(
        "short_shares",
        record.short_shares,
        lambda value: parse_nonnegative_integer(value, "short_shares"),
        missing_code=DiagnosticCode.FINRA_MISSING_SHORT_SHARES,
    )
    float_shares = parsed(
        "float_shares",
        record.float_shares,
        lambda value: parse_nonnegative_integer(value, "float_shares"),
        missing_code=DiagnosticCode.FINRA_MISSING_FLOAT,
    )
    if float_shares == 0:
        invalid_fields.append("float_shares")
        float_shares = None
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.INVALID_NUMERIC_VALUE,
                DiagnosticSeverity.ERROR,
                "float_shares",
                "float_shares must be positive when supplied.",
                True,
                record.source_record_id,
            )
        )
    short_float_percent = parsed(
        "short_float_percent",
        record.short_float_percent,
        lambda value: parse_percentage(value, record.short_float_percent_unit),
    )
    days_to_cover = parsed(
        "days_to_cover",
        record.days_to_cover,
        lambda value: parse_nonnegative_decimal(value, "days_to_cover"),
        missing_code=DiagnosticCode.FINRA_MISSING_DAYS_TO_COVER,
    )
    previous_short_shares = parsed(
        "previous_short_shares",
        record.previous_short_shares,
        lambda value: parse_nonnegative_integer(value, "previous_short_shares"),
    )
    average_daily_volume = parsed(
        "average_daily_volume",
        record.average_daily_volume,
        lambda value: parse_nonnegative_integer(value, "average_daily_volume"),
    )
    if average_daily_volume is not None and record.average_daily_volume_reference is None:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.FINRA_DAYS_TO_COVER_REFERENCE_UNKNOWN,
                DiagnosticSeverity.WARNING,
                "average_daily_volume_reference",
                "Average-volume reference period is unknown; days to cover is not recomputed.",
                True,
                record.source_record_id,
            )
        )

    provider_timestamp_utc: datetime | None = None
    provider_timezone_label: str | None = None
    if record.provider_timestamp is not None:
        try:
            provider_timestamp_utc, provider_timezone_label = parse_timestamp(
                record.provider_timestamp,
                record.provider_timezone or context.source_timezone,
                field="provider_timestamp",
            )
        except FinraParseError as error:
            invalid_fields.append("provider_timestamp")
            diagnostics.append(
                _diagnostic(
                    error.code,
                    DiagnosticSeverity.ERROR,
                    "provider_timestamp",
                    str(error),
                    True,
                    record.source_record_id,
                )
            )
    capture_timestamp_utc: datetime | None = None
    if record.capture_timestamp is not None:
        try:
            capture_timestamp_utc, _ = parse_timestamp(
                record.capture_timestamp,
                record.capture_timezone or context.source_timezone,
                field="capture_timestamp",
            )
        except FinraParseError as error:
            invalid_fields.append("capture_timestamp")
            diagnostics.append(
                _diagnostic(
                    error.code,
                    DiagnosticSeverity.ERROR,
                    "capture_timestamp",
                    str(error),
                    True,
                    record.source_record_id,
                )
            )

    if record.revision_status in {RevisionStatus.CORRECTED, RevisionStatus.REVISED}:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.FINRA_CORRECTED_RECORD,
                DiagnosticSeverity.INFO,
                "revision_status",
                "Revision is preserved as a new immutable observation.",
                True,
                record.source_record_id,
            )
        )

    partial = bool(missing_fields or invalid_fields or publication.uncertain)
    if partial:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.FINRA_PARTIAL_RECORD,
                DiagnosticSeverity.WARNING,
                None,
                "Record was normalized only where field and availability semantics were defensible.",
                True,
                record.source_record_id,
            )
        )

    if record.revision_status is RevisionStatus.CANCELLED:
        quality = Quality(
            state=QualityState.UNAVAILABLE,
            reasons=("provider record is cancelled",),
            evaluated_at=context.ingested_at,
            completeness=Completeness.PARTIAL,
        )
    elif invalid_fields:
        quality = Quality(
            state=QualityState.INVALID,
            reasons=tuple(f"invalid {field}" for field in sorted(set(invalid_fields))),
            evaluated_at=context.ingested_at,
            completeness=Completeness.PARTIAL,
        )
    elif short_shares is None or publication.uncertain:
        reasons = []
        if short_shares is None:
            reasons.append("published short shares are missing")
        if publication.uncertain:
            reasons.append("exact publication time is unknown")
        quality = Quality(
            state=QualityState.MISSING,
            reasons=tuple(reasons),
            evaluated_at=context.ingested_at,
            completeness=Completeness.PARTIAL,
        )
    else:
        quality = Quality(
            state=QualityState.KNOWN_VALUE,
            evaluated_at=context.ingested_at,
            completeness=Completeness.PARTIAL if partial else Completeness.COMPLETE,
        )

    effective_timestamp = max(publication.timestamp, context.ingested_at)
    units_modified = record.short_float_percent_unit is PercentageUnit.DECIMAL_FRACTION
    metadata = {
        "adapter_version": context.adapter_version,
        "normalization_version": context.normalization_version,
        "source_endpoint_name": context.source_endpoint_name,
        "fixture_origin": record.fixture_origin,
        "provider_record_id": record.provider_record_id,
        "provider_timestamp": provider_timestamp_utc,
        "provider_timestamp_representation": record.provider_timestamp,
        "provider_timestamp_timezone": provider_timezone_label,
        "provider_timestamp_is_publication": record.provider_timestamp_is_publication,
        "capture_timestamp": capture_timestamp_utc,
        "capture_timestamp_representation": record.capture_timestamp,
        "publication_availability": publication.timestamp,
        "publication_time_policy": publication.policy,
        "publication_time_uncertain": publication.uncertain,
        "settlement_date": settlement_date,
        "revision_status": record.revision_status,
        "revision_number": record.revision_number,
        "supersedes_source_record_id": record.supersedes_source_record_id,
        "previous_short_shares": previous_short_shares,
        "average_daily_volume": average_daily_volume,
        "average_daily_volume_reference": record.average_daily_volume_reference,
        "market": record.market,
        "exchange": record.exchange,
        "short_float_input_unit": record.short_float_percent_unit,
    }
    observation = Observation(
        schema_version="1.0.0",
        event_type=EventType.PUBLISHED_SHORT_INTEREST,
        symbol=record.symbol,
        asset_class=AssetClass.EQUITY,
        source=PROVIDER_SOURCE,
        source_record_id=record.source_record_id,
        source_timestamp=publication.timestamp,
        received_timestamp=context.ingested_at,
        effective_timestamp=effective_timestamp,
        market_session=MarketSession.UNKNOWN,
        data_freshness=DataFreshness.HISTORICAL,
        observation_kind=ObservationKind.PROVIDER_PUBLISHED,
        quality=quality,
        payload_type=PayloadType.PUBLISHED_SHORT_INTEREST,
        payload=PublishedShortInterestPayload(
            short_shares=short_shares,
            float_shares=float_shares,
            short_float_percent=short_float_percent,
            settlement_date=settlement_date,
            publication_date=publication.publication_date,
            days_to_cover=days_to_cover,
        ),
        provenance=Provenance(
            provider=context.provider,
            ingestion_method=context.collection_method,
            origin_kind=ObservationKind.PROVIDER_PUBLISHED,
            normalized=True,
            normalization_version=context.normalization_version,
            completeness=Completeness.PARTIAL if partial else Completeness.COMPLETE,
            units_modified=units_modified,
            naming_modified=True,
            entitlement_state=context.entitlement_status,
            source_timezone=publication.timezone_label,
            source_timestamp_representation=(
                record.publication_date or record.provider_timestamp
            ),
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


def normalize_finra_short_interest_records(
    provider_records: Iterable[FinraShortInterestRecord | Mapping[str, Any]],
    context: AdapterContext,
) -> NormalizationResult:
    observations: list[Observation] = []
    diagnostics: list[NormalizationDiagnostic] = []
    seen_hashes: set[str] = set()
    seen_ids: set[str] = set()
    first_rejection: RejectedRecord | None = None

    for provider_record in provider_records:
        raw_hash = canonical_hash(provider_record)
        record_id = (
            provider_record.source_record_id
            if isinstance(provider_record, FinraShortInterestRecord)
            else provider_record.get("source_record_id")
        )
        normalized_id = None if record_id is None else str(record_id)
        if raw_hash in seen_hashes or (
            normalized_id is not None and normalized_id in seen_ids
        ):
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.FINRA_DUPLICATE_RECORD,
                    DiagnosticSeverity.WARNING,
                    "source_record_id",
                    "Duplicate provider record was emitted only once.",
                    True,
                    normalized_id,
                )
            )
            continue
        seen_hashes.add(raw_hash)
        if normalized_id is not None:
            seen_ids.add(normalized_id)
        result = normalize_finra_short_interest_record(provider_record, context)
        observations.extend(result.observations)
        diagnostics.extend(result.diagnostics)
        if result.rejection is not None and first_rejection is None:
            first_rejection = result.rejection

    by_source_id = {item.source_record_id: item for item in observations}
    linked_pairs: set[frozenset[str]] = set()
    for index, observation in enumerate(tuple(observations)):
        metadata = observation.provenance.provider_metadata
        supersedes = metadata.get("supersedes_source_record_id")
        status = metadata.get("revision_status")
        if not supersedes:
            continue
        prior = by_source_id.get(str(supersedes))
        if prior is None:
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.FINRA_REVISION_LINK_MISSING,
                    DiagnosticSeverity.WARNING,
                    "supersedes_source_record_id",
                    "Revision link target was not present in this normalization batch.",
                    True,
                    observation.source_record_id,
                )
            )
            continue
        correlation_id = f"finra-revision-{canonical_hash((prior.observation_id, observation.observation_id))[:16]}"
        prior_index = observations.index(prior)
        observations[prior_index] = prior.model_copy(
            update={"correlation_id": correlation_id}
        )
        updated = observation.model_copy(
            update={
                "parent_observation_ids": (prior.observation_id,),
                "correlation_id": correlation_id,
            }
        )
        observations[index] = updated
        by_source_id[prior.source_record_id] = observations[prior_index]
        by_source_id[updated.source_record_id] = updated
        linked_pairs.add(frozenset((prior.observation_id, observation.observation_id)))
        if status in {RevisionStatus.CORRECTED, RevisionStatus.REVISED, "CORRECTED", "REVISED"}:
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.FINRA_CORRECTED_RECORD,
                    DiagnosticSeverity.INFO,
                    "revision_status",
                    "Revision was linked to its immutable prior observation.",
                    True,
                    observation.source_record_id,
                )
            )

    grouped: dict[tuple[str | None, object], list[int]] = {}
    for index, observation in enumerate(observations):
        grouped.setdefault(
            (observation.symbol, observation.payload.settlement_date), []
        ).append(index)
    for key, indexes in grouped.items():
        if len(indexes) < 2:
            continue
        unlinked_conflict = False
        for left_position, left_index in enumerate(indexes):
            for right_index in indexes[left_position + 1 :]:
                left = observations[left_index]
                right = observations[right_index]
                if frozenset((left.observation_id, right.observation_id)) in linked_pairs:
                    continue
                if canonical_hash(left.payload) != canonical_hash(right.payload):
                    unlinked_conflict = True
        if not unlinked_conflict:
            continue
        correlation_id = f"finra-conflict-{canonical_hash((key[0], key[1]))[:16]}"
        for index in indexes:
            current = observations[index]
            observations[index] = current.model_copy(
                update={
                    "quality": Quality(
                        state=QualityState.CONFLICTED,
                        reasons=(
                            "unlinked provider records conflict for the same settlement period",
                        ),
                        evaluated_at=context.ingested_at,
                        completeness=current.quality.completeness,
                    ),
                    "correlation_id": correlation_id,
                }
            )
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.FINRA_CONFLICTING_RECORD,
                DiagnosticSeverity.ERROR,
                "short_shares",
                "Conflicting same-period records were preserved; no winner was selected.",
                True,
                None,
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
