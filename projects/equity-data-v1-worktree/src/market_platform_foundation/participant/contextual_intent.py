"""PI8 contextual intent — participant action timing relative to catalyst windows."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from ..contracts.participant import (
    ContextualIntentEvidence,
    InsiderDiscretion,
    ParticipantActionType,
    ParticipantQualityFlag,
)
from ..cross_lane.evidence import (
    EvidenceProvenanceClass,
    EvidenceSignal,
    LaneId,
    NormalizedLaneEvidence,
    lane_evidence_to_dict,
)
from ..market_context.catalyst import CatalystSummary
from ..normalization.equity_bars import iso_to_epoch_ns

PRODUCER_VERSION = "participant_contextual_intent_v1"
SCORING_METHOD = "contextual_intent_v1"
CATALYST_WINDOW_DAYS = 14
SECONDS_PER_DAY = 86_400


@dataclass(frozen=True, slots=True)
class ContextualIntentSummary:
    action_id: str
    participant_id: str
    catalyst_event_id: str | None
    timing_relation: str
    intent_classification: str
    days_offset_from_catalyst: float | None
    event_time: str
    available_time: str
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    cross_lane_signal: str | None = None


def _parse_time(value: str) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def _days_between(earlier: str, later: str) -> float | None:
    start = _parse_time(earlier)
    end = _parse_time(later)
    if start is None or end is None:
        return None
    return round((end - start).total_seconds() / SECONDS_PER_DAY, 4)


def _qualifying_action(action: dict[str, Any]) -> bool:
    form_type = str(action.get("form_type", "")).upper().replace("/A", "")
    action_type = str(action.get("action_type", ""))
    if form_type == "13D":
        return True
    if form_type == "4" and action_type == ParticipantActionType.OPEN_MARKET_BUY.value:
        return action.get("insider_discretion") == InsiderDiscretion.DISCRETIONARY.value
    return False


def _nearest_catalyst(
    action: dict[str, Any],
    catalysts: list[CatalystSummary],
    *,
    prediction_cutoff: int,
) -> tuple[CatalystSummary | None, str, float | None]:
    action_time = str(action.get("action_time", ""))
    action_ns = iso_to_epoch_ns(str(action.get("available_time", "")))
    if action_ns > prediction_cutoff:
        return None, "UNRELATED", None

    best: CatalystSummary | None = None
    best_abs_days: float | None = None
    best_relation = "UNRELATED"
    best_offset: float | None = None

    for catalyst in catalysts:
        catalyst_ns = iso_to_epoch_ns(catalyst.available_time)
        if catalyst_ns > prediction_cutoff:
            continue
        offset = _days_between(action_time, catalyst.event_time)
        if offset is None:
            continue
        if abs(offset) <= 0.5:
            relation = "CONTEMPORANEOUS"
            abs_days = abs(offset)
        elif offset > 0:
            relation = "PRE_CATALYST"
            abs_days = abs(offset)
        else:
            relation = "POST_CATALYST"
            abs_days = abs(offset)
        if abs_days > CATALYST_WINDOW_DAYS:
            continue
        if best_abs_days is None or abs_days < best_abs_days:
            best = catalyst
            best_abs_days = abs_days
            best_relation = relation
            best_offset = offset

    return best, best_relation, best_offset


def _intent_classification(
    action: dict[str, Any],
    timing_relation: str,
) -> str:
    if timing_relation == "UNRELATED":
        return "UNRELATED"
    if not _qualifying_action(action):
        return "INSUFFICIENT_DATA"
    if timing_relation == "PRE_CATALYST":
        return "INFORMED_TIMING_CANDIDATE"
    if timing_relation in {"POST_CATALYST", "CONTEMPORANEOUS"}:
        return "REACTIVE"
    return "INSUFFICIENT_DATA"


def _cross_lane_signal(
    intent_classification: str,
    catalyst: CatalystSummary | None,
) -> str | None:
    if intent_classification != "INFORMED_TIMING_CANDIDATE" or catalyst is None:
        return None
    lean = str(catalyst.lean or "").upper()
    if lean == "BULLISH":
        return EvidenceSignal.PARTICIPANT_ALIGNMENT_CANDIDATE.value
    if lean == "BEARISH":
        return EvidenceSignal.PARTICIPANT_CONTRARIAN_CANDIDATE.value
    return None


def build_contextual_intent_evidence(
    actions: list[dict[str, Any]],
    catalysts: list[CatalystSummary],
    *,
    prediction_cutoff: int,
) -> tuple[list[ContextualIntentEvidence], list[ContextualIntentSummary]]:
    evidence_rows: list[ContextualIntentEvidence] = []
    summaries: list[ContextualIntentSummary] = []

    for action in actions:
        catalyst, timing_relation, offset = _nearest_catalyst(
            action,
            catalysts,
            prediction_cutoff=prediction_cutoff,
        )
        intent = _intent_classification(action, timing_relation)
        quality_flags: list[str] = []
        if intent == "INSUFFICIENT_DATA":
            quality_flags.append(ParticipantQualityFlag.ACTION_AMBIGUOUS.value)
        if catalyst is None:
            quality_flags.append(ParticipantQualityFlag.CATALYST_CONTEXT_MISSING.value)

        signal = _cross_lane_signal(intent, catalyst)
        summary = ContextualIntentSummary(
            action_id=str(action.get("action_id", "")),
            participant_id=str(action.get("participant_id", "")),
            catalyst_event_id=catalyst.event_id if catalyst else None,
            timing_relation=timing_relation,
            intent_classification=intent,
            days_offset_from_catalyst=offset,
            event_time=str(action.get("event_time", "")),
            available_time=str(action.get("available_time", "")),
            quality_flags=tuple(dict.fromkeys(quality_flags)),
            cross_lane_signal=signal,
        )
        summaries.append(summary)
        evidence_rows.append(
            ContextualIntentEvidence(
                action_id=summary.action_id,
                participant_id=summary.participant_id,
                catalyst_event_id=summary.catalyst_event_id,
                timing_relation=summary.timing_relation,
                intent_classification=summary.intent_classification,
                days_offset_from_catalyst=summary.days_offset_from_catalyst,
                event_time=summary.event_time,
                available_time=summary.available_time,
                producer_version=PRODUCER_VERSION,
                quality_flags=summary.quality_flags,
                cross_lane_signal=signal,
            )
        )

    return evidence_rows, summaries


def contextual_intent_summary_to_dict(item: ContextualIntentSummary) -> dict[str, Any]:
    return {
        "action_id": item.action_id,
        "participant_id": item.participant_id,
        "catalyst_event_id": item.catalyst_event_id,
        "timing_relation": item.timing_relation,
        "intent_classification": item.intent_classification,
        "days_offset_from_catalyst": item.days_offset_from_catalyst,
        "event_time": item.event_time,
        "available_time": item.available_time,
        "quality_flags": list(item.quality_flags),
        "cross_lane_signal": item.cross_lane_signal,
        "scoring_method": SCORING_METHOD,
    }


def publish_contextual_intent_signals(
    summaries: list[ContextualIntentSummary],
    *,
    prediction_cutoff: int,
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for item in summaries:
        if iso_to_epoch_ns(item.available_time) > prediction_cutoff:
            continue
        if not item.cross_lane_signal:
            continue
        detail = (
            f"PI8 contextual intent {item.intent_classification} "
            f"timing={item.timing_relation} catalyst={item.catalyst_event_id}"
        )
        evidence.append(
            lane_evidence_to_dict(
                NormalizedLaneEvidence(
                    lane=LaneId.PARTICIPANT_INTELLIGENCE,
                    signal=EvidenceSignal(item.cross_lane_signal),
                    strength="MODERATE",
                    available=True,
                    source_ref=f"participant:contextual_intent:{item.action_id}",
                    detail=detail,
                    observed_at=item.available_time,
                    quality_flags=item.quality_flags,
                    provenance_class=EvidenceProvenanceClass.DERIVED,
                )
            )
        )
    return evidence


__all__ = [
    "PRODUCER_VERSION",
    "SCORING_METHOD",
    "ContextualIntentSummary",
    "build_contextual_intent_evidence",
    "contextual_intent_summary_to_dict",
    "publish_contextual_intent_signals",
]
