"""Fail-closed promotion gates for quantitative factor research.

A factor observation is not an Opportunity Engine ranking input, not a
ForecastV1, not Paper EXECUTION, and not Live. Academic long-short returns
are RESEARCH_PORTFOLIO only.
"""

from __future__ import annotations

from typing import Any

from .errors import FactorContractError

FORBIDDEN_PROMOTION_KEYS = frozenset(
    {
        "order_id",
        "quantity",
        "size",
        "broker_order",
        "execution_authority",
        "authorized",
        "submit_order",
        "side_buy_sell",
        "universal_score",
        "opaque_score",
        "economic_score",
        "rank_score",
        "opportunity_id",
        "forecast_id",
        "live_eligible",
        "paper_execution",
    }
)

OPPORTUNITY_ENGINE_RANKING_ELIGIBLE = False
LIVE_ELIGIBLE = False


def reject_promotion_fields(metadata: dict[str, Any]) -> None:
    if not isinstance(metadata, dict):
        raise FactorContractError("FACTOR_METADATA_INVALID")
    for key in metadata:
        if key in FORBIDDEN_PROMOTION_KEYS:
            raise FactorContractError("FACTOR_PROMOTION_FIELD_FORBIDDEN")


def assert_not_opportunity_engine_input() -> None:
    if OPPORTUNITY_ENGINE_RANKING_ELIGIBLE:
        raise FactorContractError("FACTOR_OPPORTUNITY_ENGINE_RANKING_FORBIDDEN")


def assert_research_only() -> None:
    if LIVE_ELIGIBLE:
        raise FactorContractError("FACTOR_LIVE_ELIGIBILITY_FORBIDDEN")
    assert_not_opportunity_engine_input()


__all__ = [
    "FORBIDDEN_PROMOTION_KEYS",
    "LIVE_ELIGIBLE",
    "OPPORTUNITY_ENGINE_RANKING_ELIGIBLE",
    "assert_not_opportunity_engine_input",
    "assert_research_only",
    "reject_promotion_fields",
]
