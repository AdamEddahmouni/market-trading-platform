"""Point-in-time queries for EIA physical energy observations."""

from __future__ import annotations

from datetime import date, datetime, timezone

from .contracts import EnergyFundamentalObservation, EnergyReleaseFamily
from .quality import EiaQualityFlag
from .release_schedule import is_visible_at, release_for_period_end


def observation_visible(obs: EnergyFundamentalObservation, decision_time: str) -> bool:
    if not obs.available_time:
        return False
    return decision_time >= obs.available_time


def query_visible(
    observations: list[EnergyFundamentalObservation],
    *,
    decision_time: str,
    canonical_indicator_id: str | None = None,
    release_family: EnergyReleaseFamily | None = None,
) -> list[EnergyFundamentalObservation]:
    visible: list[EnergyFundamentalObservation] = []
    for obs in observations:
        if canonical_indicator_id and obs.canonical_indicator_id != canonical_indicator_id:
            continue
        if release_family and obs.release_family != release_family:
            continue
        if observation_visible(obs, decision_time):
            visible.append(obs)
    visible.sort(key=lambda item: (item.period_end, item.available_time))
    return visible


def latest_visible_or_flags(
    observations: list[EnergyFundamentalObservation],
    *,
    decision_time: str,
    canonical_indicator_id: str,
) -> tuple[EnergyFundamentalObservation | None, tuple[str, ...]]:
    visible = query_visible(
        observations,
        decision_time=decision_time,
        canonical_indicator_id=canonical_indicator_id,
    )
    if visible:
        latest = visible[-1]
        return latest, latest.quality_flags

    pending = [
        obs
        for obs in observations
        if obs.canonical_indicator_id == canonical_indicator_id and not observation_visible(obs, decision_time)
    ]
    if pending:
        release = release_for_period_end(
            date.fromisoformat(pending[-1].period_end),
            pending[-1].release_family,
        )
        if release is not None:
            query_dt = datetime.fromisoformat(decision_time.replace("Z", "+00:00"))
            if not is_visible_at(release, query_dt):
                return None, (EiaQualityFlag.REPORT_NOT_YET_RELEASED.value,)
        return None, (EiaQualityFlag.EXPECTED_NOT_YET_RELEASED.value,)
    return None, (EiaQualityFlag.SERIES_UNAVAILABLE.value,)


def energy_as_of(
    observations: list[EnergyFundamentalObservation],
    *,
    decision_time: str,
    canonical_indicator_id: str,
) -> EnergyFundamentalObservation | None:
    latest, _flags = latest_visible_or_flags(
        observations,
        decision_time=decision_time,
        canonical_indicator_id=canonical_indicator_id,
    )
    return latest


__all__ = [
    "energy_as_of",
    "latest_visible_or_flags",
    "observation_visible",
    "query_visible",
]
