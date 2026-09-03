"""PI10 consensus / disagreement / crowding — instrument-level participant alignment."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ..contracts.participant import (
    InsiderDiscretion,
    ParticipantActionType,
    ParticipantAlignmentRegime,
    ParticipantCrowdingEvidence,
    ParticipantQualityFlag,
    ParticipantStanceDirection,
    ParticipantType,
    participant_crowding_evidence_to_dict,
)
from ..cross_lane.evidence import (
    EvidenceProvenanceClass,
    EvidenceSignal,
    LaneId,
    NormalizedLaneEvidence,
    lane_evidence_to_dict,
)
from ..normalization.equity_bars import iso_to_epoch_ns

PRODUCER_VERSION = "participant_crowding_v1"
SCORING_METHOD = "crowding_v1"
DEFAULT_LOOKBACK_DAYS = 180
DEFAULT_MIN_INDEPENDENT = 2
DEFAULT_MIN_INSTITUTIONAL = 2
DEFAULT_CROWDING_THRESHOLD = 0.66
DEFAULT_DISAGREEMENT_THRESHOLD = 0.34

DEFAULT_CROWDING_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "participant"
    / "biya_crowding_slice.json"
)

_INSIDER_TYPES = {
    ParticipantType.CORPORATE_INSIDER.value,
}
_ACTIVIST_TYPES = {
    ParticipantType.ACTIVIST.value,
}
_INSTITUTIONAL_TYPES = {
    ParticipantType.HEDGE_FUND.value,
    ParticipantType.MUTUAL_FUND.value,
    ParticipantType.PENSION.value,
    ParticipantType.ASSET_MANAGER.value,
    ParticipantType.ETF.value,
    ParticipantType.INDEX_MANAGER.value,
    ParticipantType.FAMILY_OFFICE.value,
}

_BULLISH_ACTIONS = {
    ParticipantActionType.OPEN_MARKET_BUY.value,
    ParticipantActionType.ACTIVIST_STAKE_INITIATED.value,
    ParticipantActionType.ACTIVIST_STAKE_INCREASED.value,
    ParticipantActionType.POSITION_INITIATED.value,
    ParticipantActionType.POSITION_INCREASED.value,
}
_BEARISH_ACTIONS = {
    ParticipantActionType.OPEN_MARKET_SELL.value,
    ParticipantActionType.POSITION_REDUCED.value,
    ParticipantActionType.POSITION_EXITED.value,
}


@dataclass(frozen=True, slots=True)
class ParticipantStanceSummary:
    participant_id: str
    display_name: str
    cohort: str
    stance: str
    independent_key: str
    action_id: str
    available_time: str
    event_time: str
    quality_flags: tuple[str, ...] = field(default_factory=tuple)


def load_crowding_fixture(path: Path | str | None = None) -> dict[str, Any]:
    fixture_path = Path(path) if path is not None else DEFAULT_CROWDING_FIXTURE
    with fixture_path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _parse_time_ns(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if text.isdigit():
        return int(text)
    return iso_to_epoch_ns(text)


def _available_date(value: Any) -> date:
    ns = _parse_time_ns(value)
    if ns > 0:
        return datetime.fromtimestamp(ns / 1_000_000_000, tz=timezone.utc).date()
    text = str(value).strip()
    if len(text) == 10 and text[4] == "-":
        return date.fromisoformat(text)
    return datetime.fromisoformat(text.replace("Z", "+00:00")).date()


def _independent_key(
    action: dict[str, Any],
    *,
    affiliation_groups: dict[str, str],
) -> str:
    display_name = str(action.get("display_name", "")).strip()
    if display_name in affiliation_groups:
        return affiliation_groups[display_name]
    participant_id = str(action.get("participant_id", "")).strip()
    if participant_id:
        return participant_id
    return display_name or "unknown"


def _participant_cohort(action: dict[str, Any]) -> str | None:
    participant_type = str(action.get("participant_type", ""))
    action_type = str(action.get("action_type", ""))
    if participant_type in _INSIDER_TYPES or action_type in {
        ParticipantActionType.OPEN_MARKET_BUY.value,
        ParticipantActionType.OPEN_MARKET_SELL.value,
        ParticipantActionType.INSIDER_AWARD_GRANT.value,
    }:
        return "insider"
    if participant_type in _ACTIVIST_TYPES or action_type in {
        ParticipantActionType.ACTIVIST_STAKE_INITIATED.value,
        ParticipantActionType.ACTIVIST_STAKE_INCREASED.value,
    }:
        return "activist"
    if participant_type in _INSTITUTIONAL_TYPES or action_type in {
        ParticipantActionType.POSITION_INITIATED.value,
        ParticipantActionType.POSITION_INCREASED.value,
        ParticipantActionType.POSITION_REDUCED.value,
        ParticipantActionType.POSITION_EXITED.value,
        ParticipantActionType.INSTITUTIONAL_HOLDING_SNAPSHOT.value,
    }:
        return "institutional"
    return None


def classify_participant_stance(action: dict[str, Any]) -> str | None:
    """Map a participant action to BULLISH/BEARISH/NEUTRAL or None when non-directional."""
    action_type = str(action.get("action_type", ""))
    if action_type in _BULLISH_ACTIONS:
        if action_type == ParticipantActionType.OPEN_MARKET_BUY.value:
            discretion = str(action.get("insider_discretion", ""))
            if discretion and discretion not in {
                InsiderDiscretion.DISCRETIONARY.value,
                InsiderDiscretion.UNKNOWN.value,
            }:
                return None
        return ParticipantStanceDirection.BULLISH.value
    if action_type in _BEARISH_ACTIONS:
        if action_type == ParticipantActionType.OPEN_MARKET_SELL.value:
            discretion = str(action.get("insider_discretion", ""))
            if discretion == InsiderDiscretion.COMPENSATION.value:
                return None
        return ParticipantStanceDirection.BEARISH.value
    if action_type == ParticipantActionType.INSTITUTIONAL_HOLDING_SNAPSHOT.value:
        return ParticipantStanceDirection.NEUTRAL.value
    return None


def _filter_pit_actions(
    actions: list[dict[str, Any]],
    *,
    prediction_cutoff: int,
    lookback_days: int,
) -> list[dict[str, Any]]:
    cutoff_date = datetime.fromtimestamp(prediction_cutoff / 1_000_000_000, tz=timezone.utc).date()
    window_start = cutoff_date - timedelta(days=lookback_days)
    eligible: list[dict[str, Any]] = []
    for action in actions:
        available_ns = _parse_time_ns(action.get("available_time"))
        if available_ns > prediction_cutoff:
            continue
        available = _available_date(action.get("available_time"))
        if available < window_start or available > cutoff_date:
            continue
        eligible.append(action)
    return eligible


def _latest_stances_by_participant(
    actions: list[dict[str, Any]],
    *,
    affiliation_groups: dict[str, str],
) -> list[ParticipantStanceSummary]:
    by_participant: dict[str, tuple[int, dict[str, Any]]] = {}
    for action in actions:
        participant_id = str(action.get("participant_id", ""))
        if not participant_id:
            continue
        cohort = _participant_cohort(action)
        if cohort is None:
            continue
        stance = classify_participant_stance(action)
        if stance is None:
            continue
        available_ns = _parse_time_ns(action.get("available_time"))
        current = by_participant.get(participant_id)
        if current is None or available_ns >= current[0]:
            by_participant[participant_id] = (available_ns, action)

    summaries: list[ParticipantStanceSummary] = []
    for participant_id, (_, action) in by_participant.items():
        cohort = _participant_cohort(action)
        if cohort is None:
            continue
        stance = classify_participant_stance(action)
        if stance is None:
            continue
        if stance == ParticipantStanceDirection.NEUTRAL.value:
            continue
        summaries.append(
            ParticipantStanceSummary(
                participant_id=participant_id,
                display_name=str(action.get("display_name", "")),
                cohort=cohort,
                stance=stance,
                independent_key=_independent_key(action, affiliation_groups=affiliation_groups),
                action_id=str(action.get("action_id", "")),
                available_time=str(action.get("available_time", "")),
                event_time=str(action.get("event_time", "")),
                quality_flags=tuple(action.get("quality_flags", [])),
            )
        )
    return summaries


def _cohort_direction(stances: list[ParticipantStanceSummary], cohort: str) -> str | None:
    cohort_stances = [item.stance for item in stances if item.cohort == cohort]
    if not cohort_stances:
        return None
    bullish = cohort_stances.count(ParticipantStanceDirection.BULLISH.value)
    bearish = cohort_stances.count(ParticipantStanceDirection.BEARISH.value)
    if bullish > 0 and bearish > 0:
        return None
    if bullish > 0:
        return ParticipantStanceDirection.BULLISH.value
    if bearish > 0:
        return ParticipantStanceDirection.BEARISH.value
    return ParticipantStanceDirection.NEUTRAL.value


def _independent_stances(stances: list[ParticipantStanceSummary]) -> list[ParticipantStanceSummary]:
    latest_by_key: dict[str, tuple[int, ParticipantStanceSummary]] = {}
    for item in stances:
        current = latest_by_key.get(item.independent_key)
        available_ns = _parse_time_ns(item.available_time)
        if current is None or available_ns >= current[0]:
            latest_by_key[item.independent_key] = (available_ns, item)
    return [entry[1] for entry in latest_by_key.values()]


def _compute_crowding_score(stances: list[ParticipantStanceSummary]) -> float | None:
    institutional = [item for item in stances if item.cohort == "institutional"]
    if len(institutional) < DEFAULT_MIN_INSTITUTIONAL:
        return None
    bullish = sum(1 for item in institutional if item.stance == ParticipantStanceDirection.BULLISH.value)
    bearish = sum(1 for item in institutional if item.stance == ParticipantStanceDirection.BEARISH.value)
    directional_count = bullish + bearish
    if directional_count == 0:
        return None
    majority = max(bullish, bearish)
    return round(majority / directional_count, 6)


def _compute_disagreement_score(stances: list[ParticipantStanceSummary]) -> float | None:
    if len(stances) < 2:
        return None
    bullish = sum(1 for item in stances if item.stance == ParticipantStanceDirection.BULLISH.value)
    bearish = sum(1 for item in stances if item.stance == ParticipantStanceDirection.BEARISH.value)
    directional_count = bullish + bearish
    if directional_count < 2:
        return None
    if bullish > 0 and bearish > 0:
        minority = min(bullish, bearish)
        return round(minority / directional_count, 6)
    return 0.0


def _classify_regime(
    independent_stances: list[ParticipantStanceSummary],
    *,
    min_independent: int,
) -> ParticipantAlignmentRegime:
    directional = [
        item
        for item in independent_stances
        if item.stance in {
            ParticipantStanceDirection.BULLISH.value,
            ParticipantStanceDirection.BEARISH.value,
        }
    ]
    if len(directional) < min_independent:
        return ParticipantAlignmentRegime.INSUFFICIENT_DATA

    bullish_keys = {
        item.independent_key
        for item in directional
        if item.stance == ParticipantStanceDirection.BULLISH.value
    }
    bearish_keys = {
        item.independent_key
        for item in directional
        if item.stance == ParticipantStanceDirection.BEARISH.value
    }
    if bullish_keys and bearish_keys:
        return ParticipantAlignmentRegime.DISAGREEMENT

    aligned_keys = bullish_keys or bearish_keys
    if len(aligned_keys) >= min_independent:
        return ParticipantAlignmentRegime.CONSENSUS
    return ParticipantAlignmentRegime.MIXED


def _collect_quality_flags(
    stances: list[ParticipantStanceSummary],
    *,
    affiliation_groups: dict[str, str],
    actions: list[dict[str, Any]],
) -> tuple[str, ...]:
    flags: set[str] = set()
    for item in stances:
        flags.update(item.quality_flags)
    for action in actions:
        for flag in action.get("quality_flags", []):
            if flag == ParticipantQualityFlag.POSITION_STALE.value:
                flags.add(ParticipantQualityFlag.CROWDING_DATA_STALE.value)
    if not affiliation_groups:
        display_names = {str(action.get("display_name", "")) for action in actions}
        prefixes: dict[str, int] = {}
        for name in display_names:
            if not name:
                continue
            prefix = name.split()[0]
            prefixes[prefix] = prefixes.get(prefix, 0) + 1
        if any(count > 1 for count in prefixes.values()):
            flags.add(ParticipantQualityFlag.AFFILIATION_UNRESOLVED.value)
    return tuple(sorted(flags))


def _select_cross_lane_signal(
    *,
    regime: ParticipantAlignmentRegime,
    crowding_score: float | None,
    disagreement_score: float | None,
    independent_stances: list[ParticipantStanceSummary],
    crowding_threshold: float,
    disagreement_threshold: float,
    min_institutional: int,
) -> str | None:
    if regime == ParticipantAlignmentRegime.INSUFFICIENT_DATA:
        return None

    institutional = [item for item in independent_stances if item.cohort == "institutional"]
    if (
        crowding_score is not None
        and crowding_score >= crowding_threshold
        and len(institutional) >= min_institutional
    ):
        return EvidenceSignal.PARTICIPANT_CROWDING_ELEVATED.value

    if regime == ParticipantAlignmentRegime.DISAGREEMENT:
        if disagreement_score is not None and disagreement_score >= disagreement_threshold:
            return EvidenceSignal.PARTICIPANT_DISAGREEMENT_ELEVATED.value
        bullish_keys = {
            item.independent_key
            for item in independent_stances
            if item.stance == ParticipantStanceDirection.BULLISH.value
        }
        bearish_keys = {
            item.independent_key
            for item in independent_stances
            if item.stance == ParticipantStanceDirection.BEARISH.value
        }
        if len(bullish_keys) >= 1 and len(bearish_keys) >= 1:
            return EvidenceSignal.PARTICIPANT_DISAGREEMENT_ELEVATED.value

    if regime == ParticipantAlignmentRegime.CONSENSUS:
        aligned_keys = {
            item.independent_key
            for item in independent_stances
            if item.stance
            in {ParticipantStanceDirection.BULLISH.value, ParticipantStanceDirection.BEARISH.value}
        }
        if len(aligned_keys) >= DEFAULT_MIN_INDEPENDENT:
            return EvidenceSignal.PARTICIPANT_CONSENSUS_ELEVATED.value
    return None


def compute_crowding_evidence(
    actions: list[dict[str, Any]],
    *,
    instrument_id: str,
    prediction_cutoff: int,
    crowding_fixture_path: Path | str | None = None,
) -> ParticipantCrowdingEvidence | None:
    if not actions:
        return None

    fixture = load_crowding_fixture(crowding_fixture_path)
    lookback_days = int(fixture.get("lookback_days", DEFAULT_LOOKBACK_DAYS))
    min_independent = int(fixture.get("min_independent_participants", DEFAULT_MIN_INDEPENDENT))
    min_institutional = int(
        fixture.get("min_institutional_participants_for_crowding", DEFAULT_MIN_INSTITUTIONAL)
    )
    crowding_threshold = float(fixture.get("crowding_score_threshold", DEFAULT_CROWDING_THRESHOLD))
    disagreement_threshold = float(
        fixture.get("disagreement_score_threshold", DEFAULT_DISAGREEMENT_THRESHOLD)
    )
    affiliation_groups_raw = fixture.get("affiliation_groups", {})
    affiliation_groups = (
        {str(k): str(v) for k, v in affiliation_groups_raw.items()}
        if isinstance(affiliation_groups_raw, dict)
        else {}
    )

    eligible = _filter_pit_actions(
        actions,
        prediction_cutoff=prediction_cutoff,
        lookback_days=lookback_days,
    )
    if not eligible:
        return None

    participant_stances = _latest_stances_by_participant(
        eligible,
        affiliation_groups=affiliation_groups,
    )
    independent_stances = _independent_stances(participant_stances)
    regime = _classify_regime(independent_stances, min_independent=min_independent)
    crowding_score = _compute_crowding_score(independent_stances)
    disagreement_score = _compute_disagreement_score(independent_stances)
    quality_flags = _collect_quality_flags(
        participant_stances,
        affiliation_groups=affiliation_groups,
        actions=eligible,
    )

    latest_action = max(eligible, key=lambda row: _parse_time_ns(row.get("available_time")))
    cross_lane_signal = _select_cross_lane_signal(
        regime=regime,
        crowding_score=crowding_score,
        disagreement_score=disagreement_score,
        independent_stances=independent_stances,
        crowding_threshold=crowding_threshold,
        disagreement_threshold=disagreement_threshold,
        min_institutional=min_institutional,
    )

    raw_participant_count = len(participant_stances)
    independent_count = len(independent_stances)

    return ParticipantCrowdingEvidence(
        instrument_id=instrument_id.upper(),
        alignment_regime=regime,
        insider_direction=_cohort_direction(independent_stances, "insider"),
        institutional_direction=_cohort_direction(independent_stances, "institutional"),
        activist_direction=_cohort_direction(independent_stances, "activist"),
        independent_participant_count=independent_count,
        affiliated_participant_count=max(raw_participant_count - independent_count, 0),
        crowding_score=crowding_score,
        disagreement_score=disagreement_score,
        event_time=str(latest_action.get("event_time", "")),
        available_time=str(latest_action.get("available_time", "")),
        producer_version=PRODUCER_VERSION,
        quality_flags=quality_flags,
        cross_lane_signal=cross_lane_signal,
        supporting_action_ids=tuple(item.action_id for item in participant_stances if item.action_id),
    )


def crowding_summary_to_dict(item: ParticipantCrowdingEvidence) -> dict[str, Any]:
    payload = participant_crowding_evidence_to_dict(item)
    payload["scoring_method"] = SCORING_METHOD
    return payload


def summarize_crowding(item: ParticipantCrowdingEvidence | None) -> dict[str, Any]:
    if item is None:
        return {
            "crowding_available": False,
            "alignment_regime": ParticipantAlignmentRegime.INSUFFICIENT_DATA.value,
            "cross_lane_signals": [],
            "producer_version": PRODUCER_VERSION,
        }
    signals = [item.cross_lane_signal] if item.cross_lane_signal else []
    return {
        "crowding_available": True,
        "alignment_regime": item.alignment_regime.value,
        "insider_direction": item.insider_direction,
        "institutional_direction": item.institutional_direction,
        "activist_direction": item.activist_direction,
        "independent_participant_count": item.independent_participant_count,
        "affiliated_participant_count": item.affiliated_participant_count,
        "crowding_score": item.crowding_score,
        "disagreement_score": item.disagreement_score,
        "cross_lane_signals": signals,
        "producer_version": PRODUCER_VERSION,
    }


def publish_crowding_signals(
    item: ParticipantCrowdingEvidence | None,
    *,
    prediction_cutoff: int,
) -> list[dict[str, Any]]:
    if item is None or item.cross_lane_signal is None:
        return []
    if _parse_time_ns(item.available_time) > prediction_cutoff:
        return []
    if item.alignment_regime == ParticipantAlignmentRegime.INSUFFICIENT_DATA:
        return []

    detail = (
        f"{item.instrument_id} alignment={item.alignment_regime.value} "
        f"crowding={item.crowding_score} disagreement={item.disagreement_score}; research only"
    )
    return [
        lane_evidence_to_dict(
            NormalizedLaneEvidence(
                lane=LaneId.PARTICIPANT_INTELLIGENCE,
                signal=EvidenceSignal(item.cross_lane_signal),
                strength="MODERATE",
                available=True,
                source_ref=f"participant:crowding:{item.instrument_id}",
                detail=detail,
                observed_at=item.available_time,
                quality_flags=item.quality_flags,
                provenance_class=EvidenceProvenanceClass.DERIVED,
            )
        )
    ]


def build_participant_crowding_bundle(
    actions: list[dict[str, Any]],
    *,
    instrument_id: str,
    prediction_cutoff: int,
    crowding_fixture_path: Path | str | None = None,
) -> dict[str, Any]:
    if not actions:
        return {
            "available": False,
            "reason": "NO_PARTICIPANT_ACTIONS",
            "summary": summarize_crowding(None),
            "evidence": None,
            "stance_summaries": [],
        }
    evidence = compute_crowding_evidence(
        actions,
        instrument_id=instrument_id,
        prediction_cutoff=prediction_cutoff,
        crowding_fixture_path=crowding_fixture_path,
    )
    return {
        "available": evidence is not None,
        "summary": summarize_crowding(evidence),
        "evidence": crowding_summary_to_dict(evidence) if evidence is not None else None,
        "stance_summaries": [],
    }
