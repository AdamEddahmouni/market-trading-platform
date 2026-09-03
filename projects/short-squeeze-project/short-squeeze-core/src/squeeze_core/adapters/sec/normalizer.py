from collections.abc import Iterable, Mapping
from datetime import UTC, date, datetime
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
    SecFilingPayload,
)
from squeeze_core.replay.engine import observation_order_key
from squeeze_core.serialization import canonical_hash

from .models import SecFilingRecord
from .parsing import (
    PublicAvailability,
    SecParseError,
    parse_accession_number,
    parse_cik,
    parse_document_count,
    parse_form_type,
    parse_period_of_report,
    parse_public_availability,
    sanitize_primary_document,
)
from .semantics import FilingStatus, PROVIDER_SOURCE
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


def _parse_exact_timestamp(value: str, timezone_name: str | None) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as error:
        raise SecParseError(DiagnosticCode.SEC_UNKNOWN_AVAILABILITY_TIME, "filing timestamp is invalid") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        if timezone_name in {None, ""}:
            raise SecParseError(DiagnosticCode.SEC_UNKNOWN_PUBLICATION_TIMEZONE, "filing timestamp timezone is missing")
        if timezone_name == "UTC":
            parsed = parsed.replace(tzinfo=UTC)
        elif len(timezone_name) == 6 and timezone_name[0] in "+-" and timezone_name[3] == ":":
            sign = 1 if timezone_name[0] == "+" else -1
            from datetime import timedelta, timezone

            parsed = parsed.replace(
                tzinfo=timezone(
                    sign * timedelta(
                        hours=int(timezone_name[1:3]), minutes=int(timezone_name[4:6])
                    )
                )
            )
        else:
            raise SecParseError(DiagnosticCode.SEC_UNKNOWN_PUBLICATION_TIMEZONE, "unsupported filing timezone")
    return parsed.astimezone(UTC)


def _filed_timestamp(
    record: SecFilingRecord,
    availability: PublicAvailability,
    diagnostics: list[NormalizationDiagnostic],
) -> datetime:
    if record.filed_at is None or not record.filed_at.strip():
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.SEC_DATE_ONLY_FILED,
                DiagnosticSeverity.WARNING,
                "filed_at",
                "Filed time is absent; public availability is used as an uncertain canonical placeholder.",
                True,
                record.source_record_id,
            )
        )
        return availability.timestamp
    raw = record.filed_at.strip()
    if len(raw) == 10:
        try:
            date.fromisoformat(raw)
        except ValueError as error:
            raise SecParseError(DiagnosticCode.SEC_UNKNOWN_AVAILABILITY_TIME, "filed date is invalid") from error
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.SEC_DATE_ONLY_FILED,
                DiagnosticSeverity.WARNING,
                "filed_at",
                "Date-only filed value does not establish availability; public time is the canonical placeholder.",
                True,
                record.source_record_id,
            )
        )
        return availability.timestamp
    return _parse_exact_timestamp(raw, record.filed_timezone)


