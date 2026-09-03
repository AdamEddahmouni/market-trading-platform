from collections.abc import Iterable, Mapping
from datetime import datetime
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
    NewsItemPayload,
    Observation,
    ObservationKind,
    PayloadType,
    Provenance,
    Quality,
    QualityState,
)
from squeeze_core.replay.engine import observation_order_key
from squeeze_core.serialization import canonical_hash

from .models import NewsRecord
from .parsing import NewsParseError, ParsedNewsTimestamp, sanitize_news_url, parse_news_timestamp
from .semantics import NewsDateOnlyPolicy, NewsLifecycleStatus, PROVIDER_SOURCE
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


def _timestamp(
    value: str | None,
    *,
    record: NewsRecord,
    context: AdapterContext,
    field: str,
) -> ParsedNewsTimestamp | None:
    return parse_news_timestamp(
        value,
        timezone_name=record.timezone or context.source_timezone,
        policy=record.date_only_policy,
        field=field,
        received_at=context.ingested_at,
    )


_LIFECYCLE_DIAGNOSTIC = {
    NewsLifecycleStatus.UPDATED: DiagnosticCode.NEWS_UPDATED_RECORD,
    NewsLifecycleStatus.CORRECTED: DiagnosticCode.NEWS_CORRECTED_RECORD,
    NewsLifecycleStatus.WITHDRAWN: DiagnosticCode.NEWS_WITHDRAWN_RECORD,
    NewsLifecycleStatus.DELETED: DiagnosticCode.NEWS_DELETED_RECORD,
}


