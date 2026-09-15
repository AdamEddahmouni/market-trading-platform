"""Diagnostic catalog of next-RTH source→operator clocks.

Read-only: maps existing EventV1 / news / detection / opportunity / DecisionTrace
fields onto hops. Never zero-fills missing clocks. Does not emit production
telemetry or mutate contracts.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

from market_platform_foundation.intelligence.contracts.detection import DetectionV1
from market_platform_foundation.intelligence.contracts.event import EventV1
from market_platform_foundation.intelligence.contracts.opportunity import OpportunityV1
from market_platform_foundation.news.contracts import NewsArticleEvent, PublicationTimeQuality
from market_platform_foundation.news.timestamps import epoch_ns_from_iso
from market_platform_foundation.rt01.execution_decision_trace.types import ExecutionDecisionTraceV1


class HopClassification(StrEnum):
    AVAILABLE = "AVAILABLE"
    DERIVABLE = "DERIVABLE"
    MISSING = "MISSING"
    AMBIGUOUS = "AMBIGUOUS"


class HopId(StrEnum):
    SOURCE_PUBLICATION = "source_publication"
    PROVIDER_RETRIEVAL = "provider_retrieval"
    IMP_RECEIVE = "imp_receive"
    NORMALIZATION = "normalization"
    DETECTOR = "detector"
    OPPORTUNITY_CREATION = "opportunity_creation"
    RANKED_BOOK = "ranked_book"
    API_RESPONSE = "api_response"
    UI_FIRST_VISIBLE = "ui_first_visible"
    OPERATOR_ACTION = "operator_action"


class DeltaId(StrEnum):
    SOURCE_TO_RECEIVE = "source_to_receive"
    RECEIVE_TO_NORMALIZATION = "receive_to_normalization"
    NORMALIZATION_TO_DETECTOR = "normalization_to_detector"
    DETECTOR_TO_OPPORTUNITY = "detector_to_opportunity"
    OPPORTUNITY_TO_UI = "opportunity_to_ui"
    UI_TO_OPERATOR = "ui_to_operator"
    SOURCE_TO_OPERATOR = "source_to_operator"


@dataclass(frozen=True, slots=True)
class HopCatalogEntry:
    hop_id: HopId
    classification: HopClassification
    existing_fields: tuple[str, ...]
    notes: str


HOP_CATALOG: tuple[HopCatalogEntry, ...] = (
    HopCatalogEntry(
        hop_id=HopId.SOURCE_PUBLICATION,
        classification=HopClassification.AVAILABLE,
        existing_fields=(
            "NewsArticleEvent.published_time",
            "NewsArticleEvent.published_time_quality",
            "EventV1.event_time_ns",
        ),
        notes=(
            "News publication is AVAILABLE when quality is KNOWN. EventV1.event_time_ns is "
            "AMBIGUOUS (economic event vs discovery time). No news→EventV1 mapper on origin/main."
        ),
    ),
    HopCatalogEntry(
        hop_id=HopId.PROVIDER_RETRIEVAL,
        classification=HopClassification.AMBIGUOUS,
        existing_fields=(
            "NewsArticleEvent.retrieved_time",
            "aggregator.received_time",
            "EventV1.provider_time_ns",
        ),
        notes="Pull adapters stamp HTTP completion; provider_time_ns often copies event_time_ns.",
    ),
    HopCatalogEntry(
        hop_id=HopId.IMP_RECEIVE,
        classification=HopClassification.AVAILABLE,
        existing_fields=(
            "EventV1.received_time_ns",
            "NormalizationContext.received_time_ns",
            "NewsArticleEvent.retrieved_time",
        ),
        notes="Distinct on BUILD 03. On pull news, same instant as retrieved_time.",
    ),
    HopCatalogEntry(
        hop_id=HopId.NORMALIZATION,
        classification=HopClassification.AMBIGUOUS,
        existing_fields=(
            "EventV1.available_time_ns",
            "ProviderProvenance.availability",
            "HotPathClockRow.normalized_at",
        ),
        notes="available_time_ns is PIT eligibility, not adapter completion; collector currently aliases it.",
    ),
    HopCatalogEntry(
        hop_id=HopId.DETECTOR,
        classification=HopClassification.AMBIGUOUS,
        existing_fields=("DetectionV1.detected_at_ns",),
        notes="detected_at_ns is snapshot.decision_time_ns, not detector wall-clock.",
    ),
    HopCatalogEntry(
        hop_id=HopId.OPPORTUNITY_CREATION,
        classification=HopClassification.AMBIGUOUS,
        existing_fields=("OpportunityV1.created_at_ns",),
        notes="created_at_ns is opportunity_decision_time_ns, not mint wall-clock.",
    ),
    HopCatalogEntry(
        hop_id=HopId.RANKED_BOOK,
        classification=HopClassification.MISSING,
        existing_fields=("OpportunitySummary.rank_order",),
        notes="rank_review_rows has no ranked_at_ns.",
    ),
    HopCatalogEntry(
        hop_id=HopId.API_RESPONSE,
        classification=HopClassification.MISSING,
        existing_fields=("as_of_context.as_of_time",),
        notes="as_of is store as-of, not HTTP generated_at. Serialize monotonic is not in the payload.",
    ),
    HopCatalogEntry(
        hop_id=HopId.UI_FIRST_VISIBLE,
        classification=HopClassification.MISSING,
        existing_fields=(),
        notes="No client first-visible / first-paint clock on opportunity rows.",
    ),
    HopCatalogEntry(
        hop_id=HopId.OPERATOR_ACTION,
        classification=HopClassification.AMBIGUOUS,
        existing_fields=(
            "opportunity_operator_acks.created_at_ns",
            "ExecutionDecisionTraceV1.decision_time_ns",
        ),
        notes="Ack uses as_of_time_ns which as_of_context does not currently emit (often 0).",
    ),
)


DELTA_CATALOG: dict[DeltaId, tuple[HopId, HopId, HopClassification]] = {
    DeltaId.SOURCE_TO_RECEIVE: (
        HopId.SOURCE_PUBLICATION,
        HopId.IMP_RECEIVE,
        HopClassification.DERIVABLE,
    ),
    DeltaId.RECEIVE_TO_NORMALIZATION: (
        HopId.IMP_RECEIVE,
        HopId.NORMALIZATION,
        HopClassification.AMBIGUOUS,
    ),
    DeltaId.NORMALIZATION_TO_DETECTOR: (
        HopId.NORMALIZATION,
        HopId.DETECTOR,
        HopClassification.AMBIGUOUS,
    ),
    DeltaId.DETECTOR_TO_OPPORTUNITY: (
        HopId.DETECTOR,
        HopId.OPPORTUNITY_CREATION,
        HopClassification.AMBIGUOUS,
    ),
    DeltaId.OPPORTUNITY_TO_UI: (
        HopId.OPPORTUNITY_CREATION,
        HopId.UI_FIRST_VISIBLE,
        HopClassification.MISSING,
    ),
    DeltaId.UI_TO_OPERATOR: (
        HopId.UI_FIRST_VISIBLE,
        HopId.OPERATOR_ACTION,
        HopClassification.MISSING,
    ),
    DeltaId.SOURCE_TO_OPERATOR: (
        HopId.SOURCE_PUBLICATION,
        HopId.OPERATOR_ACTION,
        HopClassification.AMBIGUOUS,
    ),
}


@dataclass(frozen=True, slots=True)
class HopClockSnapshot:
    """Optional per-correlation clocks. Missing stays None."""

    source_publication_ns: int | None = None
    provider_retrieval_ns: int | None = None
    imp_receive_ns: int | None = None
    normalization_ns: int | None = None
    detector_ns: int | None = None
    opportunity_created_ns: int | None = None
    ranked_book_ns: int | None = None
    api_response_ns: int | None = None
    ui_first_visible_ns: int | None = None
    operator_action_ns: int | None = None

    def as_hop_map(self) -> dict[HopId, int | None]:
        return {
            HopId.SOURCE_PUBLICATION: self.source_publication_ns,
            HopId.PROVIDER_RETRIEVAL: self.provider_retrieval_ns,
            HopId.IMP_RECEIVE: self.imp_receive_ns,
            HopId.NORMALIZATION: self.normalization_ns,
            HopId.DETECTOR: self.detector_ns,
            HopId.OPPORTUNITY_CREATION: self.opportunity_created_ns,
            HopId.RANKED_BOOK: self.ranked_book_ns,
            HopId.API_RESPONSE: self.api_response_ns,
            HopId.UI_FIRST_VISIBLE: self.ui_first_visible_ns,
            HopId.OPERATOR_ACTION: self.operator_action_ns,
        }


def hop_classification(hop_id: HopId | str) -> HopCatalogEntry:
    key = HopId(str(hop_id))
    for entry in HOP_CATALOG:
        if entry.hop_id == key:
            return entry
    raise KeyError(hop_id)


def classification_table() -> tuple[dict[str, str], ...]:
    return tuple(
        {
            "hop": entry.hop_id.value,
            "classification": entry.classification.value,
            "existing_fields": ",".join(entry.existing_fields),
            "notes": entry.notes,
        }
        for entry in HOP_CATALOG
    )


def _positive_delta(left: int | None, right: int | None) -> int | None:
    if left is None or right is None:
        return None
    delta = int(right) - int(left)
    if delta < 0:
        return None
    return delta


def compute_next_rth_deltas(snapshot: HopClockSnapshot) -> dict[str, dict[str, Any]]:
    """Compute target deltas. Missing or inverted pairs stay missing (never 0-fill)."""

    clocks = snapshot.as_hop_map()
    body: dict[str, dict[str, Any]] = {}
    for delta_id, (left_hop, right_hop, klass) in DELTA_CATALOG.items():
        sample = _positive_delta(clocks[left_hop], clocks[right_hop])
        body[delta_id.value] = {
            "classification": klass.value,
            "left_hop": left_hop.value,
            "right_hop": right_hop.value,
            "delta_ns": sample,
            "pair_present": sample is not None,
        }
    return body


def snapshot_from_news_article(event: NewsArticleEvent) -> HopClockSnapshot:
    published_ns = None
    if event.published_time_quality == PublicationTimeQuality.KNOWN:
        published_ns = epoch_ns_from_iso(event.published_time)
    return HopClockSnapshot(
        source_publication_ns=published_ns,
        provider_retrieval_ns=None,
        imp_receive_ns=epoch_ns_from_iso(event.retrieved_time),
    )


def snapshot_from_event_v1(event: EventV1) -> HopClockSnapshot:
    return HopClockSnapshot(
        source_publication_ns=event.event_time_ns,
        provider_retrieval_ns=event.provider_time_ns,
        imp_receive_ns=event.received_time_ns,
        normalization_ns=event.available_time_ns,
    )


def snapshot_from_detection(detection: DetectionV1) -> HopClockSnapshot:
    return HopClockSnapshot(detector_ns=detection.detected_at_ns)


def snapshot_from_opportunity(opportunity: OpportunityV1) -> HopClockSnapshot:
    return HopClockSnapshot(opportunity_created_ns=opportunity.created_at_ns)


def snapshot_from_decision_trace(trace: ExecutionDecisionTraceV1) -> HopClockSnapshot:
    return HopClockSnapshot(operator_action_ns=trace.decision_time_ns)


def merge_snapshots(*rows: HopClockSnapshot) -> HopClockSnapshot:
    """First non-None wins per hop. Does not invent values."""

    merged: dict[str, int | None] = {key.value: None for key in HopId}
    for row in rows:
        payload = row.as_hop_map()
        for hop, value in payload.items():
            if merged[hop.value] is None and value is not None:
                merged[hop.value] = value
    return HopClockSnapshot(
        source_publication_ns=merged[HopId.SOURCE_PUBLICATION.value],
        provider_retrieval_ns=merged[HopId.PROVIDER_RETRIEVAL.value],
        imp_receive_ns=merged[HopId.IMP_RECEIVE.value],
        normalization_ns=merged[HopId.NORMALIZATION.value],
        detector_ns=merged[HopId.DETECTOR.value],
        opportunity_created_ns=merged[HopId.OPPORTUNITY_CREATION.value],
        ranked_book_ns=merged[HopId.RANKED_BOOK.value],
        api_response_ns=merged[HopId.API_RESPONSE.value],
        ui_first_visible_ns=merged[HopId.UI_FIRST_VISIBLE.value],
        operator_action_ns=merged[HopId.OPERATOR_ACTION.value],
    )


def event_v1_clocks_are_eligibility_not_processing(event: EventV1) -> bool:
    """True when available_time aliases receive — not a measured normalize hop."""

    if event.received_time_ns is None:
        return False
    return event.available_time_ns == event.received_time_ns


def ack_created_at_is_usable(created_at_ns: int | None) -> bool:
    return created_at_ns is not None and int(created_at_ns) > 0


def patch_plan() -> Mapping[str, tuple[str, ...]]:
    """Minimal next-RTH plan. Schema rows are P1; this lane must not apply them."""

    return {
        "wiring_no_schema": (
            "Map NewsArticleEvent.published_time (KNOWN only) to HotPathClockRow.source_event_at",
            "Map retrieved_time / EventV1.received_time_ns to imp_received_at",
            "Stamp collector normalized_at with wall_time_ns at adapter return; do not alias available_time_ns",
            "Join DetectionV1.source_event_refs and OpportunityV1.lineage_refs; never first-row merge",
            "Label API serialize operator_surfaced_at as OPERATOR_SURFACED_API_SERIALIZE, not UI first-visible",
        ),
        "p1_schema_do_not_edit": (
            "EventV1.normalized_at_ns / processed_at (optional) — P1 EventV1",
            "News→EventV1 mapper clock mapping — other lane",
            "ranked_at_ns / generated_at_ns on /opportunities/summary — P1 API schema",
            "UI first_visible_at_ns — P1 UI",
            "opportunity_projections.apply_opportunity_ack wall-clock created_at_ns — other lane",
        ),
        "forbidden": (
            "Do not edit frozen RTH artifacts",
            "Do not add a telemetry backend or per-tick provenance write",
            "Do not zero-fill missing hop pairs",
        ),
    }


__all__ = [
    "DELTA_CATALOG",
    "DeltaId",
    "HOP_CATALOG",
    "HopCatalogEntry",
    "HopClassification",
    "HopClockSnapshot",
    "HopId",
    "ack_created_at_is_usable",
    "classification_table",
    "compute_next_rth_deltas",
    "event_v1_clocks_are_eligibility_not_processing",
    "hop_classification",
    "merge_snapshots",
    "patch_plan",
    "snapshot_from_decision_trace",
    "snapshot_from_detection",
    "snapshot_from_event_v1",
    "snapshot_from_news_article",
    "snapshot_from_opportunity",
]