def normalize_sec_filing_record(
    provider_record: SecFilingRecord | Mapping[str, Any],
    context: AdapterContext,
) -> NormalizationResult:
    raw_hash = canonical_hash(provider_record)
    try:
        record = (
            provider_record
            if isinstance(provider_record, SecFilingRecord)
            else SecFilingRecord.model_validate(provider_record)
        )
    except ValidationError as error:
        raw = provider_record if isinstance(provider_record, Mapping) else {}
        code = structural_diagnostic_code(raw, error)
        source_record_id = raw.get("source_record_id")
        return _rejected(
            code,
            "SEC-shaped provider record failed structural validation.",
            raw_hash,
            None if source_record_id is None else str(source_record_id),
        )

    try:
        accession = parse_accession_number(record.accession_number)
        form_type = parse_form_type(record.form_type)
        availability = parse_public_availability(
            published_at=record.published_at,
            publication_timezone=record.publication_timezone or context.source_timezone,
            accepted_at=record.accepted_at,
            acceptance_timezone=record.acceptance_timezone or context.source_timezone,
            date_only_policy=record.date_only_publication_policy,
            received_at=context.ingested_at,
        )
    except SecParseError as error:
        return _rejected(error.code, str(error), raw_hash, record.source_record_id)

    diagnostics: list[NormalizationDiagnostic] = []
    missing: list[str] = []
    invalid: list[str] = []

    cik: str | None
    try:
        cik = parse_cik(record.issuer_cik)
        if record.issuer_cik is not None and cik != record.issuer_cik.strip():
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.SEC_CIK_NORMALIZED,
                    DiagnosticSeverity.INFO,
                    "issuer_cik",
                    "CIK was normalized to ten digits.",
                    True,
                    record.source_record_id,
                )
            )
    except SecParseError as error:
        if error.code is DiagnosticCode.SEC_MISSING_CIK:
            cik = None
            missing.append("issuer_cik")
            diagnostics.append(_diagnostic(error.code, DiagnosticSeverity.WARNING, "issuer_cik", str(error), True, record.source_record_id))
        else:
            return _rejected(error.code, str(error), raw_hash, record.source_record_id, "issuer_cik")

    if record.accession_number is not None and accession != record.accession_number.strip():
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.SEC_ACCESSION_NORMALIZED,
                DiagnosticSeverity.INFO,
                "accession_number",
                "Compact accession number was normalized to canonical dashed form.",
                True,
                record.source_record_id,
            )
        )

    try:
        period = parse_period_of_report(record.period_of_report)
    except SecParseError as error:
        invalid.append("period_of_report")
        period = None
        diagnostics.append(_diagnostic(error.code, DiagnosticSeverity.ERROR, "period_of_report", str(error), True, record.source_record_id))
    if period is None:
        missing.append("period_of_report")
        diagnostics.append(_diagnostic(DiagnosticCode.SEC_MISSING_PERIOD_OF_REPORT, DiagnosticSeverity.WARNING, "period_of_report", "Period of report is missing and remains null.", True, record.source_record_id))

    try:
        primary_document = sanitize_primary_document(record.primary_document)
    except SecParseError as error:
        primary_document = None
        invalid.append("primary_document")
        diagnostics.append(_diagnostic(error.code, DiagnosticSeverity.WARNING, "primary_document", str(error), True, record.source_record_id))
    if primary_document is None:
        missing.append("primary_document")
        diagnostics.append(_diagnostic(DiagnosticCode.SEC_MISSING_PRIMARY_DOCUMENT, DiagnosticSeverity.WARNING, "primary_document", "Primary document is missing and remains null.", True, record.source_record_id))

    try:
        document_count = parse_document_count(record.document_count)
    except SecParseError as error:
        document_count = None
        invalid.append("document_count")
        diagnostics.append(_diagnostic(error.code, DiagnosticSeverity.ERROR, "document_count", str(error), True, record.source_record_id))

    try:
        filed_at = _filed_timestamp(record, availability, diagnostics)
    except SecParseError as error:
        return _rejected(error.code, str(error), raw_hash, record.source_record_id, "filed_at")

    explicit_amendment = record.is_amendment is True or record.filing_status is FilingStatus.AMENDED
    suffix_amendment = form_type.endswith("/A")
    is_amendment = explicit_amendment or suffix_amendment
    if is_amendment:
        diagnostics.append(_diagnostic(DiagnosticCode.SEC_AMENDMENT_RECORD, DiagnosticSeverity.INFO, "is_amendment", "Amendment is preserved as a new immutable observation.", True, record.source_record_id))
        if not record.amends_accession_number:
            missing.append("amends_accession_number")
            diagnostics.append(_diagnostic(DiagnosticCode.SEC_AMENDMENT_LINK_MISSING, DiagnosticSeverity.WARNING, "amends_accession_number", "Amendment does not identify an original accession.", True, record.source_record_id))

    amends_accession: str | None = None
    if record.amends_accession_number:
        try:
            amends_accession = parse_accession_number(record.amends_accession_number)
        except SecParseError as error:
            invalid.append("amends_accession_number")
            diagnostics.append(_diagnostic(error.code, DiagnosticSeverity.ERROR, "amends_accession_number", str(error), True, record.source_record_id))

    if record.filing_url:
        diagnostics.append(_diagnostic(DiagnosticCode.SEC_REMOTE_URL_SANITIZED, DiagnosticSeverity.INFO, "filing_url", "Filing URL was omitted; normalization never opens or retains remote references.", True, record.source_record_id))
    if availability.uncertain:
        diagnostics.append(_diagnostic(DiagnosticCode.SEC_DATE_ONLY_PUBLICATION, DiagnosticSeverity.WARNING, "published_at", "Date-only public availability used an explicit conservative policy.", True, record.source_record_id))
    if context.ingested_at < availability.timestamp:
        diagnostics.append(_diagnostic(DiagnosticCode.SEC_RECEIVED_BEFORE_ACCEPTANCE, DiagnosticSeverity.WARNING, "received_timestamp", "Receipt precedes claimed public availability; effective time waits for public availability.", True, record.source_record_id))

    partial = bool(missing or invalid or availability.uncertain)
    if partial:
        diagnostics.append(_diagnostic(DiagnosticCode.SEC_PARTIAL_RECORD, DiagnosticSeverity.WARNING, None, "Record was normalized only where filing metadata was defensible.", True, record.source_record_id))

    if invalid:
        quality = Quality(
            state=QualityState.INVALID,
            reasons=tuple(f"invalid {field}" for field in sorted(set(invalid))),
            evaluated_at=context.ingested_at,
            completeness=Completeness.PARTIAL,
        )
    elif missing or availability.uncertain:
        reasons = tuple(f"missing {field}" for field in sorted(set(missing)))
        if availability.uncertain:
            reasons += ("exact public availability time is uncertain",)
        quality = Quality(
            state=QualityState.MISSING,
            reasons=reasons,
            evaluated_at=context.ingested_at,
            completeness=Completeness.PARTIAL,
        )
    else:
        quality = Quality(
            state=QualityState.KNOWN_VALUE,
            evaluated_at=context.ingested_at,
            completeness=Completeness.COMPLETE,
        )

    metadata = {
        "adapter_version": context.adapter_version,
        "normalization_version": context.normalization_version,
        "fixture_origin": record.fixture_origin,
        "company_name": record.company_name,
        "acceptance_timestamp": (
            _parse_exact_timestamp(record.accepted_at, record.acceptance_timezone or context.source_timezone)
            if record.accepted_at and len(record.accepted_at.strip()) != 10
            else None
        ),
        "acceptance_timestamp_representation": record.accepted_at,
        "publication_timestamp_representation": record.published_at,
        "public_availability_basis": availability.basis,
        "public_availability_uncertain": availability.uncertain,
        "filed_timestamp_representation": record.filed_at,
        "is_amendment": is_amendment,
        "amends_accession_number": amends_accession,
        "document_count": document_count,
        "file_number": record.file_number,
        "film_number": record.film_number,
        "fiscal_year_end": record.fiscal_year_end,
        "provider_record_id": record.provider_record_id,
        "filing_status": record.filing_status,
        "filing_url_omitted": record.filing_url is not None,
    }
    observation = Observation(
        schema_version="1.0.0",
        event_type=EventType.SEC_FILING,
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
        payload_type=PayloadType.SEC_FILING,
        payload=SecFilingPayload(
            form_type=form_type,
            accession_number=accession,
            filed_at=filed_at,
            period_of_report=period,
            primary_document=primary_document,
            issuer_cik=cik,
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
            source_timestamp_representation=record.published_at or record.accepted_at,
            provider_metadata=metadata,
        ),
        timezone=availability.timezone_label,
        raw_payload_hash=raw_hash,
        normalization_version=context.normalization_version,
    )
    return NormalizationResult(
        observations=(observation,), diagnostics=_sorted_diagnostics(diagnostics)
    )


