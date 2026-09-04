"""PI9 copyability / entry quality — follower return after available_time."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..contracts.participant import (
    CopyabilityClass,
    CopyabilityEvidence,
    IdentityConfidence,
    InsiderDiscretion,
    ParticipantActionType,
    ParticipantHorizon,
    ParticipantMechanism,
    ParticipantQualityFlag,
    copyability_evidence_to_dict,
)
from ..cross_lane.evidence import (
    EvidenceProvenanceClass,
    EvidenceSignal,
    LaneId,
    NormalizedLaneEvidence,
    lane_evidence_to_dict,
)
from ..normalization.equity_bars import iso_to_epoch_ns
from .skill import (
    DEFAULT_PRICE_OUTCOME_FIXTURE,
    forward_return_from_prices,
    load_price_outcome_fixture,
)

PRODUCER_VERSION = "participant_copyability_v1"
SCORING_METHOD = "copyability_v1"
DEFAULT_COPY_WINDOW_DAYS = 20
DEFAULT_COST_BPS = 50
COPYABILITY_SCORE_SCALE = 0.10
COPYABILITY_HIGH_THRESHOLD = 0.5

_COPYABLE_MECHANISMS = {
    ParticipantMechanism.INFORMED_DIRECTIONAL,
    ParticipantMechanism.FUNDAMENTAL_CONVICTION,
    ParticipantMechanism.STRATEGIC_CONTROL,
    ParticipantMechanism.ACTIVIST_INFLUENCE,
    ParticipantMechanism.MECHANICAL_FLOW,
}

_SCORABLE_ACTION_TYPES = {
    ParticipantActionType.OPEN_MARKET_BUY.value,
    ParticipantActionType.ACTIVIST_STAKE_INITIATED.value,
    ParticipantActionType.POSITION_INITIATED.value,
    ParticipantActionType.POSITION_INCREASED.value,
}


@dataclass(frozen=True, slots=True)
class CopyabilitySummary:
    action_id: str
    participant_id: str
    display_name: str
    instrument_id: str
    mechanism: str
    copyability_class: str
    participant_gross_return: float | None
    follower_return_at_available: float | None
    cost_adjusted_follower_return: float | None
    copyability_score: float | None
    event_time: str
    available_time: str
    quality_flags: tuple[str, ...] = field(default_factory=tuple)
    cross_lane_signal: str | None = None


def load_copyability_fixture(path: Path | str | None = None) -> dict[str, Any]:
    fixture_path = (
        Path(path)
        if path is not None
        else Path(__file__).resolve().parents[3]
        / "tests"
        / "fixtures"
        / "participant"
        / "biya_copyability_slice.json"
    )
    with fixture_path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _parse_time_ns(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if text.isdigit():
        return int(text)
    return iso_to_epoch_ns(text)


def infer_mechanism_from_action(action: dict[str, Any]) -> ParticipantMechanism:
    form_type = str(action.get("form_type", "")).upper().replace("/A", "")
    action_type = str(action.get("action_type", ""))
    discretion = action.get("insider_discretion")
    if form_type == "13D" or action_type == ParticipantActionType.ACTIVIST_STAKE_INITIATED.value:
        return ParticipantMechanism.ACTIVIST_INFLUENCE
    if form_type.startswith("13F"):
        return ParticipantMechanism.PORTFOLIO_ALLOCATION
    if form_type == "13G":
        return ParticipantMechanism.PASSIVE_INDEX
    if (
        action_type == ParticipantActionType.OPEN_MARKET_BUY.value
        and discretion == InsiderDiscretion.DISCRETIONARY.value
    ):
        return ParticipantMechanism.INFORMED_DIRECTIONAL
    if action_type == ParticipantActionType.OPEN_MARKET_SELL.value:
        return ParticipantMechanism.INFORMED_DIRECTIONAL
    if action_type in {
        ParticipantActionType.POSITION_INITIATED.value,
        ParticipantActionType.POSITION_INCREASED.value,
    }:
        return ParticipantMechanism.PORTFOLIO_ALLOCATION
    return ParticipantMechanism.UNKNOWN


def mechanism_is_copyable(mechanism: ParticipantMechanism) -> bool:
    return mechanism in _COPYABLE_MECHANISMS


def _cost_fraction(cost_bps: float) -> float:
    return max(0.0, cost_bps) / 10_000.0


def score_copyability_action(
    action: dict[str, Any],
    *,
    daily_closes: dict[str, float],
    prediction_cutoff: int,
    copy_window_days: int = DEFAULT_COPY_WINDOW_DAYS,
    cost_bps: float = DEFAULT_COST_BPS,
) -> CopyabilityEvidence | None:
    available_ns = _parse_time_ns(action.get("available_time"))
    if available_ns > prediction_cutoff:
        return None

    quality_flags = list(action.get("quality_flags", []))
    quality_flags.append(ParticipantQualityFlag.COPYABILITY_EXPERIMENTAL.value)

    if ParticipantQualityFlag.QUARTER_END_NOT_COPYABLE.value in quality_flags:
        mechanism = infer_mechanism_from_action(action)
        return CopyabilityEvidence(
            action_id=str(action.get("action_id", "")),
            participant_id=str(action.get("participant_id", "")),
            instrument_id=str(action.get("instrument_id", "UNKNOWN")),
            mechanism=mechanism,
            horizon=ParticipantHorizon.MONTHS,
            identity_confidence=IdentityConfidence(
                str(action.get("identity_confidence", IdentityConfidence.UNKNOWN.value))
            ),
            copyability_class=CopyabilityClass.NOT_COPYABLE,
            participant_gross_return=None,
            follower_return_at_available=None,
            cost_adjusted_follower_return=None,
            copyability_score=None,
            event_time=str(action.get("event_time", "")),
            available_time=str(action.get("available_time", "")),
            producer_version=PRODUCER_VERSION,
            quality_flags=tuple(sorted(set(quality_flags))),
            cross_lane_signal=EvidenceSignal.PARTICIPANT_COPYABILITY_LOW.value,
        )

    action_type = str(action.get("action_type", ""))
    if action_type not in _SCORABLE_ACTION_TYPES:
        return None

    mechanism = infer_mechanism_from_action(action)
    if mechanism == ParticipantMechanism.UNKNOWN:
        quality_flags.append(ParticipantQualityFlag.MECHANISM_UNKNOWN.value)
        return CopyabilityEvidence(
            action_id=str(action.get("action_id", "")),
            participant_id=str(action.get("participant_id", "")),
            instrument_id=str(action.get("instrument_id", "UNKNOWN")),
            mechanism=mechanism,
            horizon=ParticipantHorizon.UNKNOWN,
            identity_confidence=IdentityConfidence(
                str(action.get("identity_confidence", IdentityConfidence.UNKNOWN.value))
            ),
            copyability_class=CopyabilityClass.INSUFFICIENT_DATA,
            participant_gross_return=None,
            follower_return_at_available=None,
            cost_adjusted_follower_return=None,
            copyability_score=None,
            event_time=str(action.get("event_time", "")),
            available_time=str(action.get("available_time", "")),
            producer_version=PRODUCER_VERSION,
            quality_flags=tuple(sorted(set(quality_flags))),
            cross_lane_signal=None,
        )

    action_time = action.get("action_time") or action.get("event_time")
    gross_return, gross_flags = forward_return_from_prices(
        daily_closes,
        available_time=action_time,
        window_days=copy_window_days,
        prediction_cutoff_ns=prediction_cutoff,
    )
    follower_return, follower_flags = forward_return_from_prices(
        daily_closes,
        available_time=action.get("available_time"),
        window_days=copy_window_days,
        prediction_cutoff_ns=prediction_cutoff,
    )
    quality_flags.extend(gross_flags)
    quality_flags.extend(follower_flags)

    if follower_return is None:
        quality_flags.append(ParticipantQualityFlag.OUTCOME_WINDOW_INCOMPLETE.value)
        return CopyabilityEvidence(
            action_id=str(action.get("action_id", "")),
            participant_id=str(action.get("participant_id", "")),
            instrument_id=str(action.get("instrument_id", "UNKNOWN")),
            mechanism=mechanism,
            horizon=ParticipantHorizon.MONTHS,
            identity_confidence=IdentityConfidence(
                str(action.get("identity_confidence", IdentityConfidence.UNKNOWN.value))
            ),
            copyability_class=CopyabilityClass.INSUFFICIENT_DATA,
            participant_gross_return=gross_return,
            follower_return_at_available=None,
            cost_adjusted_follower_return=None,
            copyability_score=None,
            event_time=str(action.get("event_time", "")),
            available_time=str(action.get("available_time", "")),
            producer_version=PRODUCER_VERSION,
            quality_flags=tuple(sorted(set(quality_flags))),
            cross_lane_signal=None,
        )

    cost_adjusted = follower_return - _cost_fraction(cost_bps)
    signal: str | None = None
    if not mechanism_is_copyable(mechanism):
        copy_class = CopyabilityClass.NOT_COPYABLE
        score = None
        signal = EvidenceSignal.PARTICIPANT_COPYABILITY_LOW.value
    elif cost_adjusted > 0:
        copy_class = CopyabilityClass.COPYABLE
        score = round(_clamp01(cost_adjusted / COPYABILITY_SCORE_SCALE), 6)
        if score >= COPYABILITY_HIGH_THRESHOLD:
            signal = EvidenceSignal.PARTICIPANT_COPYABILITY_HIGH.value
    else:
        copy_class = CopyabilityClass.STALE
        score = None
        signal = EvidenceSignal.PARTICIPANT_COPYABILITY_LOW.value

    return CopyabilityEvidence(
        action_id=str(action.get("action_id", "")),
        participant_id=str(action.get("participant_id", "")),
        instrument_id=str(action.get("instrument_id", "UNKNOWN")),
        mechanism=mechanism,
        horizon=ParticipantHorizon.MONTHS,
        identity_confidence=IdentityConfidence(
            str(action.get("identity_confidence", IdentityConfidence.UNKNOWN.value))
        ),
        copyability_class=copy_class,
        participant_gross_return=round(gross_return, 6) if gross_return is not None else None,
        follower_return_at_available=round(follower_return, 6),
        cost_adjusted_follower_return=round(cost_adjusted, 6),
        copyability_score=score,
        event_time=str(action.get("event_time", "")),
        available_time=str(action.get("available_time", "")),
        producer_version=PRODUCER_VERSION,
        quality_flags=tuple(sorted(set(quality_flags))),
        cross_lane_signal=signal,
    )


def build_copyability_evidence(
    actions: list[dict[str, Any]],
    *,
    prediction_cutoff: int,
    price_fixture_path: Path | str | None = None,
    copyability_fixture_path: Path | str | None = None,
) -> tuple[list[CopyabilityEvidence], list[CopyabilitySummary]]:
    if not actions:
        return [], []
    price_fixture = load_price_outcome_fixture(price_fixture_path or DEFAULT_PRICE_OUTCOME_FIXTURE)
    daily_closes_raw = price_fixture.get("daily_closes", {})
    if not isinstance(daily_closes_raw, dict) or not daily_closes_raw:
        return [], []
    daily_closes = {str(k): float(v) for k, v in daily_closes_raw.items()}

    slice_fixture = load_copyability_fixture(copyability_fixture_path)
    copy_window_days = int(slice_fixture.get("copy_window_days", DEFAULT_COPY_WINDOW_DAYS))
    cost_bps = float(slice_fixture.get("default_cost_bps", DEFAULT_COST_BPS))
    per_action_costs = slice_fixture.get("action_cost_bps", {})
    if not isinstance(per_action_costs, dict):
        per_action_costs = {}

    evidence_items: list[CopyabilityEvidence] = []
    summaries: list[CopyabilitySummary] = []
    for action in actions:
        action_id = str(action.get("action_id", ""))
        action_cost = float(per_action_costs.get(action_id, cost_bps))
        item = score_copyability_action(
            action,
            daily_closes=daily_closes,
            prediction_cutoff=prediction_cutoff,
            copy_window_days=copy_window_days,
            cost_bps=action_cost,
        )
        if item is None:
            continue
        evidence_items.append(item)
        summaries.append(
            CopyabilitySummary(
                action_id=item.action_id,
                participant_id=item.participant_id,
                display_name=str(action.get("display_name", "")),
                instrument_id=item.instrument_id,
                mechanism=item.mechanism.value,
                copyability_class=item.copyability_class.value,
                participant_gross_return=item.participant_gross_return,
                follower_return_at_available=item.follower_return_at_available,
                cost_adjusted_follower_return=item.cost_adjusted_follower_return,
                copyability_score=item.copyability_score,
                event_time=item.event_time,
                available_time=item.available_time,
                quality_flags=item.quality_flags,
                cross_lane_signal=item.cross_lane_signal,
            )
        )
    return evidence_items, summaries


def copyability_summary_to_dict(item: CopyabilitySummary) -> dict[str, Any]:
    return {
        "action_id": item.action_id,
        "participant_id": item.participant_id,
        "display_name": item.display_name,
        "instrument_id": item.instrument_id,
        "mechanism": item.mechanism,
        "copyability_class": item.copyability_class,
        "participant_gross_return": item.participant_gross_return,
        "follower_return_at_available": item.follower_return_at_available,
        "cost_adjusted_follower_return": item.cost_adjusted_follower_return,
        "copyability_score": item.copyability_score,
        "event_time": item.event_time,
        "available_time": item.available_time,
        "quality_flags": list(item.quality_flags),
        "cross_lane_signal": item.cross_lane_signal,
        "scoring_method": SCORING_METHOD,
        "producer_version": PRODUCER_VERSION,
    }


def summarize_copyability(summaries: list[CopyabilitySummary]) -> dict[str, Any]:
    copyable_count = sum(1 for item in summaries if item.copyability_class == CopyabilityClass.COPYABLE.value)
    not_copyable_count = sum(
        1 for item in summaries if item.copyability_class == CopyabilityClass.NOT_COPYABLE.value
    )
    stale_count = sum(1 for item in summaries if item.copyability_class == CopyabilityClass.STALE.value)
    insufficient_count = sum(
        1 for item in summaries if item.copyability_class == CopyabilityClass.INSUFFICIENT_DATA.value
    )
    signals = sorted(
        {item.cross_lane_signal for item in summaries if item.cross_lane_signal is not None}
    )
    return {
        "copyability_available": bool(summaries),
        "action_count": len(summaries),
        "copyable_count": copyable_count,
        "not_copyable_count": not_copyable_count,
        "stale_count": stale_count,
        "insufficient_data_count": insufficient_count,
        "cross_lane_signals": signals,
        "producer_version": PRODUCER_VERSION,
        "whale_aligned_copyability_gate": whale_aligned_copyability_gate(summaries),
    }


def whale_aligned_copyability_gate(summaries: list[CopyabilitySummary]) -> bool:
    """Return True when at least one COPYABLE action has a copyable mechanism."""
    for item in summaries:
        if item.copyability_class != CopyabilityClass.COPYABLE.value:
            continue
        try:
            mechanism = ParticipantMechanism(item.mechanism)
        except ValueError:
            continue
        if mechanism_is_copyable(mechanism) and item.copyability_score is not None:
            return True
    return False


def publish_copyability_signals(
    summaries: list[CopyabilitySummary],
    *,
    prediction_cutoff: int,
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for item in summaries:
        if _parse_time_ns(item.available_time) > prediction_cutoff:
            continue
        if item.cross_lane_signal is None:
            continue
        if ParticipantQualityFlag.MECHANISM_UNKNOWN.value in item.quality_flags:
            continue
        detail = (
            f"{item.display_name or item.participant_id} copyability={item.copyability_class} "
            f"follower_return={item.follower_return_at_available}; research only"
        )
        evidence.append(
            lane_evidence_to_dict(
                NormalizedLaneEvidence(
                    lane=LaneId.PARTICIPANT_INTELLIGENCE,
                    signal=EvidenceSignal(item.cross_lane_signal),
                    strength="MODERATE",
                    available=True,
                    source_ref=f"participant:copyability:{item.action_id}",
                    detail=detail,
                    observed_at=item.available_time,
                    quality_flags=item.quality_flags,
                    provenance_class=EvidenceProvenanceClass.DERIVED,
                )
            )
        )
    return evidence


def build_participant_copyability_bundle(
    actions: list[dict[str, Any]],
    *,
    prediction_cutoff: int,
    price_fixture_path: Path | str | None = None,
    copyability_fixture_path: Path | str | None = None,
) -> dict[str, Any]:
    if not actions:
        return {
            "available": False,
            "reason": "NO_PARTICIPANT_ACTIONS",
            "summary": {"copyability_available": False, "action_count": 0},
            "evidence": [],
            "summaries": [],
        }
    evidence, summaries = build_copyability_evidence(
        actions,
        prediction_cutoff=prediction_cutoff,
        price_fixture_path=price_fixture_path,
        copyability_fixture_path=copyability_fixture_path,
    )
    summary = summarize_copyability(summaries)
    return {
        "available": bool(summaries),
        "summary": summary,
        "evidence": [copyability_evidence_to_dict(item) for item in evidence],
        "summaries": [copyability_summary_to_dict(item) for item in summaries],
    }


__all__ = [
    "CopyabilitySummary",
    "PRODUCER_VERSION",
    "SCORING_METHOD",
    "build_copyability_evidence",
    "build_participant_copyability_bundle",
    "copyability_summary_to_dict",
    "infer_mechanism_from_action",
    "load_copyability_fixture",
    "mechanism_is_copyable",
    "publish_copyability_signals",
    "score_copyability_action",
    "summarize_copyability",
    "whale_aligned_copyability_gate",
]
