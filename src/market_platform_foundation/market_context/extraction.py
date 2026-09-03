"""MC5 event extraction — typed ontology, economic channels, and deterministic metrics."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from ..contracts.market_context import (
    CompanyEventType,
    ContextQualityFlag,
    EconomicChannel,
    EvidenceSpan,
    ExtractedMetric,
    InformationEvent,
    MacroEventType,
    ModelVersionRef,
    PublicationState,
    extracted_metric_to_dict,
)
from ..normalization.equity_bars import iso_to_epoch_ns
from .entity_resolution import ContextDocumentRecord
from .event_clustering import cluster_fixture_records

PRODUCER_VERSION = "market_context_extraction_v1"
RULE_MODEL_ID = "rule-v1"
LLM_MODEL_ID = "fixture-llm-v1"

_RULE_MODEL_VERSION = ModelVersionRef(
    model_id=RULE_MODEL_ID,
    model_version="1.0.0",
    schema_version="market_context.v1",
    feature_version=PRODUCER_VERSION,
)
_LLM_MODEL_VERSION = ModelVersionRef(
    model_id=LLM_MODEL_ID,
    model_version="1.0.0",
    prompt_version="mc5_extraction_prompt_v1",
    schema_version="mc5_extraction_schema_v1",
    feature_version=PRODUCER_VERSION,
)

_CANONICAL_TO_COMPANY: dict[str, CompanyEventType] = {
    "earnings_beat": CompanyEventType.EARNINGS,
    "fda_clearance": CompanyEventType.FDA_APPROVAL,
    "analyst_upgrade": CompanyEventType.ANALYST_UPGRADE,
    "offering_risk": CompanyEventType.EQUITY_ISSUANCE,
}

_CANONICAL_TO_CHANNELS: dict[str, tuple[EconomicChannel, ...]] = {
    "earnings_beat": (EconomicChannel.REVENUE_UP,),
    "fda_clearance": (EconomicChannel.REGULATORY_RISK_DOWN,),
    "analyst_upgrade": (EconomicChannel.MARGIN_UP,),
    "offering_risk": (
        EconomicChannel.DILUTION_UP,
        EconomicChannel.LIQUIDITY_RISK_UP,
    ),
    "macro_headwind": (EconomicChannel.UNCERTAINTY_UP,),
}

_PRICE_TARGET_RE = re.compile(
    r"price target(?:\s+raised)?(?:\s+to)?\s*\$?\s*([\d]+(?:\.\d+)?)",
    re.IGNORECASE,
)
_REVENUE_RE = re.compile(
    r"revenue\s+(?:of\s+)?\$?\s*([\d]+(?:\.\d+)?)\s*(million|billion)?",
    re.IGNORECASE,
)
_MARGIN_RE = re.compile(
    r"margin(?:\s+profile)?(?:\s+at)?\s*([\d]+(?:\.\d+)?)\s*%",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class LlmExtractionLabel:
    """Fixture-precomputed schema-bound extraction for one document."""

    document_id: str
    company_event_type: CompanyEventType | None
    macro_event_type: MacroEventType | None
    economic_channels: tuple[EconomicChannel, ...]
    confidence: float | None
    source_span: EvidenceSpan | None
    model_version: ModelVersionRef
    quality_flags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class DocumentExtractionResult:
    document_id: str
    company_event_type: CompanyEventType | None
    macro_event_type: MacroEventType | None
    economic_channels: tuple[EconomicChannel, ...]
    extracted_metrics: tuple[ExtractedMetric, ...]
    extraction_models: tuple[str, ...]
    llm_confidence: float | None
    evidence_span: EvidenceSpan | None
    quality_flags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class EventExtractionSummary:
    event_id: str
    canonical_event_type: str
    company_event_type: CompanyEventType | None
    macro_event_type: MacroEventType | None
    economic_channels: tuple[EconomicChannel, ...]
    extracted_metrics: tuple[ExtractedMetric, ...]
    extraction_models: tuple[str, ...]
    document_count: int
    quality_flags: tuple[str, ...] = field(default_factory=tuple)


def map_canonical_event_type(canonical_event_type: str) -> tuple[CompanyEventType | None, MacroEventType | None]:
    """Map fixture canonical_event_type string to versioned ontology enums."""
    company = _CANONICAL_TO_COMPANY.get(canonical_event_type)
    return company, None


def infer_economic_channels(
    canonical_event_type: str,
    *,
    title: str | None = None,
    body: str | None = None,
    llm_channels: tuple[EconomicChannel, ...] = (),
) -> tuple[EconomicChannel, ...]:
    """Infer economic channels from ontology mapping, keywords, and optional LLM fixture."""
    channels: list[EconomicChannel] = list(_CANONICAL_TO_CHANNELS.get(canonical_event_type, ()))
    text = f"{title or ''} {body or ''}".lower()
    if "margin" in text and EconomicChannel.MARGIN_UP not in channels:
        if canonical_event_type == "analyst_upgrade":
            channels.append(EconomicChannel.MARGIN_UP)
    if "dilution" in text or "offering" in text:
        if EconomicChannel.DILUTION_UP not in channels:
            channels.append(EconomicChannel.DILUTION_UP)
    for channel in llm_channels:
        if channel not in channels:
            channels.append(channel)
    return tuple(channels)


def extract_metrics_rule_v1(
    title: str | None,
    body: str | None,
    *,
    document_id: str,
) -> tuple[ExtractedMetric, ...]:
    """Deterministic regex metric extraction from document text."""
    text = f"{title or ''} {body or ''}"
    metrics: list[ExtractedMetric] = []

    price_match = _PRICE_TARGET_RE.search(text)
    if price_match:
        metrics.append(
            ExtractedMetric(
                metric_name="price_target",
                reported_value=_decimal_or_none(price_match.group(1)),
                units="USD",
                period=None,
                currency="USD",
                comparison_period=None,
                source_span=_span_from_match(document_id, text, price_match),
            )
        )

    revenue_match = _REVENUE_RE.search(text)
    if revenue_match:
        units = revenue_match.group(2) or "USD"
        metrics.append(
            ExtractedMetric(
                metric_name="revenue",
                reported_value=_decimal_or_none(revenue_match.group(1)),
                units=units.upper() if units else "USD",
                period=None,
                currency="USD",
                comparison_period=None,
                source_span=_span_from_match(document_id, text, revenue_match),
            )
        )

    margin_match = _MARGIN_RE.search(text)
    if margin_match:
        metrics.append(
            ExtractedMetric(
                metric_name="gross_margin",
                reported_value=_decimal_or_none(margin_match.group(1)),
                units="percent",
                period=None,
                currency=None,
                comparison_period=None,
                source_span=_span_from_match(document_id, text, margin_match),
            )
        )

    return tuple(metrics)


def _decimal_or_none(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def _span_from_match(document_id: str, text: str, match: re.Match[str]) -> EvidenceSpan:
    excerpt = match.group(0).strip()
    start = match.start()
    end = match.end()
    return EvidenceSpan(
        source_document_id=document_id,
        start_offset=start,
        end_offset=end,
        excerpt=excerpt,
        extraction_model=_RULE_MODEL_VERSION,
    )


def _evidence_span_from_dict(document_id: str, row: dict[str, Any]) -> EvidenceSpan | None:
    span_row = row.get("source_span")
    if not isinstance(span_row, dict):
        return None
    excerpt = str(span_row.get("excerpt", "")).strip()
    if not excerpt:
        return None
    start_offset = span_row.get("start_offset")
    end_offset = span_row.get("end_offset")
    return EvidenceSpan(
        source_document_id=str(span_row.get("source_document_id", document_id)),
        start_offset=int(start_offset) if start_offset is not None else None,
        end_offset=int(end_offset) if end_offset is not None else None,
        excerpt=excerpt,
        extraction_model=_LLM_MODEL_VERSION,
        confidence=float(row.get("confidence")) if row.get("confidence") is not None else None,
    )


def _parse_company_event_type(value: str | None) -> CompanyEventType | None:
    if not value:
        return None
    normalized = value.strip().upper()
    for item in CompanyEventType:
        if item.value == normalized:
            return item
    return None


def _parse_macro_event_type(value: str | None) -> MacroEventType | None:
    if not value:
        return None
    normalized = value.strip().upper()
    for item in MacroEventType:
        if item.value == normalized:
            return item
    return None


def _parse_economic_channels(values: Any) -> tuple[EconomicChannel, ...]:
    if not isinstance(values, list):
        return ()
    channels: list[EconomicChannel] = []
    for raw in values:
        normalized = str(raw).strip().upper()
        for item in EconomicChannel:
            if item.value == normalized:
                channels.append(item)
                break
    return tuple(channels)


def load_llm_extraction_fixture(path: Path) -> dict[str, LlmExtractionLabel]:
    """Load fixture-precomputed schema-bound LLM extractions keyed by document_id."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("extractions", payload.get("labels", []))
    result: dict[str, LlmExtractionLabel] = {}
    if not isinstance(rows, list):
        return result

    for row in rows:
        if not isinstance(row, dict):
            continue
        document_id = str(row.get("document_id", "")).strip()
        if not document_id:
            continue
        model_id = str(row.get("model_id", LLM_MODEL_ID))
        model_version = ModelVersionRef(
            model_id=model_id,
            model_version=str(row.get("model_version", "1.0.0")),
            prompt_version=row.get("prompt_version"),
            schema_version=str(row.get("schema_version", "mc5_extraction_schema_v1")),
            feature_version=PRODUCER_VERSION,
        )
        confidence_raw = row.get("confidence")
        confidence = float(confidence_raw) if confidence_raw is not None else None
        quality_flags = tuple(str(flag) for flag in row.get("quality_flags", []))
        if confidence is not None and confidence < 0.5:
            quality_flags = tuple(
                dict.fromkeys(
                    (*quality_flags, ContextQualityFlag.LLM_EXTRACTION_LOW_CONFIDENCE.value)
                )
            )
        result[document_id] = LlmExtractionLabel(
            document_id=document_id,
            company_event_type=_parse_company_event_type(row.get("company_event_type")),
            macro_event_type=_parse_macro_event_type(row.get("macro_event_type")),
            economic_channels=_parse_economic_channels(row.get("economic_channels")),
            confidence=confidence,
            source_span=_evidence_span_from_dict(document_id, row),
            model_version=model_version,
            quality_flags=quality_flags,
        )
    return result


