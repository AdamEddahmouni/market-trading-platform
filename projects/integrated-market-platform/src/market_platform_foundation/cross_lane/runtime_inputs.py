"""G7 — cross-lane runtime input bridge (canonical observational → fusion inputs).

Builds fusion/opportunity-compatible snapshot dicts from canonical
ObservationalStateStore lane outputs. Does not modify fusion formulas or
introduce duplicate market-data authority.
"""

from __future__ import annotations

from typing import Any

from ..market_data.observational_lanes import ObservationalLaneRuntime
from ..market_data.observational_state import ObservationalStateStore


def build_order_flow_lane_snapshot(
    store: ObservationalStateStore,
    instrument_id: str,
) -> dict[str, Any]:
    """Produce an order-flow payload dict for cross-lane fusion from canonical state."""
    lanes = ObservationalLaneRuntime(store)
    cvd = lanes.build_cvd_payload(instrument_id)
    ofi = lanes.build_ofi_payload(instrument_id)
    book_features = lanes.build_book_features_payload(instrument_id)
    l1 = lanes.build_l1_payload(instrument_id)
    return {
        "available": any(
            row.get("available")
            for row in (cvd, ofi, book_features, l1)
            if isinstance(row, dict)
        ),
        "book_features": book_features,
        "cvd": cvd,
        "instrument_id": instrument_id.upper(),
        "l1": l1,
        "ofi": ofi,
        "producer": "observational_lane_runtime/g7",
    }


__all__ = ["build_order_flow_lane_snapshot"]
