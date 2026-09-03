"""ALFRED point-in-time reconstruction and macro_as_of queries."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any

from .availability import AvailabilityPrecision, knowledge_interval_contains
from .contracts import MacroIndicatorValue, MacroObservation, MacroRegimeState
from .quality import FredQualityFlag
from .registry import MacroDomain, TIER1_REGISTRY, lookup_canonical


def _parse_iso(value: str) -> datetime:
    text = value.replace("Z", "+00:00")
    if len(text) == 10:
        dt = datetime.fromisoformat(text)
        return dt.replace(tzinfo=timezone.utc)
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _days_between(earlier: str, later: str) -> int | None:
    if not earlier or not later:
        return None
    try:
        return (_parse_iso(later) - _parse_iso(earlier)).days
    except ValueError:
        return None


@dataclass
class RevisionSequence:
    """Deterministic revision fixture: E @ T1=100, T2=98, T3=99."""

    observation_date: str
    revisions: tuple[tuple[str, str, float | None], ...]

    def as_of(self, decision_time: str) -> tuple[float | None, str, tuple[str, ...]]:
        flags: list[str] = []
        chosen_value: float | None = None
        chosen_available = ""
        for available_time, raw, normalized in self.revisions:
            if decision_time >= available_time:
                chosen_value = normalized
                chosen_available = available_time
            else:
                break
        if chosen_available == "":
            flags.append(FredQualityFlag.PIT_UNAVAILABLE.value)
            return None, "", tuple(flags)
        return chosen_value, chosen_available, tuple(flags)


DEFAULT_REVISION_FIXTURE = RevisionSequence(
    observation_date="2020-01-01",
    revisions=(
        ("2020-01-15T13:30:00Z", "100", 100.0),
        ("2020-02-14T13:30:00Z", "98", 98.0),
        ("2020-03-13T13:30:00Z", "99", 99.0),
    ),
)


def _observation_visible_at(obs: MacroObservation, decision_time: str) -> tuple[bool, tuple[str, ...]]:
    if obs.api_version == "v2" or obs.availability_precision == AvailabilityPrecision.SNAPSHOT.value:
        return False, ()
    start = obs.knowledge_start_date or obs.realtime_start
    end = obs.knowledge_end_date or obs.realtime_end
    if start:
        return knowledge_interval_contains(
            decision_time,
            knowledge_start=start,
            knowledge_end=end,
            availability_precision=obs.availability_precision,
            available_time=obs.available_time,
        )
    if obs.available_time:
        return obs.available_time <= decision_time, ()
    return False, ()


def select_pit_observation(
    observations: list[MacroObservation],
    *,
    decision_time: str,
    canonical_indicator_id: str,
    observation_date: str | None = None,
) -> MacroObservation | None:
    candidates: list[tuple[MacroObservation, tuple[str, ...]]] = []
    for obs in observations:
        if obs.canonical_indicator_id != canonical_indicator_id:
            continue
        if observation_date is not None and obs.observation_date != observation_date:
            continue
        visible, flags = _observation_visible_at(obs, decision_time)
        if visible:
            candidates.append((obs, flags))
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda item: (
            item[0].knowledge_start_date or item[0].realtime_start or item[0].available_time,
            item[0].revision_number,
        ),
    )[0]


def macro_as_of(
    observations: list[MacroObservation],
    *,
    canonical_indicator_id: str,
    decision_time: str,
    pit_available: bool = True,
) -> MacroIndicatorValue:
    if not pit_available:
        return MacroIndicatorValue(
            canonical_indicator_id=canonical_indicator_id,
            value=None,
            raw_value=None,
            observation_date="",
            available_time="",
            knowledge_age_days=None,
            observation_age_days=None,
            revision_state="PIT_UNAVAILABLE",
            quality_flags=(FredQualityFlag.PIT_UNAVAILABLE.value,),
        )
    obs = select_pit_observation(
        observations,
        decision_time=decision_time,
        canonical_indicator_id=canonical_indicator_id,
    )
    if obs is None:
        return MacroIndicatorValue(
            canonical_indicator_id=canonical_indicator_id,
            value=None,
            raw_value=None,
            observation_date="",
            available_time="",
            knowledge_age_days=None,
            observation_age_days=None,
            revision_state="UNKNOWN",
            quality_flags=(FredQualityFlag.PIT_UNAVAILABLE.value,),
        )
    revision_state = "INITIAL" if obs.revision_number == 0 else f"REVISION_{obs.revision_number}"
    knowledge_anchor = obs.knowledge_start_date or obs.available_time
    return MacroIndicatorValue(
        canonical_indicator_id=canonical_indicator_id,
        value=obs.normalized_value,
        raw_value=obs.raw_value,
        observation_date=obs.observation_date,
        available_time=knowledge_anchor,
        knowledge_age_days=_days_between(knowledge_anchor, decision_time),
        observation_age_days=_days_between(obs.observation_date, decision_time),
        revision_state=revision_state,
        quality_flags=obs.quality_flags,
        provenance_ref=obs.provenance_ref,
    )


def macro_state_as_of(
    observations: list[MacroObservation],
    *,
    decision_time: str,
    pit_available: bool = True,
) -> MacroRegimeState:
    blocks: dict[MacroDomain, dict[str, MacroIndicatorValue | None]] = {
        domain: {} for domain in MacroDomain
    }
    quality: list[str] = []
    for entry in TIER1_REGISTRY:
        value = macro_as_of(
            observations,
            canonical_indicator_id=entry.canonical_indicator_id,
            decision_time=decision_time,
            pit_available=pit_available,
        )
        blocks[entry.domain][entry.canonical_indicator_id] = value
        quality.extend(value.quality_flags)
    return MacroRegimeState(
        rates=blocks[MacroDomain.RATES],
        yield_curve=blocks[MacroDomain.YIELD_CURVE],
        inflation=blocks[MacroDomain.INFLATION],
        labor=blocks[MacroDomain.LABOR],
        growth=blocks[MacroDomain.GROWTH],
        liquidity=blocks[MacroDomain.LIQUIDITY],
        credit=blocks[MacroDomain.CREDIT],
        financial_conditions=blocks[MacroDomain.FINANCIAL_CONDITIONS],
        usd=blocks[MacroDomain.USD],
        decision_time=decision_time,
        quality_flags=tuple(dict.fromkeys(quality)),
        provenance_ref="fred.macro_state_as_of",
    )


def observations_from_v1_realtime_rows(
    rows: list[dict[str, Any]],
    *,
    canonical_indicator_id: str,
    series_id: str,
    retrieved_time: str,
) -> list[MacroObservation]:
    from .normalize import normalize_v1_observation_row
    from .registry import lookup_canonical

    entry = lookup_canonical(canonical_indicator_id)
    if entry is None:
        return []
    result: list[MacroObservation] = []
    revision = 0
    for row in rows:
        obs = normalize_v1_observation_row(
            row,
            entry=entry,
            retrieved_time=retrieved_time,
            observed_time=str(row.get("provider_first_observed_time", "")),
        )
        obs = replace(
            obs,
            revision_number=revision,
            initial_release_value=obs.raw_value if revision == 0 else obs.initial_release_value,
        )
        revision += 1
        result.append(obs)
    return result


__all__ = [
    "DEFAULT_REVISION_FIXTURE",
    "RevisionSequence",
    "macro_as_of",
    "macro_state_as_of",
    "observations_from_v1_realtime_rows",
    "select_pit_observation",
]
