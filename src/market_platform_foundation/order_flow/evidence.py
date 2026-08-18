"""Build versioned OrderFlowEvidence for cross-lane publication."""

from __future__ import annotations

from typing import Any

from .contracts import (
    BookPressureEvidence,
    CVDState,
    L1QuoteState,
    MicrostructureCapabilityTier,
    OrderFlowEvidence,
    cvd_state_to_dict,
    l1_state_to_dict,
)
from .cvd import compute_cvd_state
from .l1 import compute_book_pressure, compute_l1_state

PRODUCER_VERSION = "order_flow.1.0.0"
OFI_METHOD_BBO_DELTA = "ofi_bbo_delta_v1"


def build_order_flow_evidence(
    *,
    instrument: str,
    venue: str,
    event_time: str,
    available_time: str,
    bars: list[dict[str, object]] | None = None,
    snapshot: dict[str, Any] | None = None,
    ofi_value: float | None = None,
    horizon: str = "bar",
    data_confidence: float | None = None,
    quality_flags: tuple[str, ...] = (),
) -> OrderFlowEvidence | None:
    """Assemble microstructure evidence from trade bars and/or book snapshot."""
    cvd: CVDState | None = None
    if bars:
        cvd = compute_cvd_state(bars)

    l1: L1QuoteState | None = None
    book_pressure: BookPressureEvidence | None = None
    capability = MicrostructureCapabilityTier.L1

    if snapshot:
        bids = snapshot.get("bids", [])
        asks = snapshot.get("asks", [])
        if isinstance(bids, list) and isinstance(asks, list) and bids and asks:
            book_pressure = compute_book_pressure(bids, asks)
            best_bid = max(float(row["price"]) for row in bids)
            best_ask = min(float(row["price"]) for row in asks)
            top_bid = max(bids, key=lambda row: float(row["price"]))
            top_ask = min(asks, key=lambda row: float(row["price"]))
            l1 = compute_l1_state(
                best_bid=best_bid,
                best_ask=best_ask,
                bid_size=float(top_bid["size"]),
                ask_size=float(top_ask["size"]),
            )
            if len(bids) > 1 or len(asks) > 1:
                capability = MicrostructureCapabilityTier.L2_MBP

    if cvd is None and l1 is None:
        return None

    resolved_confidence = data_confidence
    if resolved_confidence is None and cvd is not None:
        resolved_confidence = cvd.cvd_confidence
    elif resolved_confidence is None and l1 is not None:
        resolved_confidence = 0.7

    supporting: list[str] = []
    counter: list[str] = []
    if cvd is not None:
        if cvd.session_cvd > 0:
            supporting.append(f"session CVD positive ({cvd.session_cvd:.0f})")
        elif cvd.session_cvd < 0:
            supporting.append(f"session CVD negative ({cvd.session_cvd:.0f})")
        if cvd.unknown_fraction > 0.25:
            counter.append(f"unknown aggressor fraction {cvd.unknown_fraction:.0%}")
    if book_pressure is not None:
        if book_pressure.queue_imbalance_l1 > 0.1:
            supporting.append(f"L1 queue imbalance bid-heavy ({book_pressure.queue_imbalance_l1:.2f})")
        elif book_pressure.queue_imbalance_l1 < -0.1:
            supporting.append(f"L1 queue imbalance ask-heavy ({book_pressure.queue_imbalance_l1:.2f})")

    return OrderFlowEvidence(
        instrument=instrument,
        venue=venue,
        horizon=horizon,
        event_time=event_time,
        available_time=available_time,
        producer_version=PRODUCER_VERSION,
        data_confidence=resolved_confidence or 0.0,
        model_confidence=0.0,
        capability_tier=capability,
        cvd=cvd,
        l1=l1,
        book_pressure=book_pressure,
        ofi_value=ofi_value,
        ofi_method=OFI_METHOD_BBO_DELTA if ofi_value is not None else None,
        ofi_version="1" if ofi_value is not None else None,
        quality_flags=quality_flags,
        supporting_evidence=tuple(supporting),
        counter_evidence=tuple(counter),
    )


def order_flow_evidence_to_dict(evidence: OrderFlowEvidence) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "instrument": evidence.instrument,
        "venue": evidence.venue,
        "horizon": evidence.horizon,
        "event_time": evidence.event_time,
        "available_time": evidence.available_time,
        "producer_version": evidence.producer_version,
        "data_confidence": evidence.data_confidence,
        "model_confidence": evidence.model_confidence,
        "capability_tier": evidence.capability_tier.value,
        "quality_flags": list(evidence.quality_flags),
        "supporting_evidence": list(evidence.supporting_evidence),
        "counter_evidence": list(evidence.counter_evidence),
    }
    if evidence.cvd is not None:
        payload["cvd"] = cvd_state_to_dict(evidence.cvd)
    if evidence.l1 is not None:
        payload["l1"] = l1_state_to_dict(evidence.l1)
    if evidence.book_pressure is not None:
        bp = evidence.book_pressure
        payload["book_pressure"] = {
            "depth_imbalance_ratio": bp.depth_imbalance_ratio,
            "queue_imbalance_l1": bp.queue_imbalance_l1,
            "bid_depth": bp.bid_depth,
            "ask_depth": bp.ask_depth,
            "level_count": bp.level_count,
            "capability_tier": bp.capability_tier.value,
        }
    if evidence.ofi_value is not None:
        payload["ofi_value"] = evidence.ofi_value
        payload["ofi_method"] = evidence.ofi_method
        payload["ofi_version"] = evidence.ofi_version
    return payload


__all__ = [
    "OFI_METHOD_BBO_DELTA",
    "PRODUCER_VERSION",
    "build_order_flow_evidence",
    "order_flow_evidence_to_dict",
]
