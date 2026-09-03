"""Frozen initial paper portfolio state (BUILD 27)."""

from __future__ import annotations

from dataclasses import replace

from .identity import derive_initial_portfolio_state_id
from .types import (
    DEFAULT_INITIAL_CASH_MINOR,
    PAPER_EXECUTION_QUALIFICATION_SCHEMA_VERSION,
    InitialPaperPortfolioStateV1,
)


def build_initial_paper_portfolio_state(
    *,
    initial_cash_minor: int = DEFAULT_INITIAL_CASH_MINOR,
    initial_equity_minor: int | None = None,
    currency: str = "USD",
    price_scale: int = 100,
    allow_short: bool = False,
    margin_policy: str = "CASH_ONLY",
    initial_positions: tuple[dict[str, object], ...] = (),
    initial_open_orders: tuple[dict[str, object], ...] = (),
) -> InitialPaperPortfolioStateV1:
    equity = initial_equity_minor if initial_equity_minor is not None else initial_cash_minor
    state = InitialPaperPortfolioStateV1(
        state_id="pending",
        schema_version=PAPER_EXECUTION_QUALIFICATION_SCHEMA_VERSION,
        initial_cash_minor=initial_cash_minor,
        initial_equity_minor=equity,
        currency=currency,
        price_scale=price_scale,
        allow_short=allow_short,
        margin_policy=margin_policy,
        initial_positions=tuple(dict(p) for p in initial_positions),
        initial_open_orders=tuple(dict(o) for o in initial_open_orders),
        metadata={"build": "BUILD_27_PAPER_EXECUTION_QUALIFICATION"},
    )
    return replace(state, state_id=derive_initial_portfolio_state_id(state))