def normalize_news_record(
    provider_record: NewsRecord | Mapping[str, Any],
    context: AdapterContext,
) -> NormalizationResult:
    raw_hash = canonical_hash(provider_record)
    try:
        record = (
            provider_record
            if isinstance(provider_record, NewsRecord)
            else NewsRecord.model_validate(provider_record)
        )
    except ValidationError as error:
        raw = provider_record if isinstance(provider_record, Mapping) else {}
        code = structural_diagnostic_code(raw, error)
        raw_id = raw.get("source_record_id")
        return _rejected(
            code,
            "News provider record failed structural validation.",
            raw_hash,
            None if raw_id is None else str(raw_id),
            "headline" if code is DiagnosticCode.NEWS_INVALID_HEADLINE else None,
        )

    diagnostics: list[NormalizationDiagnostic] = []
    missing: list[str] = []

    try:
        published = _timestamp(
            record.published_at, record=record, context=context, field="published_at"
        )
        updated = _timestamp(
            record.updated_at, record=record, context=context, field="updated_at"
        )
        provider_available = _timestamp(
            record.provider_available_at,
            record=record,
            context=context,
            field="provider_available_at",
        )
        capture = _timestamp(
            record.capture_timestamp,
            record=record,
            context=context,
            field="capture_timestamp",
        )
    except NewsParseError as error:
        return _rejected(error.code, str(error), raw_hash, record.source_record_id)

    if published is None:
        missing.append("published_at")
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.NEWS_MISSING_PUBLICATION_TIMESTAMP,
                DiagnosticSeverity.WARNING,
                "published_at",
                "Original publication timestamp is missing and remains null.",
                True,
                record.source_record_id,
            )
        )

    if provider_available is None:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.NEWS_MISSING_PROVIDER_AVAILABILITY,
                DiagnosticSeverity.INFO,
                "provider_available_at",
                "Provider availability is missing; a defensible source boundary is required.",
                True,
                record.source_record_id,
            )
        )

    availability = provider_available
    availability_basis = "PROVIDER_AVAILABILITY"
    if availability is None and record.status is not NewsLifecycleStatus.ORIGINAL and updated is not None:
        availability = updated
        availability_basis = "PROVIDER_UPDATE_TIMESTAMP"
    if availability is None and published is not None:
        availability = published
        availability_basis = "PUBLICATION_TIMESTAMP"
    if availability is None:
        if record.date_only_policy is not NewsDateOnlyPolicy.UNCERTAIN_PLACEHOLDER:
            code = (
                DiagnosticCode.NEWS_CAPTURE_TIMESTAMP_ONLY
                if capture is not None
                else DiagnosticCode.NEWS_UNKNOWN_AVAILABILITY
            )
            return _rejected(
                code,
                "No defensible publication or provider-availability boundary exists.",
                raw_hash,
                record.source_record_id,
            )
        availability = ParsedNewsTimestamp(
            timestamp=context.ingested_at,
            representation=context.ingested_at.isoformat(),
            timezone_label="RECEIPT_PLACEHOLDER",
            uncertain=True,
        )
        availability_basis = "UNCERTAIN_RECEIPT_PLACEHOLDER"
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.NEWS_UNCERTAIN_AVAILABILITY,
                DiagnosticSeverity.WARNING,
                "source_timestamp",
                "Receipt is used only as an explicitly uncertain availability placeholder.",
                True,
                record.source_record_id,
            )
        )

    sanitized_url = None
    if record.url is None:
        missing.append("url")
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.NEWS_MISSING_URL,
                DiagnosticSeverity.WARNING,
                "url",
                "Article URL is missing and remains null.",
                True,
                record.source_record_id,
            )
        )
    else:
        try:
            sanitized_url = sanitize_news_url(record.url)
        except NewsParseError as error:
            missing.append("url")
            diagnostics.append(
                _diagnostic(
                    error.code,
                    DiagnosticSeverity.WARNING,
                    "url",
                    str(error),
                    True,
                    record.source_record_id,
                )
            )
        else:
            assert sanitized_url is not None
            if sanitized_url.fragment_removed:
                diagnostics.append(
                    _diagnostic(
                        DiagnosticCode.NEWS_URL_FRAGMENT_REMOVED,
                        DiagnosticSeverity.INFO,
                        "url",
                        "URL fragment was removed by the documented identity policy.",
                        True,
                        record.source_record_id,
                    )
                )
            if sanitized_url.removed_tracking_parameters:
                diagnostics.append(
                    _diagnostic(
                        DiagnosticCode.NEWS_TRACKING_PARAMETER_REMOVED,
                        DiagnosticSeverity.INFO,
                        "url",
                        "Documented tracking parameters were removed from the URL.",
                        True,
                        record.source_record_id,
                    )
                )

    for field, code in (
        ("summary", DiagnosticCode.NEWS_MISSING_SUMMARY),
        ("publisher", DiagnosticCode.NEWS_MISSING_PUBLISHER),
        ("author", DiagnosticCode.NEWS_MISSING_AUTHOR),
    ):
        if getattr(record, field) is None:
            missing.append(field)
            diagnostics.append(
                _diagnostic(
                    code,
                    DiagnosticSeverity.INFO,
                    field,
                    f"Provider omitted {field}; it remains null.",
                    True,
                    record.source_record_id,
                )
            )

    if record.symbols is None:
        symbol_status = "MISSING"
        missing.append("symbols")
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.NEWS_MISSING_SYMBOL_ASSOCIATION,
                DiagnosticSeverity.WARNING,
                "symbols",
                "No explicit symbol association was supplied.",
                True,
                record.source_record_id,
            )
        )
    elif not record.symbols:
        symbol_status = "EXPLICIT_EMPTY"
        missing.append("symbols")
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.NEWS_EMPTY_SYMBOL_ASSOCIATION,
                DiagnosticSeverity.WARNING,
                "symbols",
                "The source supplied an explicitly empty symbol association.",
                True,
                record.source_record_id,
            )
        )
    else:
        symbol_status = "EXPLICIT"

    lifecycle_code = _LIFECYCLE_DIAGNOSTIC.get(record.status)
    if lifecycle_code is not None:
        diagnostics.append(
            _diagnostic(
                lifecycle_code,
                DiagnosticSeverity.INFO,
                "status",
                f"Objective news lifecycle status is {record.status.value}.",
                True,
                record.source_record_id,
            )
        )
        if not record.supersedes_provider_record_id and not record.prior_canonical_url:
            missing.append("revision_relationship")
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.NEWS_REVISION_LINK_MISSING,
                    DiagnosticSeverity.WARNING,
                    "supersedes_provider_record_id",
                    "Lifecycle record does not identify a prior provider record or canonical URL.",
                    True,
                    record.source_record_id,
                )
            )

    if context.ingested_at < availability.timestamp:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.NEWS_PROVIDER_AVAILABILITY_AFTER_RECEIPT,
                DiagnosticSeverity.WARNING,
                "received_timestamp",
                "Receipt precedes claimed provider availability; effective time waits for availability.",
                True,
                record.source_record_id,
            )
        )
    if published is not None and context.ingested_at < published.timestamp:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.NEWS_RECEIVED_BEFORE_PUBLICATION,
                DiagnosticSeverity.WARNING,
                "received_timestamp",
                "Receipt precedes claimed original publication.",
                True,
                record.source_record_id,
            )
        )

    partial = bool(missing)
    if partial:
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.NEWS_PARTIAL_RECORD,
                DiagnosticSeverity.WARNING,
                None,
                "News record was normalized only where objective metadata was defensible.",
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

    canonical_url = None if sanitized_url is None else sanitized_url.url
    source_record_id = record.provider_record_id
    provider_record_id_status = "SUPPLIED"
    if source_record_id is None:
        provider_record_id_status = "DERIVED"
        source_record_id = f"derived:{canonical_hash({'provider': record.provider, 'url': canonical_url, 'raw_hash': raw_hash})[:24]}"

    metadata = {
        "adapter_version": context.adapter_version,
        "normalization_version": context.normalization_version,
        "fixture_origin": record.fixture_origin,
        "source_shape": record.source_shape,
        "fixture_source_record_id": record.source_record_id,
        "provider_record_id": record.provider_record_id,
        "provider_record_id_status": provider_record_id_status,
        "headline_representation": record.headline,
        "author": record.author,
        "language": record.language,
        "content_type": record.content_type,
        "status": record.status,
        "supersedes_provider_record_id": record.supersedes_provider_record_id,
        "prior_canonical_url": record.prior_canonical_url,
        "published_at_representation": record.published_at,
        "published_at_uncertain": False if published is None else published.uncertain,
        "updated_at_representation": record.updated_at,
        "updated_at": None if updated is None else updated.timestamp,
        "provider_available_at_representation": record.provider_available_at,
        "provider_availability": availability.timestamp,
        "availability_basis": availability_basis,
        "availability_uncertain": availability.uncertain,
        "capture_timestamp_representation": record.capture_timestamp,
        "capture_timestamp": None if capture is None else capture.timestamp,
        "canonical_url": canonical_url,
        "url_policy_version": None if sanitized_url is None else sanitized_url.policy_version,
        "removed_tracking_parameters": () if sanitized_url is None else sanitized_url.removed_tracking_parameters,
        "symbol_association_status": symbol_status,
        "provider_metadata": record.provider_metadata,
        "source_endpoint_name": context.source_endpoint_name,
    }
    observation = Observation(
        schema_version="1.0.0",
        event_type=EventType.NEWS_ITEM,
        symbol=None,
        asset_class=AssetClass.UNKNOWN,
        source=PROVIDER_SOURCE,
        source_record_id=source_record_id,
        source_timestamp=availability.timestamp,
        received_timestamp=context.ingested_at,
        effective_timestamp=max(availability.timestamp, context.ingested_at),
        market_session=MarketSession.UNKNOWN,
        data_freshness=DataFreshness.HISTORICAL,
        observation_kind=ObservationKind.PROVIDER_PUBLISHED,
        quality=quality,
        payload_type=PayloadType.NEWS_ITEM,
        payload=NewsItemPayload(
            headline=record.headline,
            summary=record.summary,
            url=canonical_url,
            publisher=record.publisher,
            published_at=(
                None if published is None or published.uncertain else published.timestamp
            ),
            associated_symbols=record.symbols or (),
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
        timezone=availability.timezone_label,
        raw_payload_hash=raw_hash,
        normalization_version=context.normalization_version,
    )
    return NormalizationResult(
        observations=(observation,), diagnostics=_sorted_diagnostics(diagnostics)
    )


def normalize_news_records(
    provider_records: Iterable[NewsRecord | Mapping[str, Any]],
    context: AdapterContext,
) -> NormalizationResult:
    observations: list[Observation] = []
    diagnostics: list[NormalizationDiagnostic] = []
    seen_hashes: set[str] = set()
    first_rejection: RejectedRecord | None = None

    for raw in provider_records:
        raw_hash = canonical_hash(raw)
        raw_id_value = raw.source_record_id if isinstance(raw, NewsRecord) else raw.get("source_record_id")
        raw_id = None if raw_id_value is None else str(raw_id_value)
        if raw_hash in seen_hashes:
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.NEWS_DUPLICATE_RECORD,
                    DiagnosticSeverity.WARNING,
                    "source_record_id",
                    "Exact duplicate news record was emitted only once.",
                    True,
                    raw_id,
                )
            )
            continue
        seen_hashes.add(raw_hash)
        result = normalize_news_record(raw, context)
        observations.extend(result.observations)
        diagnostics.extend(result.diagnostics)
        if result.rejection is not None and first_rejection is None:
            first_rejection = result.rejection

    by_source_id = {item.source_record_id: item for item in observations}
    for index, observation in enumerate(tuple(observations)):
        supersedes = observation.provenance.provider_metadata.get(
            "supersedes_provider_record_id"
        )
        if not supersedes:
            continue
        prior = by_source_id.get(str(supersedes))
        if prior is None:
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.NEWS_REVISION_LINK_MISSING,
                    DiagnosticSeverity.WARNING,
                    "supersedes_provider_record_id",
                    "Prior provider news record was not present in this batch.",
                    True,
                    str(observation.provenance.provider_metadata.get("fixture_source_record_id")),
                )
            )
            continue
        correlation_id = f"news-revision-{canonical_hash((prior.observation_id, observation.observation_id))[:16]}"
        prior_index = observations.index(prior)
        observations[prior_index] = prior.model_copy(update={"correlation_id": correlation_id})
        observations[index] = observation.model_copy(
            update={
                "parent_observation_ids": (prior.observation_id,),
                "correlation_id": correlation_id,
            }
        )
        by_source_id[prior.source_record_id] = observations[prior_index]
        by_source_id[observation.source_record_id] = observations[index]

    grouped: dict[str, list[int]] = {}
    for index, observation in enumerate(observations):
        grouped.setdefault(observation.source_record_id, []).append(index)
    for source_id, indexes in grouped.items():
        if len(indexes) < 2:
            continue
        raw_hashes = {observations[index].raw_payload_hash for index in indexes}
        if len(raw_hashes) == 1:
            continue
        correlation_id = f"news-conflict-{canonical_hash(source_id)[:16]}"
        for index in indexes:
            current = observations[index]
            observations[index] = current.model_copy(
                update={
                    "quality": Quality(
                        state=QualityState.CONFLICTED,
                        reasons=("same provider record ID has conflicting news metadata",),
                        evaluated_at=context.ingested_at,
                        completeness=current.quality.completeness,
                    ),
                    "correlation_id": correlation_id,
                }
            )
        diagnostics.append(
            _diagnostic(
                DiagnosticCode.NEWS_CONFLICTING_RECORD,
                DiagnosticSeverity.ERROR,
                "provider_record_id",
                "Conflicting same-ID news records were preserved; no winner was selected.",
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