def normalize_sec_filing_records(
    provider_records: Iterable[SecFilingRecord | Mapping[str, Any]],
    context: AdapterContext,
) -> NormalizationResult:
    observations: list[Observation] = []
    diagnostics: list[NormalizationDiagnostic] = []
    seen_hashes: set[str] = set()
    seen_source_ids: set[str] = set()
    first_rejection: RejectedRecord | None = None

    for raw in provider_records:
        raw_hash = canonical_hash(raw)
        source_id_value = raw.source_record_id if isinstance(raw, SecFilingRecord) else raw.get("source_record_id")
        source_id = None if source_id_value is None else str(source_id_value)
        if raw_hash in seen_hashes or (source_id is not None and source_id in seen_source_ids):
            diagnostics.append(_diagnostic(DiagnosticCode.SEC_DUPLICATE_RECORD, DiagnosticSeverity.WARNING, "source_record_id", "Duplicate SEC record was emitted only once.", True, source_id))
            continue
        seen_hashes.add(raw_hash)
        if source_id is not None:
            seen_source_ids.add(source_id)
        result = normalize_sec_filing_record(raw, context)
        observations.extend(result.observations)
        diagnostics.extend(result.diagnostics)
        if result.rejection is not None and first_rejection is None:
            first_rejection = result.rejection

    by_accession = {item.payload.accession_number: item for item in observations}
    linked_pairs: set[frozenset[str]] = set()
    for index, observation in enumerate(tuple(observations)):
        amended_accession = observation.provenance.provider_metadata.get("amends_accession_number")
        if not amended_accession:
            continue
        prior = by_accession.get(str(amended_accession))
        if prior is None:
            diagnostics.append(_diagnostic(DiagnosticCode.SEC_AMENDMENT_LINK_MISSING, DiagnosticSeverity.WARNING, "amends_accession_number", "Original accession was not present in this batch.", True, observation.source_record_id))
            continue
        correlation_id = f"sec-amendment-{canonical_hash((prior.observation_id, observation.observation_id))[:16]}"
        prior_index = observations.index(prior)
        observations[prior_index] = prior.model_copy(update={"correlation_id": correlation_id})
        observations[index] = observation.model_copy(update={"parent_observation_ids": (prior.observation_id,), "correlation_id": correlation_id})
        by_accession[prior.payload.accession_number] = observations[prior_index]
        by_accession[observation.payload.accession_number] = observations[index]
        linked_pairs.add(frozenset((prior.observation_id, observation.observation_id)))

    grouped: dict[tuple[str | None, str], list[int]] = {}
    for index, observation in enumerate(observations):
        grouped.setdefault((observation.symbol, observation.payload.accession_number), []).append(index)
    for key, indexes in grouped.items():
        if len(indexes) < 2:
            continue
        payload_hashes = {canonical_hash(observations[index].payload) for index in indexes}
        if len(payload_hashes) == 1:
            continue
        correlation_id = f"sec-conflict-{canonical_hash(key)[:16]}"
        for index in indexes:
            current = observations[index]
            observations[index] = current.model_copy(
                update={
                    "quality": Quality(
                        state=QualityState.CONFLICTED,
                        reasons=("same accession has conflicting filing metadata",),
                        evaluated_at=context.ingested_at,
                        completeness=current.quality.completeness,
                    ),
                    "correlation_id": correlation_id,
                }
            )
        diagnostics.append(_diagnostic(DiagnosticCode.SEC_CONFLICTING_RECORD, DiagnosticSeverity.ERROR, "accession_number", "Conflicting same-accession records were preserved; no winner was selected.", True, None))

    observations.sort(key=observation_order_key)
    if not observations and first_rejection is not None:
        return NormalizationResult(diagnostics=_sorted_diagnostics(diagnostics), rejection=first_rejection)
    return NormalizationResult(observations=tuple(observations), diagnostics=_sorted_diagnostics(diagnostics))
