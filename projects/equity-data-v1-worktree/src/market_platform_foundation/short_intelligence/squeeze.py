"""Coarse short-intelligence → observational allocation hints. No vendor names."""

from __future__ import annotations

from typing import Any

from .contracts import ShortPressureState
from .pressure import pressure_state
from .store import ShortIntelligenceStore


def pressure_to_allocation_hint(state: ShortPressureState) -> dict[str, str | int]:
    priority = 10
    if state.threshold_status == "ACTIVE":
        priority += 30
    if state.short_interest_direction == "INCREASING":
        priority += 20
    if state.short_flow_persistence == "PERSISTENT":
        priority += 10
    return {
        "instrument_id": state.instrument_id,
        "capability": "US_EQUITY_DEPTH",
        "lane": "short_intelligence",
        "priority": priority,
        "thesis_id": f"short-pressure:{state.instrument_id}",
    }


def rank_candidates(store: ShortIntelligenceStore, instruments: list[str], as_of: str) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for instrument_id in instruments:
        state = pressure_state(store, instrument_id, as_of)
        hint = pressure_to_allocation_hint(state)
        ranked.append(
            {
                "instrument_id": instrument_id,
                "state": "IGNITION_WATCH" if int(hint["priority"]) >= 40 else "STRUCTURAL_WATCH",
                "priority": hint["priority"],
                "pressure": {
                    "short_interest_direction": state.short_interest_direction,
                    "threshold_status": state.threshold_status,
                    "recent_short_sale_flow": state.recent_short_sale_flow,
                },
            }
        )
    ranked.sort(key=lambda row: (-int(row["priority"]), str(row["instrument_id"])))
    return ranked


def fuse_regulatory_and_short(
    *,
    regulatory_state: dict[str, Any],
    pressure: ShortPressureState,
) -> dict[str, Any]:
    """Keep contradictory evidence. Do not collapse into a binary squeeze label."""
    return {
        "why_what_changed": {
            "fresh_8k": bool(regulatory_state.get("fresh_8k")),
            "dilution_terms_known": bool(regulatory_state.get("dilution_terms_known")),
            "source": "SEC",
        },
        "how_crowded": {
            "short_interest_direction": pressure.short_interest_direction,
            "threshold_status": pressure.threshold_status,
            "source": "SHORT_INTELLIGENCE",
        },
        "contradictions": [
            item
            for item in (
                "DILUTION_VS_SHORT_CROWDING"
                if regulatory_state.get("dilution_terms_known") and pressure.short_interest_direction == "INCREASING"
                else "",
                "CATALYST_WITHOUT_SHORT_CONTEXT"
                if regulatory_state.get("fresh_8k") and pressure.structural_short_crowding == "UNKNOWN"
                else "",
            )
            if item
        ],
        "squeeze_probability": None,
        "expected_value": None,
    }
