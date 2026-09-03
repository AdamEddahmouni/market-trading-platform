"""MC3 event clustering — deduplication and syndication-aware InformationEvent assembly."""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict

from ..contracts.identity import normalized_event_id
from ..contracts.market_context import (
    ContextQualityFlag,
    CorroborationState,
    InformationEvent,
    PublicationState,
)
from ..normalization.equity_bars import iso_to_epoch_ns
from .entity_resolution import ContextDocumentRecord, PRODUCER_VERSION

_EVENT_TIME_BUCKET_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")
_PROVIDER_ID = "market_context.fixture"
_VENUE_ID = "US_EQUITY"


def _normalize_headline(title: str | None) -> str:
    if not title:
        return ""
    collapsed = re.sub(r"\s+", " ", title.strip().lower())
    return collapsed


def _headline_hash(title: str | None) -> str:
    normalized = _normalize_headline(title)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _event_time_bucket(event_time: str) -> str:
    match = _EVENT_TIME_BUCKET_RE.match(event_time)
    if match:
        return match.group(1)
    return event_time[:10]


def _independent_origin_id(record: ContextDocumentRecord) -> str:
    source = record.document.source
    if source.source_origin_id:
        return source.source_origin_id
    return source.source_id


def _corroboration_state(independent_source_count: int) -> CorroborationState:
    if independent_source_count >= 3:
        return CorroborationState.CORROBORATED
    if independent_source_count == 2:
        return CorroborationState.PARTIALLY_CORROBORATED
    return CorroborationState.UNVERIFIED


def _cluster_key(record: ContextDocumentRecord) -> tuple[str, str, str]:
    primary_entity = (
        record.document.associated_entity_ids[0]
        if record.document.associated_entity_ids
        else "UNRESOLVED"
    )
    return (
        record.canonical_event_type,
        primary_entity,
        _event_time_bucket(record.document.event_time),
    )


def _has_duplicate_headlines(records: list[ContextDocumentRecord]) -> bool:
    hashes = [_headline_hash(record.document.title) for record in records]
    return len(hashes) != len(set(hashes))


def cluster_information_events(
    records: list[ContextDocumentRecord],
    *,
    prediction_cutoff: int,
) -> list[InformationEvent]:
    """Cluster resolved documents into InformationEvent objects."""
    visible_records = [
        record
        for record in records
        if iso_to_epoch_ns(record.document.available_time) <= prediction_cutoff
    ]
    if not visible_records:
        return []

    grouped: dict[tuple[str, str, str], list[ContextDocumentRecord]] = defaultdict(list)
    for record in visible_records:
        grouped[_cluster_key(record)].append(record)

    events: list[InformationEvent] = []
    for cluster_key, cluster_records in grouped.items():
        canonical_event_type, primary_entity_id, event_time_bucket = cluster_key
        if not canonical_event_type:
            continue

        quality_flags: list[str] = []
        if _has_duplicate_headlines(cluster_records):
            quality_flags.append(ContextQualityFlag.EVENT_DUPLICATE.value)

        entity_ids: list[str] = []
        ambiguous = False
        for record in cluster_records:
            if record.entity_resolution.ambiguous:
                ambiguous = True
            if record.entity_resolution.entity_id:
                entity_ids.append(record.entity_resolution.entity_id)
            quality_flags.extend(
                flag
                for flag in record.document.quality_flags
                if flag not in quality_flags
            )

        entity_ids = sorted(set(entity_ids))
        if ambiguous or not entity_ids or primary_entity_id == "UNRESOLVED":
            quality_flags.append(ContextQualityFlag.EVENT_CLUSTER_UNCERTAIN.value)

        document_ids = tuple(
            sorted(record.document.document_id for record in cluster_records)
        )
        source_ids = sorted({record.document.source.source_id for record in cluster_records})
        independent_origins = sorted(
            {_independent_origin_id(record) for record in cluster_records}
        )
        independent_source_count = len(independent_origins)

        event_times = [record.document.event_time for record in cluster_records]
        available_times = [record.document.available_time for record in cluster_records]
        first_record = min(
            cluster_records,
            key=lambda item: (item.document.available_time, item.document.document_id),
        )

        event_id = normalized_event_id(
            provider_id=_PROVIDER_ID,
            venue_id=_VENUE_ID,
            publisher_id=first_record.document.source.source_id,
            channel_id=canonical_event_type,
            source_instance_id=primary_entity_id,
            source_record_id=event_time_bucket,
            source_revision_id=PRODUCER_VERSION,
            event_family="information_event",
        )

        lineage_ids: set[str] = set()
        for record in cluster_records:
            parent_id = record.document.revision_of_document_id
            if parent_id:
                lineage_ids.add(parent_id)
                lineage_ids.add(record.document.document_id)
        revision_lineage = tuple(sorted(lineage_ids))

        events.append(
            InformationEvent(
                event_id=event_id,
                canonical_event_type=canonical_event_type,
                entity_ids=tuple(entity_ids),
                document_ids=document_ids,
                first_known_time=min(available_times),
                first_source_id=first_record.document.source.source_id,
                event_time=min(event_times),
                available_time=max(available_times),
                document_count=len(document_ids),
                source_count=len(source_ids),
                independent_source_count=independent_source_count,
                corroboration_state=_corroboration_state(independent_source_count),
                revision_lineage=revision_lineage,
                publication_state=PublicationState.PUBLISHED,
                provenance_ref=event_id,
                quality_flags=tuple(quality_flags),
            )
        )

    return sorted(events, key=lambda item: (item.event_time, item.canonical_event_type, item.event_id))


def cluster_fixture_records(
    records: list[ContextDocumentRecord],
    *,
    prediction_cutoff: str | int,
) -> list[InformationEvent]:
    cutoff_ns = (
        prediction_cutoff
        if isinstance(prediction_cutoff, int)
        else iso_to_epoch_ns(str(prediction_cutoff))
    )
    return cluster_information_events(records, prediction_cutoff=cutoff_ns)
