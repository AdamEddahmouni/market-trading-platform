"""Futures COT / OI positioning engine (F4) — crowding features, not directional inference."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from ..contracts.futures import (
    cot_point_in_time_valid,
    positioning_snapshot_to_dict,
    FuturesPositioningSnapshot,
)
from ..contracts.futures_quality import (
    FuturesQualityFlag,
    quality_blocks_positioning_interpretation,
)
from ..normalization.equity_bars import iso_to_epoch_ns
from ..providers.contracts import ProviderResult

POSITIONING_VERSION = "futures_positioning_v1"
CROWDED_LONG_THRESHOLD = 0.80
CROWDED_SHORT_THRESHOLD = 0.20


class CrowdingRegime(StrEnum):
    CROWDED_LONG = "CROWDED_LONG"
    CROWDED_SHORT = "CROWDED_SHORT"
    NEUTRAL = "NEUTRAL"


class OiVelocityHypothesis(StrEnum):
    OI_RISING_WITH_PRICE = "OI_RISING_WITH_PRICE"
    OI_RISING_AGAINST_PRICE = "OI_RISING_AGAINST_PRICE"
    OI_FALLING = "OI_FALLING"
    OI_STABLE = "OI_STABLE"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class OiVelocityObservation:
    """OI change hypothesis — not a directional forecast."""

    label: str
    front_oi_delta: int | None = None
    front_price_delta: float | None = None
    disclaimer: str = "OI change ≠ directional forecast; every contract has a long and short"
    quality_flags: tuple[str, ...] = field(default_factory=tuple)


def compute_net(snapshot: FuturesPositioningSnapshot) -> int | None:
    if snapshot.net is not None:
        return snapshot.net
    if snapshot.long_positions is not None and snapshot.short_positions is not None:
        return snapshot.long_positions - snapshot.short_positions
    return None


def _decision_time_iso(decision_time: int | str) -> str:
    if isinstance(decision_time, int):
        secs = decision_time // 1_000_000_000
        dt = datetime.fromtimestamp(secs, tz=timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%S.000000000Z")
    return str(decision_time)


def _parse_date(value: str) -> datetime | None:
    if not value:
        return None
    text = value
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def filter_pit_reports(
    reports: list[dict[str, Any]],
    decision_time: int | str,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Return PIT-valid COT reports and accumulated quality flags."""
    decision_iso = _decision_time_iso(decision_time)
    quality_flags: list[str] = []
    pit_valid: list[dict[str, Any]] = []
    pending_observation = False

    for report in reports:
        observation_time = str(report.get("observation_time", ""))
        publication_time = str(report.get("publication_time", ""))
        if cot_point_in_time_valid(observation_time, publication_time, decision_iso):
            pit_valid.append(report)
        elif observation_time and publication_time:
            obs_dt = _parse_date(observation_time)
            pub_dt = _parse_date(publication_time)
            dec_dt = _parse_date(decision_iso)
            if obs_dt and pub_dt and dec_dt and obs_dt <= dec_dt < pub_dt:
                pending_observation = True

    if not pit_valid:
        quality_flags.append(FuturesQualityFlag.POSITIONING_UNKNOWN.value)
    if pending_observation:
        quality_flags.append(FuturesQualityFlag.COT_PUBLICATION_PENDING.value)

    pit_valid.sort(key=lambda row: str(row.get("publication_time", "")))
    return pit_valid, quality_flags


def compute_net_percentile(current_net: int, history_nets: list[int]) -> float | None:
    if not history_nets:
        return None
    sorted_nets = sorted(history_nets)
    rank = sum(1 for value in sorted_nets if value <= current_net)
    return rank / len(sorted_nets)


def compute_net_zscore(current_net: int, history_nets: list[int]) -> float | None:
    if len(history_nets) < 2:
        return None
    mean = sum(history_nets) / len(history_nets)
    variance = sum((value - mean) ** 2 for value in history_nets) / len(history_nets)
    if variance <= 0:
        return 0.0
    return (current_net - mean) / math.sqrt(variance)


def crowding_regime(net_percentile: float | None) -> CrowdingRegime:
    if net_percentile is None:
        return CrowdingRegime.NEUTRAL
    if net_percentile >= CROWDED_LONG_THRESHOLD:
        return CrowdingRegime.CROWDED_LONG
    if net_percentile <= CROWDED_SHORT_THRESHOLD:
        return CrowdingRegime.CROWDED_SHORT
    return CrowdingRegime.NEUTRAL


