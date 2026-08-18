"""F2 continuous futures series builders with explicit methodology."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Sequence

from ..contracts.futures import ContinuousSeriesMethod


@dataclass(frozen=True, slots=True)
class ContinuousSeriesPoint:
    observation_time: str
    price: Decimal
    contract_id: str
    roll_adjustment: Decimal
    methodology: ContinuousSeriesMethod


def additive_back_adjusted_series(
    prices: Sequence[tuple[str, Decimal, str]],
    *,
    roll_gaps: Sequence[Decimal] | None = None,
) -> list[ContinuousSeriesPoint]:
    """Build additive back-adjusted continuous series from contract price tuples."""
    if not prices:
        return []
    cumulative_adjustment = Decimal("0")
    points: list[ContinuousSeriesPoint] = []
    for index, (obs_time, price, contract_id) in enumerate(prices):
        if roll_gaps and index > 0 and index - 1 < len(roll_gaps):
            cumulative_adjustment += roll_gaps[index - 1]
        adjusted = price + cumulative_adjustment
        points.append(
            ContinuousSeriesPoint(
                observation_time=obs_time,
                price=adjusted,
                contract_id=contract_id,
                roll_adjustment=cumulative_adjustment,
                methodology="additive_back_adjusted",
            )
        )
    return points


def unadjusted_continuous_series(
    prices: Sequence[tuple[str, Decimal, str]],
) -> list[ContinuousSeriesPoint]:
    return [
        ContinuousSeriesPoint(
            observation_time=obs_time,
            price=price,
            contract_id=contract_id,
            roll_adjustment=Decimal("0"),
            methodology="unadjusted_continuous",
        )
        for obs_time, price, contract_id in prices
    ]


def continuous_series_to_dicts(points: Sequence[ContinuousSeriesPoint]) -> list[dict[str, Any]]:
    return [
        {
            "observation_time": point.observation_time,
            "price": str(point.price),
            "contract_id": point.contract_id,
            "roll_adjustment": str(point.roll_adjustment),
            "methodology": point.methodology,
        }
        for point in points
    ]


__all__ = [
    "ContinuousSeriesPoint",
    "additive_back_adjusted_series",
    "continuous_series_to_dicts",
    "unadjusted_continuous_series",
]
