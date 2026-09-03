"""MC4 baseline financial sentiment — stdlib keyword baseline + fixture FinBERT labels."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..contracts.market_context import (
    BaselineFinancialSentiment,
    BaselineSentimentModel,
    InformationEvent,
    ModelVersionRef,
    PublicationState,
    SemanticSentimentLabel,
    TargetedSentiment,
)
from ..cross_lane.evidence import (
    EvidenceProvenanceClass,
    EvidenceSignal,
    LaneId,
    NormalizedLaneEvidence,
    lane_evidence_to_dict,
)
from ..normalization.equity_bars import iso_to_epoch_ns
from .entity_resolution import ContextDocumentRecord, PRODUCER_VERSION as ENTITY_PRODUCER_VERSION
from .event_clustering import cluster_fixture_records

PRODUCER_VERSION = "market_context_sentiment_v1"
SENTIMENT_TEXT_MISSING = "SENTIMENT_TEXT_MISSING"
_KEYWORD_MODEL_ID = "keyword-v1"
_KEYWORD_MODEL_VERSION = ModelVersionRef(
    model_id=_KEYWORD_MODEL_ID,
    model_version="1.0.0",
    schema_version="market_context.v1",
    feature_version=PRODUCER_VERSION,
)
_FINBERT_MODEL_VERSION = ModelVersionRef(
    model_id="ProsusAI/finbert",
    model_version="pretrained",
    schema_version="market_context.v1",
    feature_version="finbert_semantic_v1",
)

_POSITIVE_KEYWORDS = frozenset(
    {
        "squeeze",
        "short squeeze",
        "gamma squeeze",
        "moon",
        "rocket",
        "breakout",
        "surge",
        "rally",
        "spike",
        "gap up",
        "upgrade",
        "buyout",
        "acquisition",
        "beat",
        "beat estimates",
        "guidance raise",
        "fda approval",
        "breakthrough",
        "partnership",
        "contract",
        "buyback",
        "repurchase",
        "dividend",
        "positive",
        "profit",
        "record revenue",
        "record high",
        "all time high",
        "new high",
        "green",
        "bull",
        "bullish",
        "outperform",
        "overweight",
        "strong buy",
        "price target raised",
        "clearance",
    }
)

_NEGATIVE_KEYWORDS = frozenset(
    {
        "crash",
        "collapse",
        "plunge",
        "tumble",
        "drop",
        "decline",
        "downgrade",
        "selloff",
        "bankruptcy",
        "chapter 11",
        "layoff",
        "loss",
        "losses",
        "debt",
        "default",
        "delist",
        "delisting",
        "warning",
        "guidance cut",
        "miss",
        "missed estimates",
        "investigation",
        "lawsuit",
        "sec",
        "subpoena",
        "fraud",
        "dilution",
        "offering",
        "share sale",
        "insider sale",
        "red",
        "bear",
        "bearish",
        "underperform",
        "underweight",
        "sell",
        "short",
        "weak",
        "concern",
        "risk",
        "headwind",
        "risk-off",
    }
)

_LABEL_TO_SIGNAL: dict[SemanticSentimentLabel, EvidenceSignal | None] = {
    SemanticSentimentLabel.POSITIVE: EvidenceSignal.SEMANTIC_SENTIMENT_POSITIVE,
    SemanticSentimentLabel.NEGATIVE: EvidenceSignal.SEMANTIC_SENTIMENT_NEGATIVE,
    SemanticSentimentLabel.MIXED: EvidenceSignal.SEMANTIC_SENTIMENT_MIXED,
    SemanticSentimentLabel.NEUTRAL: None,
    SemanticSentimentLabel.UNKNOWN: None,
}


@dataclass(frozen=True, slots=True)
class DocumentSentimentResult:
    """Per-document keyword and optional FinBERT baseline sentiment."""

    document_id: str
    keyword: BaselineFinancialSentiment | None
    finbert: BaselineFinancialSentiment | None
    targeted: TargetedSentiment | None = None


@dataclass(frozen=True, slots=True)
class EventSentimentSummary:
    """Aggregated sentiment for an InformationEvent cluster."""

    event_id: str
    canonical_event_type: str
    keyword: BaselineFinancialSentiment | None
    finbert: BaselineFinancialSentiment | None
    document_count: int


def _normalize_text(title: str | None, body: str | None) -> str:
    parts = [part.strip() for part in (title, body) if part and part.strip()]
    return " ".join(parts).lower()


def _label_from_hits(pos_hits: int, neg_hits: int) -> SemanticSentimentLabel:
    if pos_hits > neg_hits:
        return SemanticSentimentLabel.POSITIVE
    if neg_hits > pos_hits:
        return SemanticSentimentLabel.NEGATIVE
    return SemanticSentimentLabel.MIXED


def _confidence_from_hits(pos_hits: int, neg_hits: int) -> float:
    if pos_hits == neg_hits:
        return 0.5
    return min(0.99, 0.51 + abs(pos_hits - neg_hits) * 0.05)


def _parse_fixture_label(raw: str) -> SemanticSentimentLabel:
    normalized = raw.strip().lower()
    try:
        return SemanticSentimentLabel(normalized)
    except ValueError:
        return SemanticSentimentLabel.UNKNOWN


def score_keyword_baseline(
    title: str | None,
    body: str | None,
    *,
    target_entity_id: str | None = None,
    event_time: str = "",
    available_time: str = "",
    provenance_ref: str = "",
) -> BaselineFinancialSentiment:
    """Score semantic sentiment using stdlib keyword-v1 baseline."""
    text = _normalize_text(title, body)
    if not text:
        return BaselineFinancialSentiment(
            target_entity_id=target_entity_id,
            label=SemanticSentimentLabel.UNKNOWN,
            confidence=None,
            uncertainty_score=1.0,
            model=BaselineSentimentModel.KEYWORD_BASELINE,
            model_version=_KEYWORD_MODEL_VERSION,
            event_time=event_time,
            available_time=available_time,
            publication_state=PublicationState.PUBLISHED,
            provenance_ref=provenance_ref,
            quality_flags=(SENTIMENT_TEXT_MISSING,),
        )

    pos_hits = sum(1 for keyword in _POSITIVE_KEYWORDS if keyword in text)
    neg_hits = sum(1 for keyword in _NEGATIVE_KEYWORDS if keyword in text)
    label = _label_from_hits(pos_hits, neg_hits)
    confidence = _confidence_from_hits(pos_hits, neg_hits)
    uncertainty = max(0.0, min(1.0, 1.0 - confidence))

    return BaselineFinancialSentiment(
        target_entity_id=target_entity_id,
        label=label,
        confidence=round(confidence, 4),
        uncertainty_score=round(uncertainty, 4),
        model=BaselineSentimentModel.KEYWORD_BASELINE,
        model_version=_KEYWORD_MODEL_VERSION,
        event_time=event_time,
        available_time=available_time,
        publication_state=PublicationState.PUBLISHED,
        provenance_ref=provenance_ref,
        quality_flags=(),
    )


def load_finbert_fixture_labels(
    path: str | Path,
) -> dict[str, BaselineFinancialSentiment]:
    """Load precomputed FinBERT labels from an admitted fixture slice."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    labels = payload.get("labels", [])
    if not isinstance(labels, list):
        return {}

    result: dict[str, BaselineFinancialSentiment] = {}
    for row in labels:
        if not isinstance(row, dict):
            continue
        document_id = str(row.get("document_id", "")).strip()
        if not document_id:
            continue
        label = _parse_fixture_label(str(row.get("label", "unknown")))
        confidence_raw = row.get("confidence")
        confidence = float(confidence_raw) if confidence_raw is not None else None
        uncertainty = None if confidence is None else max(0.0, min(1.0, 1.0 - confidence))
        result[document_id] = BaselineFinancialSentiment(
            target_entity_id=row.get("target_entity_id"),
            label=label,
            confidence=confidence,
            uncertainty_score=uncertainty,
            model=BaselineSentimentModel.FINBERT_BASELINE,
            model_version=_FINBERT_MODEL_VERSION,
            event_time=str(row.get("event_time", "")),
            available_time=str(row.get("available_time", "")),
            publication_state=PublicationState.PUBLISHED,
            provenance_ref=f"finbert.fixture:{document_id}",
            quality_flags=tuple(row.get("quality_flags", [])),
        )
    return result


