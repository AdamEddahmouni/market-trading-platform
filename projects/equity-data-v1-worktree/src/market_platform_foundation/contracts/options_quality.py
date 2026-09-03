"""Options quality flag taxonomy — missing data must never silently become zero."""

from __future__ import annotations

from enum import StrEnum


class OptionQualityFlag(StrEnum):
    """Quality flags for option contracts, chains, and derived analytics."""

    # Quote / chain freshness
    OPTION_CHAIN_STALE = "OPTION_CHAIN_STALE"
    OPTION_QUOTE_STALE = "OPTION_QUOTE_STALE"

    # Market structure
    CROSSED_OPTION_MARKET = "CROSSED_OPTION_MARKET"
    NO_TWO_SIDED_MARKET = "NO_TWO_SIDED_MARKET"
    ZERO_BID = "ZERO_BID"
    WIDE_OPTION_SPREAD = "WIDE_OPTION_SPREAD"

    # IV / Greeks
    IV_INVALID = "IV_INVALID"
    IV_SOLVER_FAILED = "IV_SOLVER_FAILED"
    GREEKS_STALE = "GREEKS_STALE"
    GREEKS_INCONSISTENT = "GREEKS_INCONSISTENT"

    # Positioning data
    OI_STALE = "OI_STALE"

    # Corporate actions
    CORPORATE_ACTION_ADJUSTED = "CORPORATE_ACTION_ADJUSTED"
    ADJUSTED_DELIVERABLE_UNKNOWN = "ADJUSTED_DELIVERABLE_UNKNOWN"

    # Pricing assumptions
    DIVIDEND_UNCERTAIN = "DIVIDEND_UNCERTAIN"
    BORROW_UNCERTAIN = "BORROW_UNCERTAIN"

    # Flow classification uncertainty
    FLOW_DIRECTION_UNCERTAIN = "FLOW_DIRECTION_UNCERTAIN"
    OPEN_CLOSE_UNKNOWN = "OPEN_CLOSE_UNKNOWN"
    PARTICIPANT_SIDE_UNKNOWN = "PARTICIPANT_SIDE_UNKNOWN"
    COMPLEX_ORDER_UNRESOLVED = "COMPLEX_ORDER_UNRESOLVED"

    # Dealer modeling
    DEALER_POSITION_UNKNOWN = "DEALER_POSITION_UNKNOWN"

    # Surface
    SURFACE_SPARSE = "SURFACE_SPARSE"
    SURFACE_ARBITRAGE_VIOLATION = "SURFACE_ARBITRAGE_VIOLATION"

    # Event volatility (O7)
    EARNINGS_DATE_UNKNOWN = "EARNINGS_DATE_UNKNOWN"
    STRADDLE_QUOTES_MISSING = "STRADDLE_QUOTES_MISSING"
    POST_EVENT_IV_UNAVAILABLE = "POST_EVENT_IV_UNAVAILABLE"

    # Strategy optimizer (O8)
    STRATEGY_INPUTS_INCOMPLETE = "STRATEGY_INPUTS_INCOMPLETE"
    STRATEGY_LIQUIDITY_BLOCKED = "STRATEGY_LIQUIDITY_BLOCKED"
    STRATEGY_NO_EDGE = "STRATEGY_NO_EDGE"

    # Execution / simulation (O9)
    EXECUTION_INPUTS_INCOMPLETE = "EXECUTION_INPUTS_INCOMPLETE"
    EXECUTION_LIQUIDITY_BLOCKED = "EXECUTION_LIQUIDITY_BLOCKED"
    EXECUTION_SCENARIO_UNAVAILABLE = "EXECUTION_SCENARIO_UNAVAILABLE"
    ASSIGNMENT_DATA_UNAVAILABLE = "ASSIGNMENT_DATA_UNAVAILABLE"


def quality_blocks_surface_fit(flags: tuple[str, ...]) -> bool:
    """Return True when surface fitting or Q inference must not proceed."""
    blocking = {
        OptionQualityFlag.SURFACE_SPARSE.value,
        OptionQualityFlag.SURFACE_ARBITRAGE_VIOLATION.value,
        OptionQualityFlag.OPTION_CHAIN_STALE.value,
        OptionQualityFlag.ADJUSTED_DELIVERABLE_UNKNOWN.value,
    }
    return any(flag in blocking for flag in flags)
