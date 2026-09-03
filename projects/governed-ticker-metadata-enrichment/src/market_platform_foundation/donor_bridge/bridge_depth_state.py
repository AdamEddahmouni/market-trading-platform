"""In-process previous-snapshot cache for donor-bridge depth (OF-D10)."""

from __future__ import annotations

from typing import Any

from ..order_flow.ofi import OFI_METHOD_MULTILEVEL_CS, compute_ofi

_PREV_SNAPSHOTS: dict[str, dict[str, Any]] = {}
DEFAULT_LEVEL_COUNT = 10


def get_prev(symbol: str) -> dict[str, Any] | None:
    """Return the last bridge depth snapshot for symbol, if any."""
    key = symbol.upper()
    prev = _PREV_SNAPSHOTS.get(key)
    if isinstance(prev, dict):
        return prev
    return None


def update(symbol: str, snapshot: dict[str, Any]) -> None:
    """Store snapshot as the previous reference for the next bridge read."""
    if not isinstance(snapshot, dict):
        return
    _PREV_SNAPSHOTS[symbol.upper()] = snapshot


def clear(symbol: str | None = None) -> None:
    """Clear cache for one symbol or all symbols (tests)."""
    if symbol is None:
        _PREV_SNAPSHOTS.clear()
        return
    _PREV_SNAPSHOTS.pop(symbol.upper(), None)


def resolve_bridge_ofi(
    symbol: str,
    snapshot: dict[str, Any],
    *,
    level_count: int = DEFAULT_LEVEL_COUNT,
) -> dict[str, Any]:
    """Compute OFI from cached prev snapshot or fail-closed degrade when no prev exists."""
    prev = get_prev(symbol)
    if prev is None:
        return {
            "ofi_value": None,
            "ofi_method": None,
            "ofi_version": None,
            "book_state_valid": False,
            "ofi_degraded": True,
            "ofi_quality_flags": ["NO_PREV_SNAPSHOT"],
        }
    result = compute_ofi(
        prev,
        snapshot,
        method=OFI_METHOD_MULTILEVEL_CS,
        level_count=level_count,
    )
    flags: list[str] = []
    if not result.book_state_valid:
        flags.append("BOOK_STATE_INVALID")
    return {
        "ofi_value": result.value,
        "ofi_method": result.ofi_method,
        "ofi_version": result.ofi_version,
        "book_state_valid": result.book_state_valid,
        "ofi_degraded": False,
        "ofi_quality_flags": flags,
    }


__all__ = ["clear", "get_prev", "resolve_bridge_ofi", "update"]
