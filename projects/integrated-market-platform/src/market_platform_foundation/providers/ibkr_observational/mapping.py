"""Pure decoding of verified IBKR callback facts into canonical facts (G6).

Every function here is a pure mapping (no I/O, no clock). The exact IBKR
integers are pinned in :mod:`.constants` with their evidence chain; tests
assert the verified values so a correction is a one-place change.

Delayed tick fields are classified delayed and never presented as real-time.
Unknown integers are rejected (fail closed) rather than guessed.
"""

from __future__ import annotations

from decimal import Decimal

from ...order_flow.order_book.contracts import (
    DepthOperation,
    DepthSide,
    price_key,
    size_value,
)
from .constants import (
    IB_DEPTH_OPERATIONS,
    IB_DEPTH_SIDES,
    IB_OP_DELETE,
    IB_OP_INSERT,
    IB_OP_UPDATE,
    IB_SIDE_ASK,
    IB_SIDE_BID,
    TICK_ASK,
    TICK_ASK_SIZE,
    TICK_BID,
    TICK_BID_SIZE,
    TICK_DELAYED_ASK,
    TICK_DELAYED_ASK_SIZE,
    TICK_DELAYED_BID,
    TICK_DELAYED_BID_SIZE,
    TICK_DELAYED_FIELDS,
    TICK_DELAYED_LAST,
    TICK_DELAYED_LAST_SIZE,
    TICK_LAST,
    TICK_LAST_SIZE,
)
from .contracts import IbkrProviderError
from .errors import normalize_provider_error


class UnknownIbOperation(ValueError):
    """Raised when an IB depth ``operation`` integer is not 0/1/2."""


class UnknownIbSide(ValueError):
    """Raised when an IB depth ``side`` integer is not 0/1."""


def decode_depth_operation(value: int) -> DepthOperation:
    """Verified IB operation → canonical ``DepthOperation``.

    IB insert(0) → INSERT; update(1) → UPDATE; delete/remove(2) → DELETE.
    """
    if value == IB_OP_INSERT:
        return DepthOperation.INSERT
    if value == IB_OP_UPDATE:
        return DepthOperation.UPDATE
    if value == IB_OP_DELETE:
        return DepthOperation.DELETE
    raise UnknownIbOperation(f"unverified IB depth operation integer: {value!r}")


def decode_depth_side(value: int) -> DepthSide:
    """Verified IB side → canonical ``DepthSide`` (0=ASK, 1=BID)."""
    if value == IB_SIDE_ASK:
        return DepthSide.ASK
    if value == IB_SIDE_BID:
        return DepthSide.BID
    raise UnknownIbSide(f"unverified IB depth side integer: {value!r}")


def is_verified_depth_operation(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value in IB_DEPTH_OPERATIONS


def is_verified_depth_side(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value in IB_DEPTH_SIDES


def exact_price(value: object) -> Decimal:
    """Canonical Decimal price via the decimal text form (G5 boundary rule)."""
    return price_key(value)


def exact_size(value: object) -> Decimal:
    """Canonical Decimal size via the decimal text form (G5 boundary rule)."""
    return size_value(value)


# --------------------------------------------------------------------------- #
# L1 tick field classification
# --------------------------------------------------------------------------- #


class TickFieldMapping:
    """Verified classification of ``reqMktData`` tick fields.

    Attributes carry ``(kind, delayed, slot)`` where ``kind`` is
    ``PRICE``/``SIZE``/``OTHER``, ``delayed`` marks the delayed family, and
    ``slot`` names the canonical L1 accumulation slot.
    """

    __slots__ = ("kind", "delayed", "slot")

    def __init__(self, kind: str, delayed: bool, slot: str | None = None) -> None:
        self.kind = kind
        self.delayed = delayed
        self.slot = slot


_L1_PRICE_SLOTS = {
    TICK_BID: ("bid_price", False),
    TICK_ASK: ("ask_price", False),
    TICK_LAST: ("last_price", False),
    TICK_DELAYED_BID: ("bid_price", True),
    TICK_DELAYED_ASK: ("ask_price", True),
    TICK_DELAYED_LAST: ("last_price", True),
}
_L1_SIZE_SLOTS = {
    TICK_BID_SIZE: ("bid_size", False),
    TICK_ASK_SIZE: ("ask_size", False),
    TICK_LAST_SIZE: ("last_size", False),
    TICK_DELAYED_BID_SIZE: ("bid_size", True),
    TICK_DELAYED_ASK_SIZE: ("ask_size", True),
    TICK_DELAYED_LAST_SIZE: ("last_size", True),
}
_PRICE_FIELDS = frozenset(_L1_PRICE_SLOTS)
_SIZE_FIELDS = frozenset(_L1_SIZE_SLOTS)
_DELAYED_FIELDS = frozenset(TICK_DELAYED_FIELDS)


def classify_tick_field(field: int) -> TickFieldMapping:
    """Classify a tick field integer, rejecting anything unverified."""
    if field in _L1_PRICE_SLOTS:
        slot, delayed = _L1_PRICE_SLOTS[field]
        return TickFieldMapping("PRICE", delayed, slot)
    if field in _L1_SIZE_SLOTS:
        slot, delayed = _L1_SIZE_SLOTS[field]
        return TickFieldMapping("SIZE", delayed, slot)
    if field in _PRICE_FIELDS or field in _SIZE_FIELDS or field in _DELAYED_FIELDS:
        return TickFieldMapping("OTHER", field in _DELAYED_FIELDS)
    return TickFieldMapping("UNKNOWN", False)


def is_delayed_tick_field(field: int) -> bool:
    return field in TICK_DELAYED_FIELDS


# --------------------------------------------------------------------------- #
# provider error normalization
# --------------------------------------------------------------------------- #


def normalize_error(
    *,
    code: int | None,
    message: str,
    req_id: int | None = None,
) -> IbkrProviderError:
    """Normalize a provider error into a documented category.

    Only codes with an authoritative local/official mapping are categorized;
    everything else stays ``UNKNOWN_PROVIDER_ERROR`` with the raw safe code
    and message. No secret/account data is carried.
    """
    return normalize_provider_error(code=code, message=message, req_id=req_id)


__all__ = [
    "UnknownIbOperation",
    "UnknownIbSide",
    "TickFieldMapping",
    "classify_tick_field",
    "decode_depth_operation",
    "decode_depth_side",
    "exact_price",
    "exact_size",
    "is_delayed_tick_field",
    "is_verified_depth_operation",
    "is_verified_depth_side",
    "normalize_error",
]