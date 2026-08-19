"""Futures quality flag taxonomy — missing data must never silently become neutral."""

from __future__ import annotations

from enum import StrEnum


class FuturesQualityFlag(StrEnum):
    """Quality flags for futures contracts, curves, and derived analytics."""

    # Contract specification
    CONTRACT_SPEC_UNKNOWN = "CONTRACT_SPEC_UNKNOWN"
    CONTRACT_STALE = "CONTRACT_STALE"
    LEAD_CONTRACT_UNCERTAIN = "LEAD_CONTRACT_UNCERTAIN"
    ROLL_WINDOW_UNCERTAIN = "ROLL_WINDOW_UNCERTAIN"

    # Curve / basis
    CURVE_SPARSE = "CURVE_SPARSE"
    BASIS_STALE = "BASIS_STALE"
    SPOT_REFERENCE_STALE = "SPOT_REFERENCE_STALE"
    BASIS_DEFINITION_MIXED = "BASIS_DEFINITION_MIXED"

    # Settlement / OI
    SETTLEMENT_STALE = "SETTLEMENT_STALE"
    OPEN_INTEREST_STALE = "OPEN_INTEREST_STALE"

    # Positioning
    COT_STALE = "COT_STALE"
    COT_PUBLICATION_PENDING = "COT_PUBLICATION_PENDING"
    POSITIONING_UNKNOWN = "POSITIONING_UNKNOWN"

    # Fundamentals / macro
    MACRO_CONSENSUS_MISSING = "MACRO_CONSENSUS_MISSING"
    INVENTORY_STALE = "INVENTORY_STALE"

    # Margin / leverage
    MARGIN_STALE = "MARGIN_STALE"
    MARGIN_TYPE_UNKNOWN = "MARGIN_TYPE_UNKNOWN"

    # Delivery / Treasury
    DELIVERY_DATA_MISSING = "DELIVERY_DATA_MISSING"
    CTD_UNCERTAIN = "CTD_UNCERTAIN"
    FIRST_NOTICE_APPROACHING = "FIRST_NOTICE_APPROACHING"
    DELIVERY_RISK = "DELIVERY_RISK"

    # Market structure
    PRICE_LIMIT_STATE_UNKNOWN = "PRICE_LIMIT_STATE_UNKNOWN"
    DOM_STALE = "DOM_STALE"
    AGGRESSOR_UNCERTAIN = "AGGRESSOR_UNCERTAIN"

    # Continuous series
    CONTINUOUS_SERIES_ADJUSTED = "CONTINUOUS_SERIES_ADJUSTED"

    # Trend / baseline features (F5)
    TREND_HISTORY_INSUFFICIENT = "TREND_HISTORY_INSUFFICIENT"


def quality_blocks_curve_analytics(flags: tuple[str, ...]) -> bool:
    """Return True when curve/carry analytics must not proceed."""
    blocking = {
        FuturesQualityFlag.CURVE_SPARSE.value,
        FuturesQualityFlag.CONTRACT_SPEC_UNKNOWN.value,
        FuturesQualityFlag.BASIS_DEFINITION_MIXED.value,
        FuturesQualityFlag.LEAD_CONTRACT_UNCERTAIN.value,
    }
    return any(flag in blocking for flag in flags)


def quality_blocks_positioning_interpretation(flags: tuple[str, ...]) -> bool:
    """Return True when positioning/crowding outputs must not proceed."""
    blocking = {
        FuturesQualityFlag.COT_STALE.value,
        FuturesQualityFlag.POSITIONING_UNKNOWN.value,
        FuturesQualityFlag.COT_PUBLICATION_PENDING.value,
    }
    return any(flag in blocking for flag in flags)


def quality_blocks_baseline_interpretation(flags: tuple[str, ...]) -> bool:
    """Return True when trend/carry baseline outputs must not proceed."""
    blocking = {
        FuturesQualityFlag.TREND_HISTORY_INSUFFICIENT.value,
        FuturesQualityFlag.SETTLEMENT_STALE.value,
        FuturesQualityFlag.CURVE_SPARSE.value,
    }
    return any(flag in blocking for flag in flags)


def quality_blocks_leverage_stress(flags: tuple[str, ...]) -> bool:
    """Return True when leverage-stress modeling must not proceed."""
    blocking = {
        FuturesQualityFlag.MARGIN_STALE.value,
        FuturesQualityFlag.MARGIN_TYPE_UNKNOWN.value,
        FuturesQualityFlag.CONTRACT_SPEC_UNKNOWN.value,
    }
    return any(flag in blocking for flag in flags)
