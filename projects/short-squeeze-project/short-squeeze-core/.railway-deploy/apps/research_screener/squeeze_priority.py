"""Squeeze-oriented ranking for discovery trim and IBKR refresh scheduling."""

from __future__ import annotations

import os
from typing import Any, TYPE_CHECKING

from .finviz_live import (
    FinvizRow,
    finviz_row_completeness,
    finviz_row_is_usable,
)

FRESH_WITHIN_S = int(os.environ.get("FRESHNESS_CURRENT_SECONDS", "90"))

if TYPE_CHECKING:
    from .session_state import CandidateState

CLASSIFICATION_RANK: dict[str, int] = {
    "PRIME": 0,
    "SUBPRIME": 1,
    "WATCH": 2,
    "CONFLICTED": 3,
    "NOT_QUALIFIED": 4,
    "UNEVALUABLE": 5,
    "REFERENCE_DEFINITION_INCOMPLETE": 6,
}


def classification_rank(row: dict[str, Any] | None) -> int:
    if not row:
        return 99
    cls = (
        row.get("adam_classification")
        or row.get("classification")
        or "UNEVALUABLE"
    )
    return CLASSIFICATION_RANK.get(str(cls), 99)


def _finviz_scalar_score(row: FinvizRow) -> float:
    """Higher is more squeeze-like. Mirrors ``finviz_rank_key`` ordering."""
    if not finviz_row_is_usable(row):
        return 0.0
    completeness = float(finviz_row_completeness(row))
    short_float = float(row.short_float_pct or 0.0)
    rel_vol = float(row.rel_volume or 0.0)
    change = abs(float(row.change_pct or 0.0))
    score = completeness * 1_000.0 + short_float * 10.0 + rel_vol * 5.0 + change
    if row.float_shares is not None:
        score += max(0.0, 50.0 - (float(row.float_shares) / 1_000_000.0))
    if row.short_ratio is not None:
        score += float(row.short_ratio) * 2.0
    return score


def score_discovery_symbol(
    symbol: str,
    finviz_row: FinvizRow | None,
    ibkr_rank: int | None,
) -> float:
    """Rank union members before the screen cap is applied."""
    _ = symbol
    score = 0.0
    if finviz_row is not None:
        score += _finviz_scalar_score(finviz_row)
    if ibkr_rank is not None:
        score += max(0.0, 250.0 - float(ibkr_rank) * 3.0)
    return score


def score_refresh_priority(
    state: CandidateState,
    projected_row: dict[str, Any] | None,
    finviz_row: FinvizRow | None,
    *,
    age_seconds: float | None = None,
) -> float:
    """Higher priority symbols refresh first under IBKR pacing limits."""
    score = 0.0
    if projected_row:
        pressure = float(projected_row.get("pressure") or state.last_pressure or 0.0)
        ignition = float(projected_row.get("ignition") or state.last_ignition or 0.0)
        score += pressure + ignition
        cls_rank = classification_rank(projected_row)
        score += max(0.0, (10 - cls_rank) * 25.0)
    elif state.last_pressure or state.last_ignition:
        score += float(state.last_pressure or 0.0) + float(state.last_ignition or 0.0)

    if state.stale:
        score += 80.0
    if age_seconds is not None and age_seconds > FRESH_WITHIN_S:
        score += min(120.0, age_seconds / 30.0)

    if state.evaluation is None:
        score += state.discovery_score * 0.25
    elif finviz_row is not None:
        score += _finviz_scalar_score(finviz_row) * 0.05

    return score


def rank_symbols_for_refresh(
    states: dict[str, CandidateState],
    *,
    row_by_symbol: dict[str, dict[str, Any]] | None = None,
    finviz_by_symbol: dict[str, FinvizRow] | None = None,
    age_by_symbol: dict[str, float | None] | None = None,
) -> list[str]:
    """Return symbols ordered by descending refresh priority."""
    rows = row_by_symbol or {}
    finviz = finviz_by_symbol or {}
    ages = age_by_symbol or {}

    scored: list[tuple[float, str]] = []
    for symbol, state in states.items():
        priority = score_refresh_priority(
            state,
            rows.get(symbol),
            finviz.get(symbol),
            age_seconds=ages.get(symbol),
        )
        scored.append((priority, symbol))

    scored.sort(key=lambda item: (-item[0], item[1]))
    return [symbol for _score, symbol in scored]


def sort_rows_for_display(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Server-side ordering aligned with scanner default sort."""
    def sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
        cls = classification_rank(row)
        combo = float(row.get("pressure") or 0.0) + float(row.get("ignition") or 0.0)
        disc = float(row.get("discovery_score") or 0.0)
        return (cls, -combo, -disc, str(row.get("symbol") or ""))

    return sorted(rows, key=sort_key)


__all__ = [
    "CLASSIFICATION_RANK",
    "classification_rank",
    "rank_symbols_for_refresh",
    "score_discovery_symbol",
    "score_refresh_priority",
    "sort_rows_for_display",
]
