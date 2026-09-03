"""SS P7 ShortPainDistribution research estimator — fail-closed without entry price proxy."""

from __future__ import annotations

from typing import Any

from ...contracts.squeeze_structural import ShortPainDistribution, short_pain_distribution_to_dict

MODEL_VERSION = "ss_pain_distribution_v1"
METHOD = "RESEARCH_PROXY_BAND_ESTIMATE"


def estimate_short_pain_distribution(
    *,
    symbol: str,
    spot_price: float | None,
    entry_price_proxy: dict[str, Any] | None,
    observation_time: str,
    available_time: str,
) -> ShortPainDistribution:
    """Estimate short pain distribution from explicit entry-price proxy bands only."""
    if spot_price is None or not entry_price_proxy:
        return ShortPainDistribution(
            symbol=symbol,
            status="UNAVAILABLE",
            underwater_pct=None,
            pain_percentiles=None,
            method=METHOD,
            observation_time=observation_time,
            available_time=available_time,
            quality_flags=("ENTRY_PRICE_PROXY_MISSING",),
        )

    bands = entry_price_proxy.get("entry_price_bands")
    if not isinstance(bands, list) or not bands:
        return ShortPainDistribution(
            symbol=symbol,
            status="UNAVAILABLE",
            underwater_pct=None,
            pain_percentiles=None,
            method=METHOD,
            observation_time=observation_time,
            available_time=available_time,
            quality_flags=("ENTRY_PRICE_BANDS_MISSING",),
        )

    weights: list[float] = []
    underwater_flags: list[bool] = []
    move_to_cover: list[float] = []
    for band in bands:
        if not isinstance(band, dict):
            continue
        weight = float(band.get("weight", 0.0))
        entry = band.get("entry_price")
        if entry is None or weight <= 0:
            continue
        entry_f = float(entry)
        weights.append(weight)
        underwater_flags.append(spot_price > entry_f)
        move_to_cover.append(max((spot_price - entry_f) / entry_f * 100.0, 0.0))

    if not weights:
        return ShortPainDistribution(
            symbol=symbol,
            status="UNAVAILABLE",
            underwater_pct=None,
            pain_percentiles=None,
            method=METHOD,
            observation_time=observation_time,
            available_time=available_time,
            quality_flags=("ENTRY_PRICE_BANDS_INVALID",),
        )

    total_weight = sum(weights)
    underwater_pct = round(
        sum(w for w, u in zip(weights, underwater_flags) if u) / total_weight,
        6,
    )
    sorted_moves = sorted(move_to_cover)
    p50_idx = len(sorted_moves) // 2
    p75_idx = min(int(len(sorted_moves) * 0.75), len(sorted_moves) - 1)
    p90_idx = min(int(len(sorted_moves) * 0.9), len(sorted_moves) - 1)
    pain_percentiles = (
        round(sorted_moves[p50_idx], 4),
        round(sorted_moves[p75_idx], 4),
        round(sorted_moves[p90_idx], 4),
    )

    proxy_tag = str(entry_price_proxy.get("proxy_status", "RESEARCH_PROXY"))
    status = "RESEARCH_PROXY" if proxy_tag == "RESEARCH_PROXY" else "UNAVAILABLE"
    quality_flags: tuple[str, ...] = ()
    if status == "RESEARCH_PROXY":
        quality_flags = ("RESEARCH_PROXY_ENTRY_PRICE",)

    return ShortPainDistribution(
        symbol=symbol,
        status=status,
        underwater_pct=underwater_pct,
        pain_percentiles=pain_percentiles,
        method=METHOD,
        observation_time=observation_time,
        available_time=available_time,
        quality_flags=quality_flags,
    )


def pain_distribution_result(dist: ShortPainDistribution) -> dict[str, Any]:
    payload = short_pain_distribution_to_dict(dist)
    payload["model_version"] = MODEL_VERSION
    return payload


__all__ = [
    "METHOD",
    "MODEL_VERSION",
    "estimate_short_pain_distribution",
    "pain_distribution_result",
]
