"""Shared fixtures for BUILD 22 paper execution tests."""

from __future__ import annotations

from market_platform_foundation.intelligence.contracts import (
    INTELLIGENCE_SCHEMA_VERSION,
    ContractKind,
    ContractReference,
    IntelligenceScope,
    OpportunitySide,
    OpportunityV1,
    QualityState,
    QualitySummary,
)
from market_platform_foundation.intelligence.execution import (
    ExecutionMode,
    ExecutionPolicyV1,
    MarketQuoteV1,
    PaperPositionSnapshot,
    SizingPolicyKind,
    build_execution_policy,
    build_portfolio_snapshot,
)
from tests.intelligence.outcome_fixtures import T

SCOPE = IntelligenceScope(instrument_ids=("inst-biya",))


def sample_opportunity(
    *,
    opportunity_id: str = "opp-build22-1",
    side: OpportunitySide = OpportunitySide.LONG,
    created_at_ns: int = T + 1_000_000_000,
    valid_until_ns: int = T + 600_000_000_000,
) -> OpportunityV1:
    return OpportunityV1(
        opportunity_id=opportunity_id,
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        scope=SCOPE,
        created_at_ns=created_at_ns,
        quality=QualitySummary(state=QualityState.GOOD),
        side=side,
        valid_until_ns=valid_until_ns,
        source_forecast_refs=(ContractReference(kind=ContractKind.FORECAST.value, id="fc-1"),),
        lineage_refs=(ContractReference(kind="champion_assignment", id="champ-1"),),
        metadata={"champion_assignment_id": "champ-1"},
    )


def default_execution_policy(**overrides) -> ExecutionPolicyV1:
    kwargs = {
        "trade_fraction_nav": 0.01,
        "max_trade_notional_minor": 50_000_00,
        "minimum_trade_notional_minor": 100,
        "minimum_quantity": 1,
    }
    kwargs.update(overrides)
    return build_execution_policy(**kwargs)


def flat_portfolio(
    *,
    equity_minor: int = 100_000_00,
    cash_minor: int | None = None,
    captured_at_ns: int = T + 1_000_000_000,
    start_of_day_equity_minor: int | None = None,
) -> object:
    cash = cash_minor if cash_minor is not None else equity_minor
    return build_portfolio_snapshot(
        captured_at_ns=captured_at_ns,
        cash_minor=cash,
        equity_minor=equity_minor,
        start_of_day_equity_minor=start_of_day_equity_minor,
    )


def sample_quote(
    *,
    instrument_id: str = "inst-biya",
    bid_minor: int = 9900,
    ask_minor: int = 10100,
    available_time_ns: int = T + 1_000_000_000,
) -> MarketQuoteV1:
    return MarketQuoteV1(
        instrument_id=instrument_id,
        bid_minor=bid_minor,
        ask_minor=ask_minor,
        available_time_ns=available_time_ns,
    )


def long_short_portfolio(*, captured_at_ns: int = T + 1_000_000_000):
    long_pos = PaperPositionSnapshot(
        instrument_id="inst-a",
        symbol="AAA",
        quantity=500,
        market_value_minor=50_000_00,
    )
    short_pos = PaperPositionSnapshot(
        instrument_id="inst-b",
        symbol="BBB",
        quantity=-500,
        market_value_minor=50_000_00,
    )
    return build_portfolio_snapshot(
        captured_at_ns=captured_at_ns,
        cash_minor=0,
        equity_minor=100_000_00,
        positions=(long_pos, short_pos),
    )


__all__ = [
    "default_execution_policy",
    "flat_portfolio",
    "long_short_portfolio",
    "sample_opportunity",
    "sample_quote",
]
