"""MC16 multi-document LLM synthesis — separate cluster fields, PIT-safe, fail-closed."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..contracts.market_context import (
    CompanyEventType,
    ContextQualityFlag,
    EconomicChannel,
    InformationEvent,
    ModelVersionRef,
    PublicationState,
)
from ..cross_lane.evidence import (
    EvidenceProvenanceClass,
    EvidenceSignal,
    LaneId,
    NormalizedLaneEvidence,
    lane_evidence_to_dict,
)
from ..normalization.equity_bars import iso_to_epoch_ns
from .entity_resolution import ContextDocumentRecord
from .extraction import LlmExtractionLabel

PRODUCER_VERSION = "market_context_multi_document_synthesis_v1"
SCORING_METHOD = "multi_document_synthesis_v1"
SYNTHESIS_MODEL_ID = "fixture-llm-synthesis-v1"
NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

THEME_AGREEMENT_ELEVATED_THRESHOLD = 0.75
LLM_CONFIDENCE_THRESHOLD = 0.70

DEFAULT_SYNTHESIS_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "market_context"
    / "boxl_multidoc_synthesis_slice.json"
)
DEFAULT_SYNTHESIS_EXPECTED = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "market_context"
    / "boxl_multidoc_synthesis_expected.json"
)
DEFAULT_RAW_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "market_context"
    / "boxl_raw_documents_slice.json"
)
DEFAULT_LLM_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "market_context"
    / "boxl_llm_extraction_slice.json"
)
GATE_PREDICTION_CUTOFF = "2026-07-23T00:00:00.000000000Z"
GATE_EARLY_CUTOFF = "2026-07-22T12:00:00.000000000Z"
GATE_REVISION_CUTOFF = "2026-07-23T12:00:00.000000000Z"

_SYNTHESIS_MODEL_VERSION = ModelVersionRef(
    model_id=SYNTHESIS_MODEL_ID,
    model_version="1.0.0",
    prompt_version="mc16_synthesis_prompt_v1",
    schema_version="mc16_synthesis_schema_v1",
    feature_version="market_context_synthesis_v1",
)

_INCOMPATIBLE_EVENT_TYPES: frozenset[frozenset[str]] = frozenset(
    {
        frozenset({CompanyEventType.EARNINGS.value, CompanyEventType.EQUITY_ISSUANCE.value}),
        frozenset({CompanyEventType.EARNINGS.value, CompanyEventType.FDA_APPROVAL.value}),
        frozenset({CompanyEventType.ANALYST_UPGRADE.value, CompanyEventType.EQUITY_ISSUANCE.value}),
    }
)

_CHANNEL_OPPOSITES: dict[str, str] = {
    EconomicChannel.REVENUE_UP.value: EconomicChannel.REVENUE_DOWN.value,
    EconomicChannel.REVENUE_DOWN.value: EconomicChannel.REVENUE_UP.value,
    EconomicChannel.MARGIN_UP.value: EconomicChannel.MARGIN_DOWN.value,
    EconomicChannel.MARGIN_DOWN.value: EconomicChannel.MARGIN_UP.value,
    EconomicChannel.REGULATORY_RISK_UP.value: EconomicChannel.REGULATORY_RISK_DOWN.value,
    EconomicChannel.REGULATORY_RISK_DOWN.value: EconomicChannel.REGULATORY_RISK_UP.value,
    EconomicChannel.DEMAND_UP.value: EconomicChannel.DEMAND_DOWN.value,
    EconomicChannel.DEMAND_DOWN.value: EconomicChannel.DEMAND_UP.value,
    EconomicChannel.COST_UP.value: EconomicChannel.COST_DOWN.value,
    EconomicChannel.COST_DOWN.value: EconomicChannel.COST_UP.value,
    EconomicChannel.LIQUIDITY_RISK_UP.value: EconomicChannel.LIQUIDITY_RISK_DOWN.value,
    EconomicChannel.LIQUIDITY_RISK_DOWN.value: EconomicChannel.LIQUIDITY_RISK_UP.value,
    EconomicChannel.UNCERTAINTY_UP.value: EconomicChannel.UNCERTAINTY_DOWN.value,
    EconomicChannel.UNCERTAINTY_DOWN.value: EconomicChannel.UNCERTAINTY_UP.value,
    EconomicChannel.DILUTION_UP.value: EconomicChannel.DILUTION_UP.value,
}


@dataclass(frozen=True, slots=True)
class SynthesisFixtureLabel:
    cluster_id: str
    thematic_summary: str | None
    synthesis_confidence: float | None
    model_version: ModelVersionRef


@dataclass(frozen=True, slots=True)
class ExtractionOverride:
    document_id: str
    company_event_type: str | None
    economic_channels: tuple[str, ...]
    confidence: float | None


@dataclass(frozen=True, slots=True)
class AdversarialCluster:
    cluster_id: str
    document_ids: tuple[str, ...]
    extraction_overrides: tuple[ExtractionOverride, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class SynthesisFixturePayload:
    synthesis_labels: dict[str, SynthesisFixtureLabel]
    adversarial_clusters: tuple[AdversarialCluster, ...]
    extraction_overrides: tuple[ExtractionOverride, ...]


@dataclass(frozen=True, slots=True)
class MultiDocumentSynthesisSummary:
    synthesis_id: str
    cluster_id: str
    entity_id: str
    thematic_summary: str | None
    theme_agreement_score: float | None
    contradiction_detected: bool
    consolidated_channels: tuple[str, ...]
    supporting_document_ids: tuple[str, ...]
    contradicting_document_ids: tuple[str, ...]
    revision_superseded_ids: tuple[str, ...]
    synthesis_confidence: float | None
    model_version: ModelVersionRef
    quality_flags: tuple[str, ...]
    available_time: str
    publication_state: str


def synthesis_id_from_parts(
    *,
    cluster_id: str,
    entity_id: str,
    prediction_cutoff_ns: int,
) -> str:
    normalized = "|".join(
        ("synthesis", cluster_id, entity_id.strip().upper(), str(prediction_cutoff_ns))
    )
    return str(uuid.uuid5(NAMESPACE, normalized))


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _model_version_from_row(row: dict[str, Any]) -> ModelVersionRef:
    return ModelVersionRef(
        model_id=str(row.get("model_id", SYNTHESIS_MODEL_ID)),
        model_version=str(row.get("model_version", "1.0.0")),
        prompt_version=row.get("prompt_version"),
        schema_version=str(row.get("schema_version", "mc16_synthesis_schema_v1")),
        feature_version=str(
            row.get("feature_version", "market_context_synthesis_v1")
        ),
    )


def model_version_to_dict(item: ModelVersionRef) -> dict[str, Any]:
    return {
        "model_id": item.model_id,
        "model_version": item.model_version,
        "prompt_version": item.prompt_version,
        "schema_version": item.schema_version,
        "feature_version": item.feature_version,
    }


def _parse_extraction_override(row: dict[str, Any]) -> ExtractionOverride | None:
    if not isinstance(row, dict):
        return None
    document_id = str(row.get("document_id", "")).strip()
    if not document_id:
        return None
    channels_raw = row.get("economic_channels") or []
    channels = tuple(str(item) for item in channels_raw) if isinstance(channels_raw, list) else ()
    company_event_type = row.get("company_event_type")
    return ExtractionOverride(
        document_id=document_id,
        company_event_type=str(company_event_type) if company_event_type else None,
        economic_channels=channels,
        confidence=_optional_float(row.get("confidence")),
    )


def load_synthesis_fixture(path: Path) -> SynthesisFixturePayload:
    payload = json.loads(path.read_text(encoding="utf-8"))
    labels: dict[str, SynthesisFixtureLabel] = {}
    labels_payload = payload.get("synthesis_labels", [])
    if isinstance(labels_payload, list):
        for row in labels_payload:
            if not isinstance(row, dict):
                continue
            cluster_id = str(row.get("cluster_id", "")).strip()
            if not cluster_id:
                continue
            labels[cluster_id] = SynthesisFixtureLabel(
                cluster_id=cluster_id,
                thematic_summary=(
                    str(row["thematic_summary"]) if row.get("thematic_summary") else None
                ),
                synthesis_confidence=_optional_float(row.get("synthesis_confidence")),
                model_version=_model_version_from_row(row),
            )

    adversarial: list[AdversarialCluster] = []
    adversarial_payload = payload.get("adversarial_clusters", [])
    if isinstance(adversarial_payload, list):
        for row in adversarial_payload:
            if not isinstance(row, dict):
                continue
            cluster_id = str(row.get("cluster_id", "")).strip()
            doc_ids_raw = row.get("document_ids", [])
            if not cluster_id or not isinstance(doc_ids_raw, list):
                continue
            overrides_raw = row.get("extraction_overrides", [])
            overrides: list[ExtractionOverride] = []
            if isinstance(overrides_raw, list):
                for override_row in overrides_raw:
                    override = _parse_extraction_override(override_row)
                    if override is not None:
                        overrides.append(override)
            adversarial.append(
                AdversarialCluster(
                    cluster_id=cluster_id,
                    document_ids=tuple(str(item) for item in doc_ids_raw),
                    extraction_overrides=tuple(overrides),
                )
            )

    global_overrides: list[ExtractionOverride] = []
    overrides_payload = payload.get("extraction_overrides", [])
    if isinstance(overrides_payload, list):
        for row in overrides_payload:
            override = _parse_extraction_override(row)
            if override is not None:
                global_overrides.append(override)

    return SynthesisFixturePayload(
        synthesis_labels=labels,
        adversarial_clusters=tuple(adversarial),
        extraction_overrides=tuple(global_overrides),
    )


def _records_by_id(records: list[ContextDocumentRecord]) -> dict[str, ContextDocumentRecord]:
    return {record.document.document_id: record for record in records}


def _lineage_root(document_id: str, records_by_id: dict[str, ContextDocumentRecord]) -> str:
    current = document_id
    seen: set[str] = set()
    while True:
        if current in seen:
            return document_id
        seen.add(current)
        record = records_by_id.get(current)
        if record is None:
            return current
        parent = record.document.revision_of_document_id
        if not parent:
            return current
        current = parent


def _lineage_members(
    document_id: str,
    records_by_id: dict[str, ContextDocumentRecord],
) -> set[str]:
    root = _lineage_root(document_id, records_by_id)
    members: set[str] = set()
    for doc_id, record in records_by_id.items():
        if _lineage_root(doc_id, records_by_id) == root:
            members.add(doc_id)
    return members


def _labels_disagree(
  label_a: LlmExtractionLabel,
  label_b: LlmExtractionLabel,
) -> bool:
    type_a = label_a.company_event_type.value if label_a.company_event_type else None
    type_b = label_b.company_event_type.value if label_b.company_event_type else None
    if type_a and type_b and type_a != type_b:
        return True
    channels_a = {channel.value for channel in label_a.economic_channels}
    channels_b = {channel.value for channel in label_b.economic_channels}
    for channel in channels_a:
        opposite = _CHANNEL_OPPOSITES.get(channel)
        if opposite and opposite in channels_b:
            return True
    return False


def _apply_extraction_overrides(
    llm_labels: dict[str, LlmExtractionLabel],
    overrides: tuple[ExtractionOverride, ...],
) -> dict[str, LlmExtractionLabel]:
    merged = dict(llm_labels)
    for override in overrides:
        base = merged.get(override.document_id)
        company_type = None
        if override.company_event_type:
            for item in CompanyEventType:
                if item.value == override.company_event_type.upper():
                    company_type = item
                    break
        channels: list[EconomicChannel] = []
        for raw in override.economic_channels:
            for item in EconomicChannel:
                if item.value == raw.upper():
                    channels.append(item)
                    break
        merged[override.document_id] = LlmExtractionLabel(
            document_id=override.document_id,
            company_event_type=company_type,
            macro_event_type=base.macro_event_type if base else None,
            economic_channels=tuple(channels),
            confidence=override.confidence,
            source_span=base.source_span if base else None,
            model_version=base.model_version if base else _SYNTHESIS_MODEL_VERSION,
            quality_flags=base.quality_flags if base else (),
        )
    return merged


def _pit_visible_members(
    document_ids: tuple[str, ...],
    records_by_id: dict[str, ContextDocumentRecord],
    *,
    prediction_cutoff: int,
) -> list[str]:
    visible: list[str] = []
    for doc_id in document_ids:
        record = records_by_id.get(doc_id)
        if record is None:
            continue
        if not record.document.available_time:
            continue
        if iso_to_epoch_ns(record.document.available_time) <= prediction_cutoff:
            visible.append(doc_id)
    return visible


def _apply_revision_supersession(
    visible_doc_ids: list[str],
    records_by_id: dict[str, ContextDocumentRecord],
    llm_labels: dict[str, LlmExtractionLabel],
    *,
    prediction_cutoff: int,
) -> tuple[list[str], list[str], bool]:
    if not visible_doc_ids:
        return [], [], False

    lineage_groups: dict[str, list[str]] = {}
    for doc_id in visible_doc_ids:
        root = _lineage_root(doc_id, records_by_id)
        lineage_groups.setdefault(root, []).append(doc_id)

    active: list[str] = []
    superseded: list[str] = []
    revision_conflict = False

    for members in lineage_groups.values():
        if len(members) == 1:
            active.append(members[0])
            continue

        sorted_members = sorted(
            members,
            key=lambda doc_id: iso_to_epoch_ns(
                records_by_id[doc_id].document.available_time
            ),
        )
        winner = sorted_members[-1]
        active.append(winner)
        for doc_id in sorted_members[:-1]:
            superseded.append(doc_id)

        visible_in_lineage = [
            doc_id
            for doc_id in members
            if iso_to_epoch_ns(records_by_id[doc_id].document.available_time)
            <= prediction_cutoff
        ]
        if len(visible_in_lineage) >= 2:
            eligible_visible = [
                doc_id
                for doc_id in visible_in_lineage
                if doc_id in llm_labels
                and llm_labels[doc_id].confidence is not None
                and llm_labels[doc_id].confidence >= LLM_CONFIDENCE_THRESHOLD
            ]
            for index, left_id in enumerate(eligible_visible):
                left_label = llm_labels[left_id]
                for right_id in eligible_visible[index + 1:]:
                    if _labels_disagree(left_label, llm_labels[right_id]):
                        revision_conflict = True
                        break
                if revision_conflict:
                    break

    return active, superseded, revision_conflict


def _event_types_incompatible(types: set[str]) -> bool:
    for pair in _INCOMPATIBLE_EVENT_TYPES:
        if pair.issubset(types):
            return True
    return False


def _channel_polarity_conflict(channels: set[str]) -> bool:
    for channel in channels:
        opposite = _CHANNEL_OPPOSITES.get(channel)
        if opposite and opposite in channels:
            return True
    return False


def _majority_event_type(labels: list[LlmExtractionLabel]) -> str | None:
    counts: dict[str, int] = {}
    for label in labels:
        if label.company_event_type is None:
            continue
        value = label.company_event_type.value
        counts[value] = counts.get(value, 0) + 1
    if not counts:
        return None
    return max(counts.items(), key=lambda item: (item[1], item[0]))[0]


def _compute_agreement_and_channels(
    eligible_labels: dict[str, LlmExtractionLabel],
) -> tuple[float | None, bool, tuple[str, ...], tuple[str, ...], tuple[str, ...], bool]:
    if len(eligible_labels) < 2:
        return None, False, (), (), (), False

    labels_list = list(eligible_labels.values())
    majority_type = _majority_event_type(labels_list)
    event_types = {
        label.company_event_type.value
        for label in labels_list
        if label.company_event_type is not None
    }

    all_channels: set[str] = set()
    for label in labels_list:
        all_channels.update(channel.value for channel in label.economic_channels)

    contradiction = _event_types_incompatible(event_types) or _channel_polarity_conflict(
        all_channels
    )

    majority_channels: set[str] = set()
    if majority_type is not None:
        for label in labels_list:
            if (
                label.company_event_type is not None
                and label.company_event_type.value == majority_type
            ):
                majority_channels.update(channel.value for channel in label.economic_channels)

    supporting: list[str] = []
    contradicting: list[str] = []
    agreeing_count = 0
    for doc_id, label in eligible_labels.items():
        label_type = label.company_event_type.value if label.company_event_type else None
        label_channels = {channel.value for channel in label.economic_channels}
        agrees = (
            label_type == majority_type
            and bool(label_channels & majority_channels)
        )
        if agrees:
            agreeing_count += 1
            supporting.append(doc_id)
        else:
            contradicting.append(doc_id)

    theme_agreement_score = round(agreeing_count / len(eligible_labels), 6)

    consolidated: set[str] = set()
    if not contradiction:
        consolidated = majority_channels
    else:
        channel_counts: dict[str, int] = {}
        for label in labels_list:
            for channel in label.economic_channels:
                channel_counts[channel.value] = channel_counts.get(channel.value, 0) + 1
        max_count = max(channel_counts.values()) if channel_counts else 0
        for channel, count in channel_counts.items():
            if count == max_count and count > 1:
                opposite = _CHANNEL_OPPOSITES.get(channel)
                if opposite and channel_counts.get(opposite, 0) == max_count:
                    continue
                if opposite and channel_counts.get(opposite, 0) > 0:
                    continue
                consolidated.add(channel)

    return (
        theme_agreement_score,
        contradiction,
        tuple(sorted(consolidated)),
        tuple(sorted(supporting)),
        tuple(sorted(contradicting)),
        False,
    )


def _epoch_ns_to_iso(epoch_ns: int) -> str:
    seconds, nanos = divmod(epoch_ns, 1_000_000_000)
    dt = datetime.fromtimestamp(seconds, tz=timezone.utc)
    return f"{dt:%Y-%m-%dT%H:%M:%S}.{nanos:09d}Z"


def synthesize_cluster(
    *,
    cluster_id: str,
    document_ids: tuple[str, ...],
    records_by_id: dict[str, ContextDocumentRecord],
    llm_labels: dict[str, LlmExtractionLabel],
    synthesis_label: SynthesisFixtureLabel | None,
    prediction_cutoff: int,
    entity_id: str,
) -> MultiDocumentSynthesisSummary | None:
    visible = _pit_visible_members(document_ids, records_by_id, prediction_cutoff=prediction_cutoff)
    if len(visible) < 2:
        return None

    active, superseded, revision_conflict = _apply_revision_supersession(
        visible,
        records_by_id,
        llm_labels,
        prediction_cutoff=prediction_cutoff,
    )
    if len(active) < 2:
        return None

    members_without_labels = [doc_id for doc_id in active if doc_id not in llm_labels]
    eligible: dict[str, LlmExtractionLabel] = {}
    for doc_id in active:
        label = llm_labels.get(doc_id)
        if label is None:
            continue
        if label.confidence is None or label.confidence < LLM_CONFIDENCE_THRESHOLD:
            continue
        eligible[doc_id] = label

    quality_flags = [
        ContextQualityFlag.MULTI_DOCUMENT_SYNTHESIS_EXPERIMENTAL.value,
        ContextQualityFlag.NO_UNIVERSAL_NEWS_SCORE.value,
    ]
    if members_without_labels:
        quality_flags.append(ContextQualityFlag.SYNTHESIS_EXTRACTION_PARTIAL.value)

    theme_agreement_score: float | None = None
    if len(eligible) < 2:
        quality_flags.append(ContextQualityFlag.SYNTHESIS_INSUFFICIENT_DOCS.value)
        contradiction_detected = False
        consolidated_channels: tuple[str, ...] = ()
        supporting_ids: tuple[str, ...] = ()
        contradicting_ids: tuple[str, ...] = ()
    else:
        (
            theme_agreement_score,
            contradiction_detected,
            consolidated_channels,
            supporting_ids,
            contradicting_ids,
            _,
        ) = _compute_agreement_and_channels(eligible)
        if revision_conflict:
            contradiction_detected = True
            quality_flags.append(ContextQualityFlag.SYNTHESIS_REVISION_CONFLICT.value)
        if contradiction_detected:
            quality_flags.append(ContextQualityFlag.SYNTHESIS_CONTRADICTION_PRESENT.value)

    available_times = [
        iso_to_epoch_ns(records_by_id[doc_id].document.available_time)
        for doc_id in active
        if doc_id in records_by_id
    ]
    available_ns = max(available_times) if available_times else prediction_cutoff

    model_version = (
        synthesis_label.model_version if synthesis_label else _SYNTHESIS_MODEL_VERSION
    )
    thematic_summary = synthesis_label.thematic_summary if synthesis_label else None
    synthesis_confidence = (
        synthesis_label.synthesis_confidence if synthesis_label else None
    )

    return MultiDocumentSynthesisSummary(
        synthesis_id=synthesis_id_from_parts(
            cluster_id=cluster_id,
            entity_id=entity_id,
            prediction_cutoff_ns=prediction_cutoff,
        ),
        cluster_id=cluster_id,
        entity_id=entity_id.upper(),
        thematic_summary=thematic_summary,
        theme_agreement_score=theme_agreement_score,
        contradiction_detected=contradiction_detected,
        consolidated_channels=consolidated_channels,
        supporting_document_ids=supporting_ids,
        contradicting_document_ids=contradicting_ids,
        revision_superseded_ids=tuple(sorted(superseded)),
        synthesis_confidence=synthesis_confidence,
        model_version=model_version,
        quality_flags=tuple(dict.fromkeys(quality_flags)),
        available_time=_epoch_ns_to_iso(available_ns),
        publication_state=PublicationState.PUBLISHED.value,
    )


def build_fixture_synthesis_pipeline(
    events: list[InformationEvent],
    records: list[ContextDocumentRecord],
    llm_labels: dict[str, LlmExtractionLabel],
    synthesis_fixture: SynthesisFixturePayload | None,
    *,
    prediction_cutoff: int,
    entity_id: str,
    include_adversarial_clusters: bool = False,
) -> tuple[list[MultiDocumentSynthesisSummary], list[dict[str, Any]]]:
    records_by_id = _records_by_id(records)
    labels_map = synthesis_fixture.synthesis_labels if synthesis_fixture else {}
    overrides: tuple[ExtractionOverride, ...] = ()
    if synthesis_fixture is not None:
        overrides = synthesis_fixture.extraction_overrides
    merged_labels = _apply_extraction_overrides(llm_labels, overrides)

    summaries: list[MultiDocumentSynthesisSummary] = []
    target = entity_id.upper()

    for event in events:
        if len(event.document_ids) < 2:
            continue
        synthesis_label = labels_map.get(event.event_id)
        summary = synthesize_cluster(
            cluster_id=event.event_id,
            document_ids=event.document_ids,
            records_by_id=records_by_id,
            llm_labels=merged_labels,
            synthesis_label=synthesis_label,
            prediction_cutoff=prediction_cutoff,
            entity_id=target,
        )
        if summary is not None:
            summaries.append(summary)

    if include_adversarial_clusters and synthesis_fixture is not None:
        for adversarial in synthesis_fixture.adversarial_clusters:
            adversarial_labels = _apply_extraction_overrides(
                merged_labels, adversarial.extraction_overrides
            )
            synthesis_label = labels_map.get(adversarial.cluster_id)
            summary = synthesize_cluster(
                cluster_id=adversarial.cluster_id,
                document_ids=adversarial.document_ids,
                records_by_id=records_by_id,
                llm_labels=adversarial_labels,
                synthesis_label=synthesis_label,
                prediction_cutoff=prediction_cutoff,
                entity_id=target,
            )
            if summary is not None:
                summaries.append(summary)

    summaries.sort(key=lambda item: (item.available_time, item.cluster_id))
    adapter_rows = [synthesis_summary_to_adapter_row(item) for item in summaries]
    return summaries, adapter_rows


def synthesis_summary_to_dict(item: MultiDocumentSynthesisSummary) -> dict[str, Any]:
    return {
        "synthesis_id": item.synthesis_id,
        "cluster_id": item.cluster_id,
        "entity_id": item.entity_id,
        "thematic_summary": item.thematic_summary,
        "theme_agreement_score": item.theme_agreement_score,
        "contradiction_detected": item.contradiction_detected,
        "consolidated_channels": list(item.consolidated_channels),
        "supporting_document_ids": list(item.supporting_document_ids),
        "contradicting_document_ids": list(item.contradicting_document_ids),
        "revision_superseded_ids": list(item.revision_superseded_ids),
        "synthesis_confidence": item.synthesis_confidence,
        "model_version": model_version_to_dict(item.model_version),
        "quality_flags": list(item.quality_flags),
        "available_time": item.available_time,
        "publication_state": item.publication_state,
        "scoring_method": SCORING_METHOD,
    }


def synthesis_summary_to_adapter_row(item: MultiDocumentSynthesisSummary) -> dict[str, Any]:
    return {
        "synthesis_id": item.synthesis_id,
        "cluster_id": item.cluster_id,
        "entity_id": item.entity_id,
        "theme_agreement_score": item.theme_agreement_score,
        "contradiction_detected": item.contradiction_detected,
        "consolidated_channels": list(item.consolidated_channels),
        "available_time": item.available_time,
        "scoring_method": SCORING_METHOD,
    }


def build_synthesis_cross_lane_evidence(
    summaries: list[MultiDocumentSynthesisSummary],
    *,
    symbol: str,
    prediction_cutoff: int,
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for item in summaries:
        if iso_to_epoch_ns(item.available_time) > prediction_cutoff:
            continue
        if (
            item.theme_agreement_score is not None
            and item.theme_agreement_score >= THEME_AGREEMENT_ELEVATED_THRESHOLD
            and not item.contradiction_detected
        ):
            row = lane_evidence_to_dict(
                NormalizedLaneEvidence(
                    lane=LaneId.MARKET_CONTEXT,
                    signal=EvidenceSignal.SYNTHESIS_THEME_ELEVATED,
                    strength=(
                        "HIGH"
                        if item.theme_agreement_score >= 0.9
                        else "MODERATE"
                    ),
                    available=True,
                    source_ref=item.cluster_id,
                    detail=(
                        f"MC16 theme agreement {item.theme_agreement_score:.4f} "
                        f"for cluster {item.cluster_id} — not fused score"
                    ),
                    observed_at=item.available_time,
                    quality_flags=item.quality_flags,
                    provenance_class=EvidenceProvenanceClass.MODEL_OUTPUT,
                )
            )
            row["metadata"] = {
                "symbol": symbol,
                "cluster_id": item.cluster_id,
                "theme_agreement_score": item.theme_agreement_score,
                "consolidated_channels": list(item.consolidated_channels),
                "scoring_method": SCORING_METHOD,
                "research_only": True,
            }
            evidence.append(row)
        if item.contradiction_detected:
            row = lane_evidence_to_dict(
                NormalizedLaneEvidence(
                    lane=LaneId.MARKET_CONTEXT,
                    signal=EvidenceSignal.SYNTHESIS_CONTRADICTION_DETECTED,
                    strength="MODERATE",
                    available=True,
                    source_ref=item.cluster_id,
                    detail=(
                        f"MC16 contradiction detected for cluster {item.cluster_id} "
                        f"— partial synthesis only"
                    ),
                    observed_at=item.available_time,
                    quality_flags=item.quality_flags,
                    provenance_class=EvidenceProvenanceClass.MODEL_OUTPUT,
                )
            )
            row["metadata"] = {
                "symbol": symbol,
                "cluster_id": item.cluster_id,
                "contradicting_document_ids": list(item.contradicting_document_ids),
                "scoring_method": SCORING_METHOD,
                "research_only": True,
            }
            evidence.append(row)
    return evidence


def _aggregate_gate_status(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "FAIL"
    if any(row.get("gate_status") == "FAIL" for row in rows):
        return "FAIL"
    return "PASS"


def run_mc16_gate_validation(
    *,
    fixture_path: Path | None = None,
    expected_path: Path | None = None,
    raw_fixture_path: Path | None = None,
    llm_fixture_path: Path | None = None,
    prediction_cutoff: int | None = None,
) -> dict[str, Any]:
    """Run MC16 golden, PIT, revision, contradiction, and doctrine gates."""
    from .entity_resolution import (
        build_symbol_mapping_registry,
        load_context_document_records,
    )
    from .extraction import build_fixture_extraction_pipeline, load_llm_extraction_fixture

    fixture = fixture_path or DEFAULT_SYNTHESIS_FIXTURE
    expected_file = expected_path or DEFAULT_SYNTHESIS_EXPECTED
    raw_fixture = raw_fixture_path or DEFAULT_RAW_FIXTURE
    llm_fixture = llm_fixture_path or DEFAULT_LLM_FIXTURE
    cutoff_ns = (
        prediction_cutoff
        if prediction_cutoff is not None
        else iso_to_epoch_ns(GATE_PREDICTION_CUTOFF)
    )
    early_cutoff_ns = iso_to_epoch_ns(GATE_EARLY_CUTOFF)
    revision_cutoff_ns = iso_to_epoch_ns(GATE_REVISION_CUTOFF)

    synthesis_fixture = load_synthesis_fixture(fixture)
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    symbol = str(payload.get("symbol", "BOXL")).upper()

    records = load_context_document_records(
        raw_fixture,
        symbol_mappings=build_symbol_mapping_registry(symbol),
    )
    llm_labels = load_llm_extraction_fixture(llm_fixture)
    _, enriched_events, _ = build_fixture_extraction_pipeline(
        records,
        prediction_cutoff=cutoff_ns,
        llm_labels=llm_labels,
    )
    _, revision_events, _ = build_fixture_extraction_pipeline(
        records,
        prediction_cutoff=revision_cutoff_ns,
        llm_labels=llm_labels,
    )

    _, early_events, _ = build_fixture_extraction_pipeline(
        records,
        prediction_cutoff=early_cutoff_ns,
        llm_labels=llm_labels,
    )
    summaries, _ = build_fixture_synthesis_pipeline(
        enriched_events,
        records,
        llm_labels,
        synthesis_fixture,
        prediction_cutoff=cutoff_ns,
        entity_id=symbol,
        include_adversarial_clusters=False,
    )
    early_summaries, _ = build_fixture_synthesis_pipeline(
        early_events,
        records,
        llm_labels,
        synthesis_fixture,
        prediction_cutoff=early_cutoff_ns,
        entity_id=symbol,
        include_adversarial_clusters=False,
    )
    adversarial_summaries, _ = build_fixture_synthesis_pipeline(
        enriched_events,
        records,
        llm_labels,
        synthesis_fixture,
        prediction_cutoff=cutoff_ns,
        entity_id=symbol,
        include_adversarial_clusters=True,
    )
    revision_summaries, _ = build_fixture_synthesis_pipeline(
        revision_events,
        records,
        llm_labels,
        synthesis_fixture,
        prediction_cutoff=revision_cutoff_ns,
        entity_id=symbol,
        include_adversarial_clusters=False,
    )

    expected = json.loads(expected_file.read_text(encoding="utf-8"))
    actual_rows = [synthesis_summary_to_dict(item) for item in summaries]
    golden_match = actual_rows == expected.get("synthesis_summaries", [])

    pit_gate = (
        len(early_summaries) < len(summaries)
        or not any(
            "mc-doc-earnings-1-v2" in row.get("supporting_document_ids", [])
            or "mc-doc-earnings-1-v2" in row.get("contradicting_document_ids", [])
            or "mc-doc-earnings-1-v2" in row.get("revision_superseded_ids", [])
            for row in actual_rows
        )
    )

    earnings_revision = next(
        (
            item
            for item in revision_summaries
            if item.cluster_id == "df2e6ba5-46ab-5bb1-a867-745fe0a75c91"
        ),
        None,
    )
    revision_gate = (
        earnings_revision is not None
        and "mc-doc-earnings-1" in earnings_revision.revision_superseded_ids
        and "mc-doc-earnings-1-v2" in earnings_revision.supporting_document_ids
        and ContextQualityFlag.SYNTHESIS_REVISION_CONFLICT.value
        in earnings_revision.quality_flags
    )

    adversarial_row = next(
        (
            item
            for item in adversarial_summaries
            if item.cluster_id == "mc16-adversarial-contradiction"
        ),
        None,
    )
    contradiction_gate = (
        adversarial_row is not None
        and adversarial_row.contradiction_detected
        and ContextQualityFlag.SYNTHESIS_CONTRADICTION_PRESENT.value
        in adversarial_row.quality_flags
    )

    forbidden_fields = ("news_score", "universal_score", "combined_score", "fused_score")
    doctrine_gate = all(
        not any(field in row for field in forbidden_fields) for row in actual_rows
    ) and all(
        "theme_agreement_score" in row or "contradiction_detected" in row
        for row in actual_rows
        if row
    )

    cross_lane = build_synthesis_cross_lane_evidence(
        summaries,
        symbol=symbol,
        prediction_cutoff=cutoff_ns,
    )
    cross_lane_gate = bool(cross_lane) and all(
        (row.get("metadata") or {}).get("research_only") for row in cross_lane
    )

    gate_summary = [
        {
            "gate_milestone": "MC16-GOLDEN",
            "gate_status": "PASS" if golden_match else "FAIL",
        },
        {
            "gate_milestone": "MC16-PIT",
            "gate_status": "PASS" if pit_gate else "FAIL",
        },
        {
            "gate_milestone": "MC16-REVISION",
            "gate_status": "PASS" if revision_gate else "FAIL",
        },
        {
            "gate_milestone": "MC16-CONTRADICTION",
            "gate_status": "PASS" if contradiction_gate else "FAIL",
        },
        {
            "gate_milestone": "MC16-DOCTRINE",
            "gate_status": "PASS" if doctrine_gate else "FAIL",
        },
        {
            "gate_milestone": "MC16-CROSS-LANE",
            "gate_status": "PASS" if cross_lane_gate else "FAIL",
        },
    ]

    return {
        "artifact_type": "MC16_MULTI_DOCUMENT_SYNTHESIS_GATE_VALIDATION_REPORT",
        "scope": "fixture",
        "research_only": True,
        "not_trade_signal": True,
        "aggregate_status": _aggregate_gate_status(gate_summary),
        "fixture_refs": [
            {
                "role": "synthesis_labels",
                "repository_relative_path": fixture.relative_to(
                    Path(__file__).resolve().parents[4]
                ).as_posix(),
                "admission_id": payload.get("admission_id"),
                "symbol": symbol,
            },
            {
                "role": "golden_expected",
                "repository_relative_path": expected_file.relative_to(
                    Path(__file__).resolve().parents[4]
                ).as_posix(),
            },
        ],
        "gate_summary": gate_summary,
        "synthesis_count": len(summaries),
        "early_synthesis_count": len(early_summaries),
        "adversarial_synthesis_count": len(adversarial_summaries),
        "synthesis_summaries": actual_rows,
    }


__all__ = [
    "DEFAULT_LLM_FIXTURE",
    "DEFAULT_RAW_FIXTURE",
    "DEFAULT_SYNTHESIS_EXPECTED",
    "DEFAULT_SYNTHESIS_FIXTURE",
    "AdversarialCluster",
    "ExtractionOverride",
    "GATE_EARLY_CUTOFF",
    "GATE_PREDICTION_CUTOFF",
    "GATE_REVISION_CUTOFF",
    "LLM_CONFIDENCE_THRESHOLD",
    "MultiDocumentSynthesisSummary",
    "PRODUCER_VERSION",
    "SCORING_METHOD",
    "SynthesisFixtureLabel",
    "SynthesisFixturePayload",
    "THEME_AGREEMENT_ELEVATED_THRESHOLD",
    "build_fixture_synthesis_pipeline",
    "build_synthesis_cross_lane_evidence",
    "load_synthesis_fixture",
    "model_version_to_dict",
    "run_mc16_gate_validation",
    "synthesis_id_from_parts",
    "synthesize_cluster",
    "synthesis_summary_to_adapter_row",
    "synthesis_summary_to_dict",
]