def _pit_visible(record: ContextDocumentRecord, prediction_cutoff: int) -> bool:
    return iso_to_epoch_ns(record.document.available_time) <= prediction_cutoff


def score_document_sentiment(
    record: ContextDocumentRecord,
    *,
    prediction_cutoff: int,
    finbert_labels: dict[str, BaselineFinancialSentiment] | None = None,
) -> DocumentSentimentResult | None:
    """Score keyword (+ optional FinBERT) sentiment for one document."""
    if not _pit_visible(record, prediction_cutoff):
        return None

    document = record.document
    entity_id = record.entity_resolution.entity_id
    keyword = score_keyword_baseline(
        document.title,
        document.body,
        target_entity_id=entity_id,
        event_time=document.event_time,
        available_time=document.available_time,
        provenance_ref=document.document_id,
    )
    finbert = None
    if finbert_labels is not None:
        finbert = finbert_labels.get(document.document_id)
        if finbert is not None and entity_id and finbert.target_entity_id is None:
            finbert = BaselineFinancialSentiment(
                target_entity_id=entity_id,
                label=finbert.label,
                confidence=finbert.confidence,
                uncertainty_score=finbert.uncertainty_score,
                model=finbert.model,
                model_version=finbert.model_version,
                source_span=finbert.source_span,
                event_time=finbert.event_time or document.event_time,
                available_time=finbert.available_time or document.available_time,
                publication_state=finbert.publication_state,
                provenance_ref=finbert.provenance_ref,
                quality_flags=finbert.quality_flags,
            )

    targeted = None
    if entity_id and keyword.label != SemanticSentimentLabel.UNKNOWN:
        targeted = TargetedSentiment(
            entity_id=entity_id,
            label=keyword.label,
            confidence=keyword.confidence,
            uncertainty_score=keyword.uncertainty_score,
            direction_rationale="keyword-v1 lexical baseline",
            model_version=_KEYWORD_MODEL_VERSION,
            quality_flags=keyword.quality_flags,
        )

    return DocumentSentimentResult(
        document_id=document.document_id,
        keyword=keyword,
        finbert=finbert,
        targeted=targeted,
    )


