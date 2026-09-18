"""Historical research labels (distinct from POST_HORIZON_HISTORICAL_LABEL_EVIDENCE)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .types import HISTORICAL_RESEARCH_LABEL_AUTHORITY, HISTORICAL_RESEARCH_LABEL_KIND


def historical_research_forward_return_label(
    bars: Sequence[Mapping[str, Any]],
    *,
    decision_time_ns: int,
    forward_horizon_bars: int,
) -> dict[str, Any] | None:
    """Forward return label for historical research only; not Path A TRADE prospective."""

    ordered = sorted(
        [bar for bar in bars if int(bar.get("available_time", 0)) >= decision_time_ns],
        key=lambda row: (int(row["available_time"]), str(row.get("normalized_event_id", ""))),
    )
    at_or_before = [bar for bar in bars if int(bar.get("available_time", 0)) <= decision_time_ns]
    if not at_or_before or len(ordered) <= forward_horizon_bars:
        return None
    at_or_before.sort(key=lambda row: (int(row["available_time"]), str(row.get("normalized_event_id", ""))))
    decision_bar = at_or_before[-1]
    future_bar = ordered[forward_horizon_bars]
    try:
        decision_close = float(decision_bar.get("bar_payload", {}).get("close"))
        future_close = float(future_bar.get("bar_payload", {}).get("close"))
    except (TypeError, ValueError, AttributeError):
        return None
    if decision_close <= 0:
        return None
    forward_return = future_close / decision_close - 1.0
    return {
        "label_kind": HISTORICAL_RESEARCH_LABEL_KIND,
        "corpus_evidence_authority": HISTORICAL_RESEARCH_LABEL_AUTHORITY,
        "not_post_horizon_label_evidence": True,
        "decision_time_ns": decision_time_ns,
        "forward_horizon_bars": forward_horizon_bars,
        "forward_return": forward_return,
        "direction": 1 if forward_return > 0 else (-1 if forward_return < 0 else 0),
    }


__all__ = ["historical_research_forward_return_label"]
