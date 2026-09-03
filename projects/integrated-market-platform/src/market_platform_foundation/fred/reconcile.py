"""V1/V2 reconciliation and V2 mixed-release consistency detection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .contracts import MacroObservation
from .quality import FredQualityFlag
from .registry import lookup_series
from .v2_client import V2ReleaseSnapshot


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    series_id: str
    observation_date: str
    v1_value: str | None
    v2_value: str | None
    match: bool
    quality_flags: tuple[str, ...]


def reconcile_current_values(
    *,
    v1_observation: MacroObservation | None,
    v2_observation: MacroObservation | None,
) -> ReconciliationResult:
    series_id = v1_observation.series_id if v1_observation else (v2_observation.series_id if v2_observation else "")
    observation_date = (
        v1_observation.observation_date
        if v1_observation
        else (v2_observation.observation_date if v2_observation else "")
    )
    v1_value = v1_observation.raw_value if v1_observation else None
    v2_value = v2_observation.raw_value if v2_observation else None
    flags: list[str] = []
    if v1_observation is None or v2_observation is None:
        flags.append(FredQualityFlag.SERIES_UNAVAILABLE.value)
        return ReconciliationResult(
            series_id=series_id,
            observation_date=observation_date,
            v1_value=v1_value,
            v2_value=v2_value,
            match=False,
            quality_flags=tuple(flags),
        )
    match = v1_value == v2_value and v1_observation.observation_date == v2_observation.observation_date
    if not match:
        flags.append(FredQualityFlag.V1_V2_RECONCILIATION_MISMATCH.value)
    return ReconciliationResult(
        series_id=series_id,
        observation_date=observation_date,
        v1_value=v1_value,
        v2_value=v2_value,
        match=match,
        quality_flags=tuple(flags),
    )


def detect_mixed_release_update(
    snapshot: V2ReleaseSnapshot,
    *,
    configured_series: set[str],
    prior_last_updated: dict[str, str] | None = None,
    retrieval_started: str,
) -> tuple[str, tuple[str, ...]]:
    """Heuristic: subset of configured series updated in this fetch while others unchanged from prior.

    A release mid-update shows a bimodal last_updated pattern among configured Tier-1 members
    where some series last_updated >= retrieval_started and others remain on older timestamps
    while prior snapshot expected a coordinated release refresh.
    """
    flags: list[str] = []
    if not configured_series:
        return "UNKNOWN", tuple(flags)

    updated_now: set[str] = set()
    stale: set[str] = set()
    for series_id in configured_series:
        current = snapshot.series_last_updated.get(series_id, "")
        if not current:
            continue
        if current >= retrieval_started[:10]:
            updated_now.add(series_id)
        else:
            stale.add(series_id)

    if prior_last_updated:
        transitioning = {
            sid
            for sid in configured_series
            if sid in snapshot.series_last_updated
            and sid in prior_last_updated
            and snapshot.series_last_updated[sid] != prior_last_updated[sid]
        }
        if transitioning and stale and updated_now:
            flags.append(FredQualityFlag.MIXED_RELEASE_UPDATE.value)
            return "MIXED_RELEASE_UPDATE", tuple(flags)

    if updated_now and stale and len(updated_now) < len(configured_series):
        flags.append(FredQualityFlag.MIXED_RELEASE_UPDATE.value)
        return "MIXED_RELEASE_UPDATE", tuple(flags)
    return "STABLE", tuple(flags)


def configured_series_for_release(release_id: int) -> set[str]:
    from .registry import TIER1_REGISTRY

    return {entry.fred_series_id for entry in TIER1_REGISTRY if entry.fred_release_id == release_id}


def release_snapshot_metadata(
    snapshot: V2ReleaseSnapshot,
    *,
    retrieval_started: str,
    retrieval_finished: str,
    response_hashes: list[str],
) -> dict[str, Any]:
    consistency, flags = detect_mixed_release_update(
        snapshot,
        configured_series=configured_series_for_release(snapshot.release_id),
        retrieval_started=retrieval_started,
    )
    return {
        "release_id": snapshot.release_id,
        "retrieval_started": retrieval_started,
        "retrieval_finished": retrieval_finished,
        "page_count": len(snapshot.pages),
        "series_count": snapshot.series_count,
        "observation_count": snapshot.observation_count,
        "has_more_final": False if snapshot.complete else True,
        "response_hashes": response_hashes,
        "series_last_updated": dict(snapshot.series_last_updated),
        "consistency_result": consistency,
        "quality_flags": list(flags),
    }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000000000Z")


__all__ = [
    "ReconciliationResult",
    "configured_series_for_release",
    "detect_mixed_release_update",
    "reconcile_current_values",
    "release_snapshot_metadata",
    "utc_now_iso",
]
