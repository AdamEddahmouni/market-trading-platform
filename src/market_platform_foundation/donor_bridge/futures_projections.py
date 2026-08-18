"""Project FuturesX donor bridge into IMP explore DTOs."""

from __future__ import annotations

from typing import Any

from .futures_client import DEFAULT_BASE_URL, fetch_depth_latest, fetch_health, is_available

ADMITTED_FUTURES_INSTRUMENT_ID = "ES"
_UNAVAILABLE_REASON = (
    "FuturesX donor bridge not reachable. "
    "Start: python scripts/bridge_server.py --port 8788"
)


def build_explore_futures_payload(
    *,
    as_of_context: dict[str, object],
    base_url: str = DEFAULT_BASE_URL,
) -> dict[str, Any]:
    if not is_available(base_url=base_url):
        return {
            "as_of_context": as_of_context,
            "available": False,
            "bridge_url": base_url,
            "reason": _UNAVAILABLE_REASON,
            "research_only": True,
            "symbol": ADMITTED_FUTURES_INSTRUMENT_ID,
        }
    health = fetch_health(base_url=base_url)
    payload: dict[str, Any] = {
        "as_of_context": as_of_context,
        "available": True,
        "bridge_url": base_url,
        "contract_month": health.get("contract_month"),
        "disclaimer": "Donor bridge snapshot when running; fixture fallback in workspace.",
        "mode": health.get("mode"),
        "research_only": True,
        "symbol": ADMITTED_FUTURES_INSTRUMENT_ID,
    }
    try:
        depth = fetch_depth_latest(base_url=base_url)
        if depth.get("available"):
            snap = depth.get("snapshot", {})
            if isinstance(snap, dict):
                from ..donor_patterns.futures_lane import depth_imbalance_signal

                bids = snap.get("bids", [])
                asks = snap.get("asks", [])
                if isinstance(bids, list) and isinstance(asks, list):
                    signal, _ratio = depth_imbalance_signal(bids, asks)
                    payload["latest_imbalance_signal"] = signal
                payload["snapshot_source"] = str(snap.get("source", "donor_bridge"))
    except (ConnectionError, OSError, ValueError):
        pass
    return payload


__all__ = ["ADMITTED_FUTURES_INSTRUMENT_ID", "build_explore_futures_payload"]
