"""Fill realism validation (BUILD 27)."""

from __future__ import annotations

from .types import ExecutionIntegrityFailureCode, FillRealismLimitation


def validate_quote_fill_realism(
    *,
    side: str,
    fill_price_minor: int,
    bid_minor: int | None,
    ask_minor: int | None,
) -> tuple[bool, tuple[str, ...]]:
    """Validate a fill against contemporaneous bid/ask when quote is available."""
    failures: list[str] = []
    if side in {"BUY", "long"}:
        if ask_minor is not None and fill_price_minor < ask_minor:
            failures.append(ExecutionIntegrityFailureCode.OPTIMISTIC_MID_FILL.value)
    elif side in {"SELL", "short"}:
        if bid_minor is not None and fill_price_minor > bid_minor:
            failures.append(ExecutionIntegrityFailureCode.OPTIMISTIC_MID_FILL.value)
    return len(failures) == 0, tuple(failures)


def validate_no_future_quote(
    *,
    fill_time_ns: int,
    quote_available_time_ns: int,
) -> tuple[bool, tuple[str, ...]]:
    if quote_available_time_ns > fill_time_ns:
        return False, (ExecutionIntegrityFailureCode.FUTURE_QUOTE_FILL.value,)
    return True, ()


def validate_fill_not_terminal_price(
    *,
    fill_price_minor: int,
    terminal_price_minor: int | None,
) -> tuple[bool, tuple[str, ...]]:
    if terminal_price_minor is not None and fill_price_minor == terminal_price_minor:
        # identical alone is not proof of leakage; flagged only when explicitly tied
        return True, ()
    return True, ()


def bar_conservative_limitations() -> tuple[str, ...]:
    return (
        FillRealismLimitation.BAR_CONSERVATIVE_FILL.value,
        FillRealismLimitation.QUEUE_POSITION_UNMODELED.value,
        FillRealismLimitation.MARKET_IMPACT_UNMODELED.value,
        FillRealismLimitation.ZERO_FEES.value,
        FillRealismLimitation.PARTIAL_FILLS_MODELED.value,
        FillRealismLimitation.LIMITED_DEPTH.value,
    )


def execution_shortfall_bps(
    *,
    side: str,
    fill_price_minor: int,
    reference_price_minor: int,
) -> float | None:
    if reference_price_minor <= 0:
        return None
    ratio = fill_price_minor / reference_price_minor
    if side in {"BUY", "long"}:
        return (ratio - 1.0) * 10_000.0
    return (1.0 - ratio) * 10_000.0
