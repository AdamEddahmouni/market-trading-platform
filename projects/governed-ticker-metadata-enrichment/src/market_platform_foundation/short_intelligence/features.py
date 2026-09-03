"""Deterministic research features. None of these are predictive until evaluated."""

from __future__ import annotations

import statistics
from typing import Any

from .contracts import FailsToDeliverObservation, ShortInterestObservation, ShortSaleVolumeObservation, ThresholdStatusObservation
from .identity import SymbolMap
from .store import ShortIntelligenceStore
from ..finra.short_sale_volume import aggregate_short_sale_rows


def short_interest_features(row: ShortInterestObservation | None) -> dict[str, Any]:
    if row is None:
        return {
            "status": "UNKNOWN",
            "current_short_position": None,
            "previous_short_position": None,
            "short_interest_change": None,
            "short_interest_change_pct": None,
            "days_to_cover": None,
            "short_interest_pct_float": None,
        }
    return {
        "status": "AVAILABLE",
        "current_short_position": row.current_short_position_quantity,
        "previous_short_position": row.previous_short_position_quantity,
        "short_interest_change": row.short_position_delta,
        "short_interest_change_pct": row.short_position_pct_change,
        "days_to_cover": row.days_to_cover_provider,
        "days_to_cover_methodology": "FINRA_PROVIDER_AVERAGE_DAILY_VOLUME",
        "short_interest_pct_float": None,
        "short_interest_pct_shares_outstanding": None,
        "float_denominator": "UNKNOWN_NOT_PIT_SAFE",
        "revision_flag": row.revision_flag,
        "stock_split_flag": row.stock_split_flag,
        "layer": "derived",
    }


def short_interest_pct_float(
    *,
    current_short_position: int | None,
    pit_shares_outstanding: int | None,
    denominator_known_from: str,
    observation_available_time: str,
) -> float | None:
    """Refuse present-day float for historical observations."""
    if current_short_position is None or pit_shares_outstanding in (None, 0):
        return None
    if not denominator_known_from or denominator_known_from > observation_available_time:
        return None
    return float(current_short_position) / float(pit_shares_outstanding)


def short_sale_features(rows: tuple[ShortSaleVolumeObservation, ...]) -> dict[str, Any]:
    if not rows:
        return {"status": "UNKNOWN", "finra_reported_short_sale_ratio": None}
    by_date: dict[str, list[ShortSaleVolumeObservation]] = {}
    for row in rows:
        by_date.setdefault(row.trade_report_date, []).append(row)
    dates = sorted(by_date)
    daily = [aggregate_short_sale_rows(by_date[day]) for day in dates]
    ratios = [
        item["finra_reported_short_sale_ratio"]
        for item in daily
        if item["finra_reported_short_sale_ratio"] is not None
    ]
    latest = daily[-1]
    change = None
    if len(daily) >= 2 and daily[-1]["short_sale_volume"] is not None and daily[-2]["short_sale_volume"] is not None:
        change = daily[-1]["short_sale_volume"] - daily[-2]["short_sale_volume"]
    ratio_5d = None
    zscore = None
    if ratios:
        window = ratios[-5:]
        ratio_5d = sum(window) / len(window)
        if len(ratios) >= 3:
            mean = statistics.fmean(ratios)
            stdev = statistics.pstdev(ratios)
            if stdev:
                zscore = (ratios[-1] - mean) / stdev
    persistence = 0
    for item in reversed(daily):
        ratio = item["finra_reported_short_sale_ratio"]
        if ratio is None:
            break
        if len(ratios) >= 2 and ratio >= statistics.fmean(ratios):
            persistence += 1
        else:
            break
    acceleration = None
    if len(daily) >= 3 and all(item["short_sale_volume"] is not None for item in daily[-3:]):
        d1 = daily[-1]["short_sale_volume"] - daily[-2]["short_sale_volume"]
        d0 = daily[-2]["short_sale_volume"] - daily[-3]["short_sale_volume"]
        acceleration = d1 - d0
    latest["status"] = "AVAILABLE"
    latest["day_over_day_short_volume_change"] = change
    latest["short_sale_ratio_5d"] = ratio_5d
    latest["short_sale_ratio_zscore"] = zscore
    latest["short_flow_persistence"] = persistence
    latest["short_flow_acceleration"] = acceleration
    latest["layer"] = "derived"
    return latest


