"""Participant walk-forward skill estimation — PI5.

Outcome-linked skill with Bayesian shrinkage. Skill at prediction_cutoff uses
only actions with available_time <= cutoff. Never emits permanent smart-money labels.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ..contracts.participant import (
    IdentityConfidence,
    InsiderDiscretion,
    ParticipantActionType,
    ParticipantQualityFlag,
    ParticipantType,
    SkillDimension,
    SkillEstimate,
    ParticipantSkillSnapshot,
    participant_skill_snapshot_to_dict,
    skill_estimate_to_dict,
)
from ..cross_lane.evidence import EvidenceSignal
from ..normalization.equity_bars import iso_to_epoch_ns
from ..research.walk_forward import build_walk_forward_folds, verify_fold_pit

PRODUCER_VERSION = "participant_skill_v1"
DEFAULT_PRICE_OUTCOME_FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "participant"
    / "biya_price_outcomes.json"
)

MIN_SAMPLE = 3
SHRINKAGE_K = 5
DEFAULT_PRIOR = 0.0
BUY_WINDOW_DAYS = 20
SELL_WINDOW_DAYS = 20
ACTIVISM_WINDOW_DAYS = 60
SKILL_ELEVATED_THRESHOLD = 0.05
SKILL_BELOW_BASELINE_THRESHOLD = -0.02

_DIMENSION_WINDOWS: dict[SkillDimension, int] = {
    SkillDimension.BUY_SKILL: BUY_WINDOW_DAYS,
    SkillDimension.SELL_SKILL: SELL_WINDOW_DAYS,
    SkillDimension.ACTIVISM_SUCCESS: ACTIVISM_WINDOW_DAYS,
}


@dataclass(frozen=True, slots=True)
class ActionOutcome:
    action_id: str
    skill_group_key: str
    participant_id: str
    display_name: str
    participant_type: str
    dimension: SkillDimension
    available_time_ns: int
    forward_return: float
    outcome_window_days: int


def load_price_outcome_fixture(path: Path | str | None = None) -> dict[str, Any]:
    fixture_path = Path(path) if path is not None else DEFAULT_PRICE_OUTCOME_FIXTURE
    with fixture_path.open(encoding="utf-8") as handle:
        return json.load(handle)


def apply_shrinkage(
    raw_mean: float | None,
    *,
    sample_count: int,
    prior: float = DEFAULT_PRIOR,
    shrinkage_k: int = SHRINKAGE_K,
) -> float | None:
    if raw_mean is None or sample_count <= 0:
        return None
    weight = sample_count / (sample_count + shrinkage_k)
    return weight * raw_mean + (1.0 - weight) * prior


def _parse_available_time_ns(value: Any) -> int:
    if value is None:
        return 0
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if text.isdigit():
        return int(text)
    return iso_to_epoch_ns(text)


def _available_date(value: Any) -> date:
    ns = _parse_available_time_ns(value)
    seconds = ns / 1_000_000_000
    return datetime.fromtimestamp(seconds, tz=timezone.utc).date()


def _price_on_or_before(daily_closes: dict[str, float], target: date) -> float | None:
    eligible = [day for day in daily_closes if date.fromisoformat(day) <= target]
    if not eligible:
        return None
    latest = max(eligible)
    return float(daily_closes[latest])


def forward_return_from_prices(
    daily_closes: dict[str, float],
    *,
    available_time: Any,
    window_days: int,
    prediction_cutoff_ns: int,
) -> tuple[float | None, tuple[str, ...]]:
    flags: list[str] = []
    start_date = _available_date(available_time)
    end_date = start_date + timedelta(days=window_days)
    end_ns = iso_to_epoch_ns(end_date.isoformat() + "T23:59:59Z")
    if end_ns > prediction_cutoff_ns:
        flags.append(ParticipantQualityFlag.OUTCOME_WINDOW_INCOMPLETE.value)
        return None, tuple(flags)
    start_price = _price_on_or_before(daily_closes, start_date)
    end_price = _price_on_or_before(daily_closes, end_date)
    if start_price is None or end_price is None or start_price <= 0:
        flags.append(ParticipantQualityFlag.OUTCOME_WINDOW_INCOMPLETE.value)
        return None, tuple(flags)
    return (end_price / start_price) - 1.0, tuple(flags)


def skill_group_key_for_action(action: dict[str, Any]) -> str:
    identity_confidence = str(action.get("identity_confidence", ""))
    display_name = str(action.get("display_name", "")).strip()
    if identity_confidence == IdentityConfidence.KNOWN_IDENTITY.value and display_name:
        return display_name.upper()
    return str(action.get("participant_id", "unknown"))


def classify_skill_dimension(action: dict[str, Any]) -> SkillDimension | None:
    action_type = str(action.get("action_type", ""))
    discretion = action.get("insider_discretion")
    if (
        action_type == ParticipantActionType.OPEN_MARKET_BUY.value
        and discretion == InsiderDiscretion.DISCRETIONARY.value
    ):
        return SkillDimension.BUY_SKILL
    if action_type == ParticipantActionType.OPEN_MARKET_SELL.value:
        return SkillDimension.SELL_SKILL
    if action_type == ParticipantActionType.ACTIVIST_STAKE_INITIATED.value:
        return SkillDimension.ACTIVISM_SUCCESS
    return None


def build_action_outcomes(
    actions: list[dict[str, Any]],
    *,
    daily_closes: dict[str, float],
    prediction_cutoff: int,
) -> list[ActionOutcome]:
    outcomes: list[ActionOutcome] = []
    for action in actions:
        available_ns = _parse_available_time_ns(action.get("available_time"))
        if available_ns > prediction_cutoff:
            continue
        dimension = classify_skill_dimension(action)
        if dimension is None:
            continue
        window_days = _DIMENSION_WINDOWS[dimension]
        forward_return, _flags = forward_return_from_prices(
            daily_closes,
            available_time=available_ns,
            window_days=window_days,
            prediction_cutoff_ns=prediction_cutoff,
        )
        if forward_return is None:
            continue
        if dimension == SkillDimension.SELL_SKILL:
            forward_return = -forward_return
        outcomes.append(
            ActionOutcome(
                action_id=str(action.get("action_id", "")),
                skill_group_key=skill_group_key_for_action(action),
                participant_id=str(action.get("participant_id", "")),
                display_name=str(action.get("display_name", "")),
                participant_type=str(action.get("participant_type", ParticipantType.UNKNOWN.value)),
                dimension=dimension,
                available_time_ns=available_ns,
                forward_return=forward_return,
                outcome_window_days=window_days,
            )
        )
    return outcomes


def _estimate_dimension(
    outcomes: list[ActionOutcome],
    *,
    dimension: SkillDimension,
    prediction_cutoff: int,
) -> SkillEstimate:
    dimension_outcomes = [row for row in outcomes if row.dimension == dimension]
    visible = [row for row in dimension_outcomes if row.available_time_ns <= prediction_cutoff]
    sample_count = len(visible)
    flags: list[str] = []
    if sample_count < MIN_SAMPLE:
        flags.append(ParticipantQualityFlag.SKILL_INSUFFICIENT_SAMPLE.value)
        return SkillEstimate(
            dimension=dimension,
            raw_mean=None,
            shrunk_estimate=None,
            sample_count=sample_count,
            outcome_window_days=_DIMENSION_WINDOWS[dimension],
            prior=DEFAULT_PRIOR,
            shrinkage_k=SHRINKAGE_K,
            quality_flags=tuple(sorted(set(flags))),
        )
    raw_mean = sum(row.forward_return for row in visible) / sample_count
    shrunk = apply_shrinkage(raw_mean, sample_count=sample_count)
    return SkillEstimate(
        dimension=dimension,
        raw_mean=raw_mean,
        shrunk_estimate=shrunk,
        sample_count=sample_count,
        outcome_window_days=_DIMENSION_WINDOWS[dimension],
        prior=DEFAULT_PRIOR,
        shrinkage_k=SHRINKAGE_K,
        quality_flags=tuple(flags),
    )


def estimate_participant_skill(
    actions: list[dict[str, Any]],
    *,
    prediction_cutoff: int,
    daily_closes: dict[str, float],
) -> list[ParticipantSkillSnapshot]:
    outcomes = build_action_outcomes(
        actions,
        daily_closes=daily_closes,
        prediction_cutoff=prediction_cutoff,
    )
    observation_times = sorted({row.available_time_ns for row in outcomes})
    folds = build_walk_forward_folds(observation_times, min_train=2, test_size=1)
    pit_rows = [
        {
            "observation_time": row.available_time_ns,
            "prediction_cutoff": prediction_cutoff,
        }
        for row in outcomes
    ]
    verify_fold_pit(folds, pit_rows)

    grouped: dict[str, list[dict[str, Any]]] = {}
    meta: dict[str, dict[str, Any]] = {}
    for action in actions:
        if _parse_available_time_ns(action.get("available_time")) > prediction_cutoff:
            continue
        key = skill_group_key_for_action(action)
        grouped.setdefault(key, []).append(action)
        meta[key] = {
            "participant_id": str(action.get("participant_id", "")),
            "display_name": str(action.get("display_name", key)),
            "participant_type": ParticipantType(
                str(action.get("participant_type", ParticipantType.UNKNOWN.value))
            ),
        }

    snapshots: list[ParticipantSkillSnapshot] = []
    for key, group_actions in sorted(grouped.items()):
        group_outcomes = build_action_outcomes(
            group_actions,
            daily_closes=daily_closes,
            prediction_cutoff=prediction_cutoff,
        )
        estimates = (
            _estimate_dimension(group_outcomes, dimension=SkillDimension.BUY_SKILL, prediction_cutoff=prediction_cutoff),
            _estimate_dimension(group_outcomes, dimension=SkillDimension.SELL_SKILL, prediction_cutoff=prediction_cutoff),
            _estimate_dimension(
                group_outcomes,
                dimension=SkillDimension.ACTIVISM_SUCCESS,
                prediction_cutoff=prediction_cutoff,
            ),
        )
        group_flags: list[str] = []
        if not any(row.sample_count >= MIN_SAMPLE and row.shrunk_estimate is not None for row in estimates):
            group_flags.append(ParticipantQualityFlag.SKILL_INSUFFICIENT_SAMPLE.value)
        info = meta[key]
        snapshots.append(
            ParticipantSkillSnapshot(
                skill_group_key=key,
                participant_id=str(info["participant_id"]),
                display_name=str(info["display_name"]),
                participant_type=info["participant_type"],
                prediction_cutoff=prediction_cutoff,
                estimates=estimates,
                walk_forward_fold_count=len(folds),
                producer_version=PRODUCER_VERSION,
                quality_flags=tuple(sorted(set(group_flags))),
            )
        )
    return snapshots


def summarize_participant_skill(
    snapshots: list[ParticipantSkillSnapshot],
) -> dict[str, Any]:
    elevated = 0
    below_baseline = 0
    signals: list[str] = []
    by_participant: dict[str, Any] = {}

    for snapshot in snapshots:
        participant_payload: dict[str, Any] = {
            "skill_group_key": snapshot.skill_group_key,
            "participant_id": snapshot.participant_id,
            "display_name": snapshot.display_name,
            "walk_forward_fold_count": snapshot.walk_forward_fold_count,
            "quality_flags": list(snapshot.quality_flags),
            "dimensions": {},
        }
        for estimate in snapshot.estimates:
            participant_payload["dimensions"][estimate.dimension.value] = skill_estimate_to_dict(estimate)
            if ParticipantQualityFlag.SKILL_INSUFFICIENT_SAMPLE.value in estimate.quality_flags:
                continue
            if estimate.dimension == SkillDimension.BUY_SKILL and estimate.shrunk_estimate is not None:
                if estimate.shrunk_estimate >= SKILL_ELEVATED_THRESHOLD:
                    elevated += 1
                    signals.append(EvidenceSignal.PARTICIPANT_SKILL_ELEVATED.value)
                elif estimate.shrunk_estimate <= SKILL_BELOW_BASELINE_THRESHOLD:
                    below_baseline += 1
                    signals.append(EvidenceSignal.PARTICIPANT_SKILL_BELOW_BASELINE.value)
        by_participant[snapshot.display_name] = participant_payload

    skill_available = any(
        estimate.sample_count >= MIN_SAMPLE and estimate.shrunk_estimate is not None
        for snapshot in snapshots
        for estimate in snapshot.estimates
    )

    return {
        "skill_available": skill_available,
        "participant_count": len(snapshots),
        "elevated_participant_count": elevated,
        "below_baseline_participant_count": below_baseline,
        "participants": by_participant,
        "snapshots": [participant_skill_snapshot_to_dict(row) for row in snapshots],
        "cross_lane_signals": sorted(set(signals)),
        "producer_version": PRODUCER_VERSION,
    }


def build_participant_skill_bundle(
    actions: list[dict[str, Any]],
    *,
    prediction_cutoff: int,
    price_fixture_path: Path | str | None = None,
) -> dict[str, Any]:
    if not actions:
        return {
            "available": False,
            "reason": "NO_PARTICIPANT_ACTIONS",
            "summary": {"skill_available": False, "participant_count": 0},
            "snapshots": [],
        }
    fixture = load_price_outcome_fixture(price_fixture_path)
    daily_closes = fixture.get("daily_closes", {})
    if not isinstance(daily_closes, dict) or not daily_closes:
        return {
            "available": False,
            "reason": "PRICE_OUTCOME_FIXTURE_MISSING",
            "summary": {"skill_available": False, "participant_count": 0},
            "snapshots": [],
        }
    snapshots = estimate_participant_skill(
        actions,
        prediction_cutoff=prediction_cutoff,
        daily_closes={str(k): float(v) for k, v in daily_closes.items()},
    )
    summary = summarize_participant_skill(snapshots)
    return {
        "available": True,
        "summary": summary,
        "snapshots": summary["snapshots"],
    }
