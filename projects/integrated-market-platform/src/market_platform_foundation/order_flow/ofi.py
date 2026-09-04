"""Versioned OFI (order flow imbalance) book-flow primitives — Order Flow OF4."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from ..donor_patterns.cvd_formulas import ofi_events

OFI_METHOD_BBO_DELTA = "ofi_bbo_delta_v1"
OFI_METHOD_MULTILEVEL_CS = "ofi_multilevel_cs_v1"
OFI_VERSION_BBO = "1"
OFI_VERSION_MULTILEVEL = "1"


@dataclass(frozen=True, slots=True)
class OFIResult:
    value: float
    ofi_method: str
    ofi_version: str
    book_state_valid: bool
    level_count: int | None = None


def _is_valid_level_row(row: object) -> bool:
    if not isinstance(row, dict):
        return False
    try:
        price = float(row["price"])
        size = float(row["size"])
    except (KeyError, TypeError, ValueError):
        return False
    return not math.isnan(price) and not math.isnan(size)


def snapshot_book_state_valid(snapshot: dict[str, Any] | None) -> bool:
    """Fail-closed when bids/asks missing, empty, or contain invalid numeric rows."""
    if snapshot is None or not isinstance(snapshot, dict):
        return False
    bids = snapshot.get("bids", [])
    asks = snapshot.get("asks", [])
    if not isinstance(bids, list) or not isinstance(asks, list):
        return False
    if not bids or not asks:
        return False
    return all(_is_valid_level_row(row) for row in bids) and all(
        _is_valid_level_row(row) for row in asks
    )


def _snapshot_has_book_sequence(snapshot: dict[str, Any]) -> bool:
    raw = snapshot.get("book_sequence")
    return isinstance(raw, int) and not isinstance(raw, bool)


def snapshot_pair_sequence_valid(
    prev_snapshot: dict[str, Any],
    curr_snapshot: dict[str, Any],
) -> tuple[bool, tuple[str, ...]]:
    """Validate optional book_sequence continuity between snapshot pairs (OF-D11)."""
    prev_has = _snapshot_has_book_sequence(prev_snapshot)
    curr_has = _snapshot_has_book_sequence(curr_snapshot)
    if not prev_has and not curr_has:
        return True, ()
    if prev_has != curr_has:
        return False, ("BOOK_SEQUENCE_MISSING",)
    prev_seq = int(prev_snapshot["book_sequence"])
    curr_seq = int(curr_snapshot["book_sequence"])
    if curr_seq <= prev_seq or curr_seq - prev_seq != 1:
        return False, ("BOOK_SEQUENCE_GAP",)
    return True, ()


def snapshot_pair_book_state_valid(
    prev_snapshot: dict[str, Any],
    curr_snapshot: dict[str, Any],
) -> bool:
    """Structure + optional sequence continuity for pair-wise book metrics."""
    if not snapshot_book_state_valid(prev_snapshot) or not snapshot_book_state_valid(curr_snapshot):
        return False
    seq_valid, _ = snapshot_pair_sequence_valid(prev_snapshot, curr_snapshot)
    return seq_valid


def _best_bid_ask(snapshot: dict[str, Any]) -> tuple[float, float, float, float] | None:
    bids = snapshot.get("bids", [])
    asks = snapshot.get("asks", [])
    if not isinstance(bids, list) or not isinstance(asks, list) or not bids or not asks:
        return None
    best_bid = max(bids, key=lambda row: float(row["price"]))
    best_ask = min(asks, key=lambda row: float(row["price"]))
    return (
        float(best_bid["price"]),
        float(best_bid["size"]),
        float(best_ask["price"]),
        float(best_ask["size"]),
    )


def _sorted_bids(bids: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(bids, key=lambda row: float(row["price"]), reverse=True)


def _sorted_asks(asks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(asks, key=lambda row: float(row["price"]))


def _level_at_rank(levels: list[dict[str, Any]], rank: int) -> tuple[float, float]:
    if rank < len(levels):
        row = levels[rank]
        return float(row["price"]), float(row["size"])
    return 0.0, 0.0


def _cs_ofi_contribution(
    pb0: float,
    pa0: float,
    qb0: float,
    qa0: float,
    pb1: float,
    pa1: float,
    qb1: float,
    qa1: float,
) -> float:
    events = ofi_events(
        [pb0, pb1],
        [pa0, pa1],
        [qb0, qb1],
        [qa0, qa1],
    )
    return events[-1] if events else 0.0


def compute_bbo_ofi(
    prev_snapshot: dict[str, Any],
    curr_snapshot: dict[str, Any],
) -> OFIResult:
    """BBO-only Cont-Kukanov-Stoikov OFI delta between two snapshots."""
    if not snapshot_pair_book_state_valid(prev_snapshot, curr_snapshot):
        return OFIResult(
            value=0.0,
            ofi_method=OFI_METHOD_BBO_DELTA,
            ofi_version=OFI_VERSION_BBO,
            book_state_valid=False,
            level_count=1,
        )
    prev_bbo = _best_bid_ask(prev_snapshot)
    curr_bbo = _best_bid_ask(curr_snapshot)
    if prev_bbo is None or curr_bbo is None:
        return OFIResult(
            value=0.0,
            ofi_method=OFI_METHOD_BBO_DELTA,
            ofi_version=OFI_VERSION_BBO,
            book_state_valid=False,
            level_count=1,
        )
    pb0, qb0, pa0, qa0 = prev_bbo[0], prev_bbo[1], prev_bbo[2], prev_bbo[3]
    pb1, qb1, pa1, qa1 = curr_bbo[0], curr_bbo[1], curr_bbo[2], curr_bbo[3]
    value = round(_cs_ofi_contribution(pb0, pa0, qb0, qa0, pb1, pa1, qb1, qa1), 4)
    return OFIResult(
        value=value,
        ofi_method=OFI_METHOD_BBO_DELTA,
        ofi_version=OFI_VERSION_BBO,
        book_state_valid=True,
        level_count=1,
    )


def compute_multilevel_ofi(
    prev_snapshot: dict[str, Any],
    curr_snapshot: dict[str, Any],
    *,
    level_count: int = 10,
) -> OFIResult:
    """Multi-level rank-based CS OFI summed across bid/ask depth ranks."""
    if not snapshot_pair_book_state_valid(prev_snapshot, curr_snapshot):
        return OFIResult(
            value=0.0,
            ofi_method=OFI_METHOD_MULTILEVEL_CS,
            ofi_version=OFI_VERSION_MULTILEVEL,
            book_state_valid=False,
            level_count=level_count,
        )
    prev_bids = _sorted_bids(prev_snapshot["bids"])
    prev_asks = _sorted_asks(prev_snapshot["asks"])
    curr_bids = _sorted_bids(curr_snapshot["bids"])
    curr_asks = _sorted_asks(curr_snapshot["asks"])
    total = 0.0
    for rank in range(level_count):
        pb0, qb0 = _level_at_rank(prev_bids, rank)
        pb1, qb1 = _level_at_rank(curr_bids, rank)
        pa0, qa0 = _level_at_rank(prev_asks, rank)
        pa1, qa1 = _level_at_rank(curr_asks, rank)
        total += _cs_ofi_contribution(pb0, pa0, qb0, qa0, pb1, pa1, qb1, qa1)
    return OFIResult(
        value=round(total, 4),
        ofi_method=OFI_METHOD_MULTILEVEL_CS,
        ofi_version=OFI_VERSION_MULTILEVEL,
        book_state_valid=True,
        level_count=level_count,
    )


def compute_ofi(
    prev_snapshot: dict[str, Any],
    curr_snapshot: dict[str, Any],
    *,
    method: str = OFI_METHOD_MULTILEVEL_CS,
    level_count: int = 10,
) -> OFIResult:
    """Compute OFI using a versioned method; fail-closed when book state is invalid."""
    if method == OFI_METHOD_BBO_DELTA:
        return compute_bbo_ofi(prev_snapshot, curr_snapshot)
    if method == OFI_METHOD_MULTILEVEL_CS:
        return compute_multilevel_ofi(prev_snapshot, curr_snapshot, level_count=level_count)
    return OFIResult(
        value=0.0,
        ofi_method=method,
        ofi_version="0",
        book_state_valid=False,
        level_count=level_count,
    )


__all__ = [
    "OFI_METHOD_BBO_DELTA",
    "OFI_METHOD_MULTILEVEL_CS",
    "OFI_VERSION_BBO",
    "OFI_VERSION_MULTILEVEL",
    "OFIResult",
    "compute_bbo_ofi",
    "compute_multilevel_ofi",
    "compute_ofi",
    "snapshot_book_state_valid",
    "snapshot_pair_book_state_valid",
    "snapshot_pair_sequence_valid",
]
