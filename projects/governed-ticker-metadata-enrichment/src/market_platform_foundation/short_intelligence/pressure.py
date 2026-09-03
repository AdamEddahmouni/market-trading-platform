"""ShortPressureState. Borrow/CTB/locate remain UNKNOWN unless a lending source exists."""

from __future__ import annotations

from .contracts import ShortPressureState
from .features import cross_source_features
from .store import ShortIntelligenceStore


def pressure_state(store: ShortIntelligenceStore, instrument_id: str, as_of: str) -> ShortPressureState:
    features = cross_source_features(store, instrument_id, as_of)
    interest = features["short_interest"]
    flow = features["short_sale_flow"]
    threshold = features["threshold"]
    ftd = features["fails_to_deliver"]
    crowding = "UNKNOWN"
    direction = "UNKNOWN"
    if interest.get("status") == "AVAILABLE":
        crowding = "OBSERVED"
        change = interest.get("short_interest_change")
        if isinstance(change, int):
            if change > 0:
                direction = "INCREASING"
            elif change < 0:
                direction = "DECREASING"
            else:
                direction = "UNCHANGED"
    flow_state = "UNKNOWN"
    if flow.get("status") == "AVAILABLE":
        flow_state = "OBSERVED"
    persistence = "UNKNOWN"
    if isinstance(flow.get("short_flow_persistence"), int):
        persistence = "PERSISTENT" if flow["short_flow_persistence"] >= 2 else "NOT_PERSISTENT"
    threshold_status = "UNKNOWN"
    if threshold.get("status") == "AVAILABLE":
        threshold_status = "ACTIVE" if threshold.get("currently_threshold") else "INACTIVE"
    elif threshold.get("status") == "SOURCE_UNAVAILABLE":
        threshold_status = "UNKNOWN"
    ftd_state = "UNKNOWN"
    ftd_balance: int | None = None
    if ftd.get("status") == "AVAILABLE":
        ftd_state = "KNOWN"
        ftd_balance = ftd.get("ftd_balance_quantity")
    flags: list[str] = []
    if interest.get("status") != "AVAILABLE":
        flags.append("SHORT_INTEREST_UNKNOWN")
    if flow.get("status") != "AVAILABLE":
        flags.append("SHORT_SALE_FLOW_UNKNOWN")
    if threshold.get("status") not in {"AVAILABLE", "NOT_APPLICABLE"}:
        flags.append("THRESHOLD_UNKNOWN")
    if ftd.get("status") != "AVAILABLE":
        flags.append("FTD_QUANTITY_UNKNOWN")
    flags.extend(["BORROW_UNKNOWN", "COST_TO_BORROW_UNKNOWN", "LOCATE_UNKNOWN"])
    return ShortPressureState(
        instrument_id=instrument_id,
        as_of=as_of,
        structural_short_crowding=crowding,
        short_interest_direction=direction,
        days_to_cover=interest.get("days_to_cover"),
        recent_short_sale_flow=flow_state,
        short_flow_persistence=persistence,
        threshold_status=threshold_status,
        threshold_duration=threshold.get("threshold_duration"),
        fails_to_deliver=ftd_state,
        ftd_balance_quantity=ftd_balance,
        borrow_state="UNKNOWN",
        cost_to_borrow="UNKNOWN",
        locate_state="UNKNOWN",
        quality_flags=tuple(flags),
        provenance=tuple(
            item
            for item in (
                "SHORT_INTEREST" if interest.get("status") == "AVAILABLE" else "",
                "SHORT_SALE_FLOW" if flow.get("status") == "AVAILABLE" else "",
                "THRESHOLD_STATUS" if threshold.get("status") == "AVAILABLE" else "",
                "FAILS_TO_DELIVER" if ftd.get("status") == "AVAILABLE" else "",
            )
            if item
        ),
    )