def compute_oi_velocity(chain_result: ProviderResult) -> OiVelocityObservation:
    """Derive OI velocity hypothesis from chain contracts — label only."""
    if chain_result.status != "available" or not chain_result.events:
        return OiVelocityObservation(label=OiVelocityHypothesis.UNAVAILABLE.value)

    contracts = [row for row in chain_result.events if isinstance(row, dict)]
    if len(contracts) < 1:
        return OiVelocityObservation(label=OiVelocityHypothesis.UNAVAILABLE.value)

    front = contracts[0]
    front_oi = front.get("open_interest")
    front_price = front.get("price") or front.get("close") or front.get("settlement_price")
    if front_oi is None:
        return OiVelocityObservation(label=OiVelocityHypothesis.UNAVAILABLE.value)

    oi_history = front.get("open_interest_history")
    if not isinstance(oi_history, list) or len(oi_history) < 2:
        return OiVelocityObservation(
            label=OiVelocityHypothesis.OI_STABLE.value,
            front_oi_delta=0,
        )

    prev_oi = oi_history[-2].get("open_interest") if isinstance(oi_history[-2], dict) else None
    prev_price = oi_history[-2].get("price") if isinstance(oi_history[-2], dict) else None
    if prev_oi is None:
        return OiVelocityObservation(label=OiVelocityHypothesis.UNAVAILABLE.value)

    oi_delta = int(front_oi) - int(prev_oi)
    price_delta: float | None = None
    if front_price is not None and prev_price is not None:
        price_delta = float(front_price) - float(prev_price)

    if abs(oi_delta) < 1000:
        label = OiVelocityHypothesis.OI_STABLE.value
    elif oi_delta > 0:
        if price_delta is not None and price_delta > 0:
            label = OiVelocityHypothesis.OI_RISING_WITH_PRICE.value
        elif price_delta is not None and price_delta < 0:
            label = OiVelocityHypothesis.OI_RISING_AGAINST_PRICE.value
        else:
            label = OiVelocityHypothesis.OI_RISING_WITH_PRICE.value
    else:
        label = OiVelocityHypothesis.OI_FALLING.value

    return OiVelocityObservation(
        label=label,
        front_oi_delta=oi_delta,
        front_price_delta=price_delta,
    )


