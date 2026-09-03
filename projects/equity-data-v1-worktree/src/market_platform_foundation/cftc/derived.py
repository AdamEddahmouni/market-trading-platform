"""Deterministic derived COT features — MEASURED, not PREDICTIVE."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .contracts import InstitutionalPositioningObservation, InstitutionalPositioningState, CotReportFamily, CotPositionScope
from .quality import CotQualityFlag


@dataclass(frozen=True, slots=True)
class DerivedPositioningFeatures:
    net_position: int | None
    net_pct_open_interest: float | None
    weekly_net_change: int | None
    net_percentile_52w: float | None
    net_percentile_104w: float | None
    net_zscore: float | None
    long_short_ratio: float | None
    predictive: bool = False
    disclaimer: str = "weekly reported position change ≠ trade flow; classification changes may affect deltas"


def compute_net(obs: InstitutionalPositioningObservation) -> int | None:
    if obs.long_positions is not None and obs.short_positions is not None:
        return obs.long_positions - obs.short_positions
    return None


def compute_net_pct_oi(obs: InstitutionalPositioningObservation) -> float | None:
    net = compute_net(obs)
    if net is None or not obs.open_interest:
        return None
    return net / obs.open_interest


def compute_percentile(current: int, history: list[int]) -> float | None:
    if not history:
        return None
    sorted_vals = sorted(history)
    rank = sum(1 for value in sorted_vals if value <= current)
    return rank / len(sorted_vals)


def compute_zscore(current: int, history: list[int]) -> float | None:
    if len(history) < 2:
        return None
    mean = sum(history) / len(history)
    variance = sum((value - mean) ** 2 for value in history) / len(history)
    if variance <= 0:
        return 0.0
    return (current - mean) / math.sqrt(variance)


def derive_features(
    current: InstitutionalPositioningObservation,
    history: list[InstitutionalPositioningObservation],
) -> DerivedPositioningFeatures:
    net = compute_net(current)
    history_nets = [n for n in (compute_net(item) for item in history) if n is not None]
    weekly_change = None
    if net is not None and history_nets:
        weekly_change = net - history_nets[-1]
    long_short = None
    if current.long_positions and current.short_positions and current.short_positions != 0:
        long_short = current.long_positions / current.short_positions
    return DerivedPositioningFeatures(
        net_position=net,
        net_pct_open_interest=compute_net_pct_oi(current),
        weekly_net_change=weekly_change,
        net_percentile_52w=compute_percentile(net, history_nets[-52:]) if net is not None else None,
        net_percentile_104w=compute_percentile(net, history_nets[-104:]) if net is not None else None,
        net_zscore=compute_zscore(net, history_nets) if net is not None else None,
        long_short_ratio=long_short,
        predictive=False,
    )


def build_positioning_state(
    observations: list[InstitutionalPositioningObservation],
    *,
    contract_family_id: str,
    report_family: CotReportFamily,
    position_scope: CotPositionScope,
    decision_time: str,
) -> InstitutionalPositioningState | None:
    visible = [
        obs
        for obs in observations
        if obs.contract_family_id == contract_family_id
        and obs.report_family == report_family
        and obs.position_scope == position_scope
        and decision_time >= obs.publication_time
    ]
    if not visible:
        return None
    visible.sort(key=lambda item: item.publication_time)
    latest = visible[-1]
    history = visible[:-1]
    features = derive_features(latest, history)

    leveraged_or_managed = None
    asset_manager_or_producer = None
    dealer_or_swap = None
    for obs in visible:
        if obs.publication_time != latest.publication_time:
            continue
        net = compute_net(obs)
        cat = obs.participant_category.value
        if cat in {"LEVERAGED_FUNDS", "MANAGED_MONEY"}:
            leveraged_or_managed = net
        elif cat in {"ASSET_MANAGER_INSTITUTIONAL", "PRODUCER_MERCHANT"}:
            asset_manager_or_producer = net
        elif cat in {"DEALER_INTERMEDIARY", "SWAP_DEALER"}:
            dealer_or_swap = net

    age_days: int | None = None
    try:
        from datetime import date

        age_days = (
            date.fromisoformat(decision_time[:10]) - date.fromisoformat(latest.position_date[:10])
        ).days
    except ValueError:
        age_days = None

    return InstitutionalPositioningState(
        contract_family_id=contract_family_id,
        report_family=report_family,
        position_scope=position_scope,
        latest_report_date=latest.position_date,
        publication_time=latest.publication_time,
        report_age_days=age_days,
        leveraged_or_managed_net=leveraged_or_managed,
        asset_manager_or_producer_net=asset_manager_or_producer,
        dealer_or_swap_net=dealer_or_swap,
        net_percentile_52w=features.net_percentile_52w,
        net_percentile_104w=features.net_percentile_104w,
        weekly_net_change=features.weekly_net_change,
        quality_flags=latest.quality_flags,
        provenance_ref=latest.provenance_ref,
        predictive=False,
    )


def derived_to_dict(features: DerivedPositioningFeatures) -> dict[str, Any]:
    return {
        "net_position": features.net_position,
        "net_pct_open_interest": features.net_pct_open_interest,
        "weekly_net_change": features.weekly_net_change,
        "net_percentile_52w": features.net_percentile_52w,
        "net_percentile_104w": features.net_percentile_104w,
        "net_zscore": features.net_zscore,
        "long_short_ratio": features.long_short_ratio,
        "predictive": features.predictive,
        "disclaimer": features.disclaimer,
    }


__all__ = [
    "DerivedPositioningFeatures",
    "build_positioning_state",
    "compute_net",
    "compute_net_pct_oi",
    "compute_percentile",
    "compute_zscore",
    "derive_features",
    "derived_to_dict",
]