def threshold_duration(rows: tuple[ThresholdStatusObservation, ...]) -> dict[str, Any]:
    if not rows:
        return {
            "status": "UNKNOWN",
            "currently_threshold": None,
            "consecutive_observed_threshold_days": 0,
            "days_since_entered": None,
            "days_since_exited": None,
        }
    consecutive = 0
    for row in reversed(rows):
        if row.currently_threshold:
            consecutive += 1
        else:
            break
    currently = rows[-1].currently_threshold
    entered = None
    exited = None
    if currently:
        entered = consecutive
    else:
        since = 0
        seen_true = False
        for row in reversed(rows):
            if row.currently_threshold:
                seen_true = True
                break
            since += 1
        exited = since if seen_true else None
    return {
        "status": "AVAILABLE",
        "currently_threshold": currently,
        "threshold_active": currently,
        "consecutive_observed_threshold_days": consecutive,
        "days_since_entered": entered,
        "days_since_exited": exited,
        "threshold_duration": consecutive if currently else 0,
        "layer": "derived",
        "note": "duration uses observed official list membership only; hidden FTD sequences are not inferred",
    }


def ftd_balance_features(rows: tuple[FailsToDeliverObservation, ...]) -> dict[str, Any]:
    if not rows:
        return {
            "status": "UNKNOWN",
            "ftd_balance_quantity": None,
            "ftd_balance_present": False,
            "ftd_balance_change": None,
            "ftd_balance_pct_change": None,
            "approx_ftd_notional_sec_price": None,
            "consecutive_settlement_days_with_ftd": 0,
            "layer": "derived",
        }
    latest = rows[-1]
    previous = rows[-2] if len(rows) >= 2 else None
    change = None
    pct_change = None
    if previous is not None:
        change = latest.ftd_balance_quantity - previous.ftd_balance_quantity
        if previous.ftd_balance_quantity:
            pct_change = change / previous.ftd_balance_quantity
    consecutive = 0
    for row in reversed(rows):
        if row.ftd_balance_quantity > 0:
            consecutive += 1
        else:
            break
    return {
        "status": "AVAILABLE",
        "ftd_balance_quantity": latest.ftd_balance_quantity,
        "ftd_balance_present": latest.ftd_balance_quantity > 0,
        "ftd_balance_change": change,
        "ftd_balance_pct_change": pct_change,
        "approx_ftd_notional_sec_price": latest.approx_ftd_notional_sec_price,
        "settlement_date": latest.settlement_date,
        "cusip": latest.cusip,
        "consecutive_settlement_days_with_ftd": consecutive,
        "layer": "derived",
        "note": "balance_change is not new failed trades; never sum balances across days as flow",
    }


def sum_of_daily_balance_observations(rows: tuple[FailsToDeliverObservation, ...]) -> int:
    """Explicitly misnamed research helper. Not total failed deliveries."""
    return sum(row.ftd_balance_quantity for row in rows)


def cross_source_features(
    store: ShortIntelligenceStore,
    instrument_id: str,
    as_of: str,
    *,
    provider_symbol: str | None = None,
    symbol_map: SymbolMap | None = None,
) -> dict[str, Any]:
    interest = short_interest_features(store.short_interest_as_of(instrument_id, as_of))
    flow = short_sale_features(store.short_sale_as_of(instrument_id, as_of))
    if provider_symbol and symbol_map is not None:
        from .threshold_coverage import threshold_state_as_of

        threshold = threshold_state_as_of(
            store,
            symbol_map,
            instrument_id=instrument_id,
            provider_symbol=provider_symbol,
            as_of=as_of,
        )
    else:
        threshold = threshold_duration(store.threshold_as_of(instrument_id, as_of))
    ftd = ftd_balance_features(store.ftd_as_of(instrument_id, as_of))
    rising = interest.get("short_interest_change")
    flow_rising = flow.get("day_over_day_short_volume_change")
    return {
        "short_interest": interest,
        "short_sale_flow": flow,
        "threshold": threshold,
        "fails_to_deliver": ftd,
        "short_interest_rising_and_threshold": bool(
            threshold.get("currently_threshold") and isinstance(rising, int) and rising > 0
        ),
        "short_flow_rising_and_threshold": bool(
            threshold.get("currently_threshold") and isinstance(flow_rising, int) and flow_rising > 0
        ),
        "predictive": False,
        "layer": "derived_unvalidated",
    }