def _data_age_days(observation_time: str, decision_time: int | str) -> int | None:
    obs_dt = _parse_date(observation_time)
    if obs_dt is None:
        return None
    if isinstance(decision_time, int):
        dec_dt = datetime.fromtimestamp(decision_time // 1_000_000_000, tz=timezone.utc)
    else:
        dec_dt = _parse_date(_decision_time_iso(decision_time))
    if dec_dt is None:
        return None
    return (dec_dt.date() - obs_dt.date()).days


def build_positioning_snapshot(
    latest_report: dict[str, Any],
    history_reports: list[dict[str, Any]],
    *,
    decision_time: int | str,
) -> FuturesPositioningSnapshot:
    history_nets: list[int] = []
    for report in history_reports:
        net = report.get("net")
        if net is None:
            long_pos = report.get("long_positions")
            short_pos = report.get("short_positions")
            if long_pos is not None and short_pos is not None:
                net = int(long_pos) - int(short_pos)
        if net is not None:
            history_nets.append(int(net))

    current_net = latest_report.get("net")
    if current_net is None:
        long_pos = latest_report.get("long_positions")
        short_pos = latest_report.get("short_positions")
        if long_pos is not None and short_pos is not None:
            current_net = int(long_pos) - int(short_pos)

    net_percentile = (
        compute_net_percentile(int(current_net), history_nets) if current_net is not None else None
    )
    net_zscore = (
        compute_net_zscore(int(current_net), history_nets) if current_net is not None else None
    )

    prev_net = history_nets[-2] if len(history_nets) >= 2 else None
    net_change = (
        int(current_net) - int(prev_net)
        if current_net is not None and prev_net is not None
        else None
    )

    observation_time = str(latest_report.get("observation_time", ""))
    quality_flags = list(latest_report.get("quality_flags", []) or [])

    return FuturesPositioningSnapshot(
        instrument_family=str(latest_report.get("instrument_family", "")),
        report_type=str(latest_report.get("report_type", "")),
        participant_category=str(latest_report.get("participant_category", "")),
        long_positions=int(latest_report["long_positions"]) if latest_report.get("long_positions") is not None else None,
        short_positions=int(latest_report["short_positions"]) if latest_report.get("short_positions") is not None else None,
        spreading=int(latest_report["spreading"]) if latest_report.get("spreading") is not None else None,
        net=int(current_net) if current_net is not None else None,
        net_change=net_change,
        net_percentile=net_percentile,
        net_zscore=round(net_zscore, 6) if net_zscore is not None else None,
        observation_time=observation_time,
        publication_time=str(latest_report.get("publication_time", "")),
        data_age_days=_data_age_days(observation_time, decision_time),
        quality_flags=tuple(quality_flags),
        provenance_ref=str(latest_report.get("provenance_ref", "cot.fixture.futures_positioning")),
    )


def oi_velocity_to_dict(observation: OiVelocityObservation) -> dict[str, Any]:
    return {
        "label": observation.label,
        "front_oi_delta": observation.front_oi_delta,
        "front_price_delta": observation.front_price_delta,
        "disclaimer": observation.disclaimer,
        "quality_flags": list(observation.quality_flags),
    }


def positioning_payload(
    positioning_result: ProviderResult,
    chain_result: ProviderResult,
    *,
    decision_time: int | str,
) -> dict[str, Any]:
    """Build workspace positioning payload with fail-closed semantics."""
    quality_flags: list[str] = []

    if positioning_result.status != "available" or not positioning_result.events:
        oi_obs = compute_oi_velocity(chain_result)
        return {
            "available": False,
            "reason": positioning_result.reason_code or "POSITIONING_UNAVAILABLE",
            "futures_positioning_available": False,
            "oi_velocity_hypothesis": oi_velocity_to_dict(oi_obs),
            "positioning_version": POSITIONING_VERSION,
        }

    reports = [row for row in positioning_result.events if isinstance(row, dict)]
    pit_reports, pit_flags = filter_pit_reports(reports, decision_time)
    quality_flags.extend(pit_flags)

    if not pit_reports:
        oi_obs = compute_oi_velocity(chain_result)
        return {
            "available": False,
            "reason": "COT_NOT_PIT_ELIGIBLE",
            "futures_positioning_available": False,
            "oi_velocity_hypothesis": oi_velocity_to_dict(oi_obs),
            "quality_flags": quality_flags,
            "positioning_version": POSITIONING_VERSION,
        }

    latest_report = pit_reports[-1]
    history_for_stats = pit_reports[:-1] if len(pit_reports) > 1 else pit_reports
    snapshot = build_positioning_snapshot(
        latest_report,
        history_for_stats,
        decision_time=decision_time,
    )

    combined_flags = tuple(dict.fromkeys(list(snapshot.quality_flags) + quality_flags))
    if quality_blocks_positioning_interpretation(combined_flags):
        snapshot = FuturesPositioningSnapshot(
            instrument_family=snapshot.instrument_family,
            report_type=snapshot.report_type,
            participant_category=snapshot.participant_category,
            long_positions=snapshot.long_positions,
            short_positions=snapshot.short_positions,
            spreading=snapshot.spreading,
            net=snapshot.net,
            net_change=snapshot.net_change,
            net_percentile=snapshot.net_percentile,
            net_zscore=snapshot.net_zscore,
            observation_time=snapshot.observation_time,
            publication_time=snapshot.publication_time,
            data_age_days=snapshot.data_age_days,
            quality_flags=combined_flags,
            provenance_ref=snapshot.provenance_ref,
        )

    oi_obs = compute_oi_velocity(chain_result)
    regime = crowding_regime(snapshot.net_percentile)
    payload = positioning_snapshot_to_dict(snapshot)
    payload["available"] = not quality_blocks_positioning_interpretation(combined_flags)
    payload["crowding_regime"] = regime.value
    payload["positioning_version"] = POSITIONING_VERSION

    return {
        "available": payload["available"],
        "positioning_snapshot": payload,
        "futures_positioning_available": payload["available"],
        "crowding_regime": regime.value,
        "oi_velocity_hypothesis": oi_velocity_to_dict(oi_obs),
        "quality_flags": list(combined_flags),
        "positioning_version": POSITIONING_VERSION,
    }


__all__ = [
    "CROWDED_LONG_THRESHOLD",
    "CROWDED_SHORT_THRESHOLD",
    "CrowdingRegime",
    "OiVelocityHypothesis",
    "OiVelocityObservation",
    "POSITIONING_VERSION",
    "build_positioning_snapshot",
    "compute_net",
    "compute_net_percentile",
    "compute_net_zscore",
    "compute_oi_velocity",
    "crowding_regime",
    "filter_pit_reports",
    "oi_velocity_to_dict",
    "positioning_payload",
]