def aggregate_event_sentiment(
    sentiments: tuple[BaselineFinancialSentiment, ...],
    *,
    event_id: str,
    canonical_event_type: str,
    model: BaselineSentimentModel,
    model_version: ModelVersionRef,
    event_time: str,
    available_time: str,
    target_entity_id: str | None,
) -> BaselineFinancialSentiment | None:
    """Aggregate document-level baselines into one event-level baseline."""
    if not sentiments:
        return None

    labels = [item.label for item in sentiments]
    unique_labels = set(labels)
    if len(unique_labels) == 1:
        aggregate_label = labels[0]
    else:
        aggregate_label = SemanticSentimentLabel.MIXED

    confidences = [item.confidence for item in sentiments if item.confidence is not None]
    aggregate_confidence = (
        round(sum(confidences) / len(confidences), 4) if confidences else None
    )
    uncertainty = (
        None
        if aggregate_confidence is None
        else round(max(0.0, min(1.0, 1.0 - aggregate_confidence)), 4)
    )

    return BaselineFinancialSentiment(
        target_entity_id=target_entity_id,
        label=aggregate_label,
        confidence=aggregate_confidence,
        uncertainty_score=uncertainty,
        model=model,
        model_version=model_version,
        event_time=event_time,
        available_time=available_time,
        publication_state=PublicationState.PUBLISHED,
        provenance_ref=event_id,
        quality_flags=(),
    )