def load_structured_metrics_fixture(path: Path) -> dict[str, tuple[ExtractedMetric, ...]]:
    """Load fixture structured numeric facts keyed by document_id."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("metrics", [])
    result: dict[str, tuple[ExtractedMetric, ...]] = {}
    if not isinstance(rows, list):
        return result

    for row in rows:
        if not isinstance(row, dict):
            continue
        document_id = str(row.get("document_id", "")).strip()
        if not document_id:
            continue
        metric_rows = row.get("metrics", [])
        if not isinstance(metric_rows, list):
            continue
        metrics: list[ExtractedMetric] = []
        for metric_row in metric_rows:
            if not isinstance(metric_row, dict):
                continue
            reported = metric_row.get("reported_value")
            reported_decimal = None
            if reported is not None:
                reported_decimal = _decimal_or_none(str(reported))
            span = None
            span_row = metric_row.get("source_span")
            if isinstance(span_row, dict):
                excerpt = str(span_row.get("excerpt", "")).strip()
                if excerpt:
                    span = EvidenceSpan(
                        source_document_id=str(
                            span_row.get("source_document_id", document_id)
                        ),
                        start_offset=span_row.get("start_offset"),
                        end_offset=span_row.get("end_offset"),
                        excerpt=excerpt,
                        extraction_model=_RULE_MODEL_VERSION,
                    )
            metrics.append(
                ExtractedMetric(
                    metric_name=str(metric_row.get("metric_name", "")),
                    reported_value=reported_decimal,
                    units=metric_row.get("units"),
                    period=metric_row.get("period"),
                    currency=metric_row.get("currency"),
                    comparison_period=metric_row.get("comparison_period"),
                    source_span=span,
                    quality_flags=tuple(str(flag) for flag in metric_row.get("quality_flags", [])),
                )
            )
        if metrics:
            result[document_id] = tuple(metrics)
    return result


def _pit_visible(record: ContextDocumentRecord, prediction_cutoff: int) -> bool:
    return iso_to_epoch_ns(record.document.available_time) <= prediction_cutoff


def _source_priority(record: ContextDocumentRecord) -> int:
    source = record.document.source
    score = 0
    if source.official:
        score += 2
    if source.first_party:
        score += 1
    return score


def extract_document(
    record: ContextDocumentRecord,
    *,
    prediction_cutoff: int,
    llm_labels: dict[str, LlmExtractionLabel] | None = None,
    structured_metrics: dict[str, tuple[ExtractedMetric, ...]] | None = None,
) -> DocumentExtractionResult | None:
    """Extract typed events and metrics for one document."""
    if not _pit_visible(record, prediction_cutoff):
        return None

    quality_flags: list[str] = []
    if record.entity_resolution.ambiguous:
        quality_flags.append(ContextQualityFlag.EXTRACTION_ENTITY_AMBIGUOUS.value)

    canonical = record.canonical_event_type
    rule_company, rule_macro = map_canonical_event_type(canonical)
    llm_label = None
    if llm_labels is not None:
        llm_label = llm_labels.get(record.document.document_id)

    company_event_type = rule_company
    macro_event_type = rule_macro
    llm_channels: tuple[EconomicChannel, ...] = ()
    llm_confidence: float | None = None
    evidence_span: EvidenceSpan | None = None

    if llm_label is not None:
        if llm_label.company_event_type is not None:
            company_event_type = llm_label.company_event_type
        if llm_label.macro_event_type is not None:
            macro_event_type = llm_label.macro_event_type
        llm_channels = llm_label.economic_channels
        llm_confidence = llm_label.confidence
        evidence_span = llm_label.source_span
        quality_flags.extend(flag for flag in llm_label.quality_flags if flag not in quality_flags)

    if not canonical:
        company_event_type = None
        macro_event_type = None

    economic_channels = infer_economic_channels(
        canonical,
        title=record.document.title,
        body=record.document.body,
        llm_channels=llm_channels,
    )

    rule_metrics = extract_metrics_rule_v1(
        record.document.title,
        record.document.body,
        document_id=record.document.document_id,
    )
    fixture_metrics: tuple[ExtractedMetric, ...] = ()
    if structured_metrics is not None:
        fixture_metrics = structured_metrics.get(record.document.document_id, ())

    merged_metrics = _merge_metrics(rule_metrics, fixture_metrics)

    extraction_models: list[str] = []
    if rule_company is not None or rule_metrics or economic_channels:
        extraction_models.append(RULE_MODEL_ID)
    if llm_label is not None:
        extraction_models.append(LLM_MODEL_ID)
    if fixture_metrics:
        extraction_models.append("structured-fixture-v1")

    if not record.document.title and not record.document.body and not merged_metrics:
        quality_flags.append(ContextQualityFlag.NUMERIC_EXTRACTION_UNCERTAIN.value)

    return DocumentExtractionResult(
        document_id=record.document.document_id,
        company_event_type=company_event_type,
        macro_event_type=macro_event_type,
        economic_channels=economic_channels,
        extracted_metrics=merged_metrics,
        extraction_models=tuple(dict.fromkeys(extraction_models)),
        llm_confidence=llm_confidence,
        evidence_span=evidence_span,
        quality_flags=tuple(quality_flags),
    )


def _merge_metrics(
    rule_metrics: tuple[ExtractedMetric, ...],
    fixture_metrics: tuple[ExtractedMetric, ...],
) -> tuple[ExtractedMetric, ...]:
    """Merge rule and fixture metrics; fixture rows override rule rows on same metric_name."""
    by_name: dict[str, ExtractedMetric] = {}
    for metric in rule_metrics:
        if metric.metric_name:
            by_name[metric.metric_name] = metric
    for metric in fixture_metrics:
        if metric.metric_name:
            by_name[metric.metric_name] = metric
    return tuple(by_name.values())


def _aggregate_metrics_for_event(
    document_results: list[DocumentExtractionResult],
    records_by_id: dict[str, ContextDocumentRecord],
) -> tuple[tuple[ExtractedMetric, ...], tuple[str, ...]]:
    """Pick best metrics per metric_name across cluster documents."""
    by_name: dict[str, tuple[ExtractedMetric, int]] = {}
    extra_flags: list[str] = []

    for result in document_results:
        record = records_by_id.get(result.document_id)
        priority = _source_priority(record) if record is not None else 0
        for metric in result.extracted_metrics:
            if not metric.metric_name:
                continue
            existing = by_name.get(metric.metric_name)
            if existing is None:
                by_name[metric.metric_name] = (metric, priority)
                continue
            existing_metric, existing_priority = existing
            if metric.reported_value != existing_metric.reported_value:
                if priority >= existing_priority:
                    by_name[metric.metric_name] = (metric, priority)
                if priority == existing_priority:
                    extra_flags.append(ContextQualityFlag.EXTRACTION_METRIC_CONFLICT.value)
            elif priority > existing_priority:
                by_name[metric.metric_name] = (metric, priority)

    metrics = tuple(item[0] for item in by_name.values())
    return metrics, tuple(dict.fromkeys(extra_flags))


def enrich_information_event(
    event: InformationEvent,
    summary: EventExtractionSummary,
) -> InformationEvent:
    """Rebuild InformationEvent with MC5 extraction fields populated."""
    merged_flags = tuple(
        dict.fromkeys((*event.quality_flags, *summary.quality_flags))
    )
    return InformationEvent(
        event_id=event.event_id,
        canonical_event_type=event.canonical_event_type,
        entity_ids=event.entity_ids,
        document_ids=event.document_ids,
        first_known_time=event.first_known_time,
        first_source_id=event.first_source_id,
        event_time=event.event_time,
        available_time=event.available_time,
        document_count=event.document_count,
        source_count=event.source_count,
        independent_source_count=event.independent_source_count,
        corroboration_state=event.corroboration_state,
        revision_lineage=event.revision_lineage,
        economic_channels=tuple(channel.value for channel in summary.economic_channels),
        extracted_metrics=summary.extracted_metrics,
        publication_state=event.publication_state,
        provenance_ref=event.provenance_ref,
        quality_flags=merged_flags,
    )


def build_event_extraction_summaries(
    events: list[InformationEvent],
    document_results: list[DocumentExtractionResult],
    records: list[ContextDocumentRecord],
) -> list[EventExtractionSummary]:
    """Aggregate per-document extractions into per-event summaries."""
    by_document_id = {item.document_id: item for item in document_results}
    records_by_id = {record.document.document_id: record for record in records}
    summaries: list[EventExtractionSummary] = []

    for event in events:
        cluster_results = [
            by_document_id[document_id]
            for document_id in event.document_ids
            if document_id in by_document_id
        ]
        if not cluster_results:
            continue

        channel_set: dict[EconomicChannel, None] = {}
        model_set: dict[str, None] = {}
        quality_flags: list[str] = []
        company_types: list[CompanyEventType | None] = []
        macro_types: list[MacroEventType | None] = []

        for result in cluster_results:
            for channel in result.economic_channels:
                channel_set[channel] = None
            for model in result.extraction_models:
                model_set[model] = None
            quality_flags.extend(result.quality_flags)
            company_types.append(result.company_event_type)
            macro_types.append(result.macro_event_type)

        metrics, metric_flags = _aggregate_metrics_for_event(cluster_results, records_by_id)
        quality_flags.extend(metric_flags)

        company_event_type = _unanimous_enum(company_types)
        macro_event_type = _unanimous_enum(macro_types)

        summaries.append(
            EventExtractionSummary(
                event_id=event.event_id,
                canonical_event_type=event.canonical_event_type,
                company_event_type=company_event_type,
                macro_event_type=macro_event_type,
                economic_channels=tuple(channel_set.keys()),
                extracted_metrics=metrics,
                extraction_models=tuple(model_set.keys()),
                document_count=len(cluster_results),
                quality_flags=tuple(dict.fromkeys(quality_flags)),
            )
        )

    return summaries


def _unanimous_enum(values: list[Any]) -> Any | None:
    non_null = [value for value in values if value is not None]
    if not non_null:
        return None
    unique = set(non_null)
    if len(unique) == 1:
        return non_null[0]
    return non_null[0]


def enrich_events_with_extraction(
    events: list[InformationEvent],
    summaries: list[EventExtractionSummary],
) -> list[InformationEvent]:
    """Apply MC5 summaries onto MC3 event clusters."""
    summary_by_id = {item.event_id: item for item in summaries}
    enriched: list[InformationEvent] = []
    for event in events:
        summary = summary_by_id.get(event.event_id)
        if summary is None:
            enriched.append(event)
            continue
        enriched.append(enrich_information_event(event, summary))
    return enriched


def build_fixture_extraction_pipeline(
    records: list[ContextDocumentRecord],
    *,
    prediction_cutoff: str | int,
    llm_labels: dict[str, LlmExtractionLabel] | None = None,
    structured_metrics: dict[str, tuple[ExtractedMetric, ...]] | None = None,
) -> tuple[
    list[DocumentExtractionResult],
    list[InformationEvent],
    list[EventExtractionSummary],
]:
    """Run MC3 clustering plus MC5 extraction on fixture records."""
    cutoff_ns = (
        prediction_cutoff
        if isinstance(prediction_cutoff, int)
        else iso_to_epoch_ns(str(prediction_cutoff))
    )
    base_events = cluster_fixture_records(records, prediction_cutoff=cutoff_ns)
    document_results = [
        result
        for record in records
        if (
            result := extract_document(
                record,
                prediction_cutoff=cutoff_ns,
                llm_labels=llm_labels,
                structured_metrics=structured_metrics,
            )
        )
        is not None
    ]
    summaries = build_event_extraction_summaries(base_events, document_results, records)
    enriched_events = enrich_events_with_extraction(base_events, summaries)
    return document_results, enriched_events, summaries


def document_extraction_to_dict(item: DocumentExtractionResult) -> dict[str, Any]:
    return {
        "document_id": item.document_id,
        "company_event_type": item.company_event_type.value if item.company_event_type else None,
        "macro_event_type": item.macro_event_type.value if item.macro_event_type else None,
        "economic_channels": [channel.value for channel in item.economic_channels],
        "extracted_metrics": [extracted_metric_to_dict(metric) for metric in item.extracted_metrics],
        "extraction_models": list(item.extraction_models),
        "llm_confidence": item.llm_confidence,
        "quality_flags": list(item.quality_flags),
    }


def event_extraction_summary_to_dict(item: EventExtractionSummary) -> dict[str, Any]:
    return {
        "event_id": item.event_id,
        "canonical_event_type": item.canonical_event_type,
        "company_event_type": item.company_event_type.value if item.company_event_type else None,
        "macro_event_type": item.macro_event_type.value if item.macro_event_type else None,
        "economic_channels": [channel.value for channel in item.economic_channels],
        "extracted_metrics": [extracted_metric_to_dict(metric) for metric in item.extracted_metrics],
        "extraction_models": list(item.extraction_models),
        "document_count": item.document_count,
        "quality_flags": list(item.quality_flags),
    }


__all__ = [
    "DocumentExtractionResult",
    "EventExtractionSummary",
    "LlmExtractionLabel",
    "PRODUCER_VERSION",
    "build_event_extraction_summaries",
    "build_fixture_extraction_pipeline",
    "document_extraction_to_dict",
    "enrich_events_with_extraction",
    "enrich_information_event",
    "event_extraction_summary_to_dict",
    "extract_document",
    "extract_metrics_rule_v1",
    "infer_economic_channels",
    "load_llm_extraction_fixture",
    "load_structured_metrics_fixture",
    "map_canonical_event_type",
]