def build_event_sentiment_summaries(
    events: list[InformationEvent],
    document_results: list[DocumentSentimentResult],
) -> list[EventSentimentSummary]:
    """Aggregate per-document sentiment into per-event summaries."""
    by_document_id = {item.document_id: item for item in document_results}
    summaries: list[EventSentimentSummary] = []

    for event in events:
        keyword_rows: list[BaselineFinancialSentiment] = []
        finbert_rows: list[BaselineFinancialSentiment] = []
        for document_id in event.document_ids:
            result = by_document_id.get(document_id)
            if result is None:
                continue
            if result.keyword is not None:
                keyword_rows.append(result.keyword)
            if result.finbert is not None:
                finbert_rows.append(result.finbert)

        target_entity_id = event.entity_ids[0] if event.entity_ids else None
        keyword = aggregate_event_sentiment(
            tuple(keyword_rows),
            event_id=event.event_id,
            canonical_event_type=event.canonical_event_type,
            model=BaselineSentimentModel.KEYWORD_BASELINE,
            model_version=_KEYWORD_MODEL_VERSION,
            event_time=event.event_time,
            available_time=event.available_time,
            target_entity_id=target_entity_id,
        )
        finbert = aggregate_event_sentiment(
            tuple(finbert_rows),
            event_id=event.event_id,
            canonical_event_type=event.canonical_event_type,
            model=BaselineSentimentModel.FINBERT_BASELINE,
            model_version=_FINBERT_MODEL_VERSION,
            event_time=event.event_time,
            available_time=event.available_time,
            target_entity_id=target_entity_id,
        )
        summaries.append(
            EventSentimentSummary(
                event_id=event.event_id,
                canonical_event_type=event.canonical_event_type,
                keyword=keyword,
                finbert=finbert,
                document_count=len(event.document_ids),
            )
        )

    return summaries


def build_fixture_sentiment_pipeline(
    records: list[ContextDocumentRecord],
    *,
    prediction_cutoff: str | int,
    finbert_labels: dict[str, BaselineFinancialSentiment] | None = None,
) -> tuple[list[DocumentSentimentResult], list[InformationEvent], list[EventSentimentSummary]]:
    """Run MC3 clustering plus MC4 sentiment scoring on fixture records."""
    cutoff_ns = (
        prediction_cutoff
        if isinstance(prediction_cutoff, int)
        else iso_to_epoch_ns(str(prediction_cutoff))
    )
    events = cluster_fixture_records(records, prediction_cutoff=cutoff_ns)
    document_results = [
        result
        for record in records
        if (result := score_document_sentiment(
            record,
            prediction_cutoff=cutoff_ns,
            finbert_labels=finbert_labels,
        ))
        is not None
    ]
    event_summaries = build_event_sentiment_summaries(events, document_results)
    return document_results, events, event_summaries


def build_sentiment_cross_lane_evidence(
    event_summaries: list[EventSentimentSummary],
    *,
    symbol: str,
    prediction_cutoff: int,
) -> list[dict[str, Any]]:
    """Publish display-only semantic sentiment evidence (no SHARED P4 fusion)."""
    evidence: list[dict[str, Any]] = []
    for summary in event_summaries:
        sentiment = summary.keyword
        if sentiment is None:
            continue
        signal = _LABEL_TO_SIGNAL.get(sentiment.label)
        if signal is None:
            continue
        if iso_to_epoch_ns(sentiment.available_time) > prediction_cutoff:
            continue
        strength = "LOW"
        if sentiment.confidence is not None:
            if sentiment.confidence >= 0.7:
                strength = "HIGH"
            elif sentiment.confidence >= 0.55:
                strength = "MODERATE"
        item = NormalizedLaneEvidence(
            lane=LaneId.MARKET_CONTEXT,
            signal=signal,
            strength=strength,
            available=True,
            source_ref=summary.event_id,
            detail=(
                f"BaselineFinancialSentiment ({sentiment.model.value}) "
                f"for {summary.canonical_event_type}: {sentiment.label.value} "
                f"(display-only, not trade signal)"
            ),
            observed_at=sentiment.available_time,
            quality_flags=sentiment.quality_flags,
            provenance_class=EvidenceProvenanceClass.MODEL_OUTPUT,
        )
        row = lane_evidence_to_dict(item)
        row["metadata"] = {
            "canonical_event_type": summary.canonical_event_type,
            "model": sentiment.model.value,
            "label": sentiment.label.value,
            "document_count": summary.document_count,
            "display_only": True,
            "instrument_id": symbol.upper(),
            "producer_id": "market_context.sentiment",
            "producer_version": PRODUCER_VERSION,
        }
        evidence.append(row)
    return evidence


__all__ = [
    "ENTITY_PRODUCER_VERSION",
    "DocumentSentimentResult",
    "EventSentimentSummary",
    "PRODUCER_VERSION",
    "SENTIMENT_TEXT_MISSING",
    "aggregate_event_sentiment",
    "build_event_sentiment_summaries",
    "build_fixture_sentiment_pipeline",
    "build_sentiment_cross_lane_evidence",
    "load_finbert_fixture_labels",
    "score_document_sentiment",
    "score_keyword_baseline",
]
