"""IBKR depth position/rank translation (G6 critical rule).

IBKR depth is POSITION-ORIENTED: ``updateMktDepth`` says *operate on row N*
and carries a price that is advisory. The canonical G5 book is PRICE-KEYED
with position used for consistency checks. This module maintains
adapter-local provider rank state per side and translates each callback into
canonical :class:`~market_platform_foundation.order_flow.order_book.contracts.DepthUpdate`
events that are truthful about the provider transition:

- **INSERT at N**: new level at rank N, later ranks shift right →
  canonical INSERT at the supplied price.
- **UPDATE at N with same price**: size replacement → canonical UPDATE.
  With ``size == 0`` the feed semantics imply removal → canonical DELETE
  (the G5 matrix 14b rule: IBKR zero-size updates map to DELETE).
- **UPDATE at N with a different price**: the level at N moved →
  canonical DELETE of the OLD price + INSERT of the NEW price. A price-
  changing UPDATE is never emitted as a canonical UPDATE that would leave a
  stale old-price level (the canonical engine keys by price).
- **DELETE at N**: the provider delete price is NOT trusted; the canonical
  price is resolved from adapter rank state (or the current canonical
  snapshot via ``resolve_snapshot_price``) before emitting canonical DELETE.

Disagreement (INSERT beyond the rank frontier, UPDATE/DELETE at a rank with
no level, unresolved delete price) fails closed with a diagnostic reason and
requires a RESET/re-snapshot — the adapter never guesses.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Callable, Mapping

from ...order_flow.order_book.contracts import (
    DepthOperation,
    DepthSide,
    DepthUpdate,
    build_depth_update,
)
from .constants import IB_OP_DELETE, IB_OP_INSERT, IB_OP_UPDATE, IB_SIDE_BID
from .contracts import DepthTranslationOutcome, RankLevel


class RankDisagreement(RuntimeError):
    """Raised on provider rank state disagreement (fail closed)."""


def _side_label(side: DepthSide) -> str:
    return "bid" if side is DepthSide.BID else "ask"


class SubscriptionRankState:
    """Provider-side rank state for ONE depth subscription (one side each).

    ``bids``/``asks`` are position-indexed lists (0 = inside best). All
    mutations happen under the adapter lock.
    """

    def __init__(self) -> None:
        self.bids: list[RankLevel] = []
        self.asks: list[RankLevel] = []

    def side_levels(self, side: DepthSide) -> list[RankLevel]:
        return self.bids if side is DepthSide.BID else self.asks

    def clear(self) -> None:
        self.bids.clear()
        self.asks.clear()

    def as_dict(self) -> dict[str, Any]:
        return {
            "asks": [level.as_dict() for level in self.asks],
            "bids": [level.as_dict() for level in self.bids],
        }


#: Resolver for the canonical book's price at a rank when adapter rank state
#: cannot answer (delete of an unknown-rank level). Returns None when unknown.
SnapshotPriceResolver = Callable[[DepthSide, int], Decimal | None]


def translate_depth_callback(
    rank_state: SubscriptionRankState,
    *,
    instrument_id: str,
    subscription_id: str,
    generation: int,
    side_value: int,
    operation_value: int,
    position: int,
    price: float | None,
    size: float | None,
    market_maker: str | None = None,
    is_smart_depth: bool | None = None,
    callback_type: str = "updateMktDepth",
    source_time_ns: int | None = None,
    received_time_ns: int | None = None,
    provider_req_id: int | None = None,
    resolve_snapshot_price: SnapshotPriceResolver | None = None,
) -> tuple[DepthTranslationOutcome, list[DepthUpdate], str | None]:
    """Translate one verified IB depth callback into canonical events.

    Returns ``(outcome, events, reason)``. ``events`` is empty unless the
    outcome is APPLIED. ``reason`` carries a diagnostic on DEGRADED/REJECTED.
    """
    from .mapping import decode_depth_operation, decode_depth_side, exact_price, exact_size

    try:
        operation = decode_depth_operation(operation_value)
        side = decode_depth_side(side_value)
    except ValueError as exc:
        return DepthTranslationOutcome.REJECTED, [], str(exc)
    if not isinstance(position, int) or isinstance(position, bool) or position < 0:
        return DepthTranslationOutcome.REJECTED, [], f"invalid depth position: {position!r}"
    levels = rank_state.side_levels(side)

    def provenance() -> dict[str, Any]:
        facts: dict[str, Any] = {
            "callback_type": callback_type,
            "provider_req_id": provider_req_id,
            "generation": generation,
        }
        if market_maker is not None:
            facts["market_maker"] = market_maker
        if is_smart_depth is not None:
            facts["is_smart_depth"] = bool(is_smart_depth)
        return facts

    def event(op: DepthOperation, px: object, sz: object | None, pos: int | None) -> DepthUpdate:
        return build_depth_update(
            instrument_id=instrument_id,
            operation=op,
            side=side,
            price=px,
            size=sz,
            position=pos,
            source="IBKR",
            source_time_ns=source_time_ns,
            received_time_ns=received_time_ns,
            subscription_id=subscription_id,
            provider_event_id=(
                f"{provider_req_id}:{operation_value}:{position}:{callback_type}"
                if provider_req_id is not None
                else None
            ),
            provenance=provenance(),
        )

    if operation is DepthOperation.INSERT:
        return _translate_insert(
            levels,
            side=side,
            position=position,
            price=price,
            size=size,
            event=event,
            instrument_id=instrument_id,
            market_maker=market_maker,
        )

    if operation is DepthOperation.UPDATE:
        return _translate_update(
            levels,
            side=side,
            position=position,
            price=price,
            size=size,
            event=event,
        )

    # DELETE — never trust the provider delete price blindly.
    return _translate_delete(
        levels,
        side=side,
        position=position,
        price=price,
        event=event,
        instrument_id=instrument_id,
        resolve_snapshot_price=resolve_snapshot_price,
    )


def _translate_insert(
    levels: list[RankLevel],
    *,
    side: DepthSide,
    position: int,
    price: float | None,
    size: float | None,
    event: Callable[..., DepthUpdate],
    instrument_id: str,
    market_maker: str | None,
) -> tuple[DepthTranslationOutcome, list[DepthUpdate], str | None]:
    if price is None or size is None:
        return (
            DepthTranslationOutcome.REJECTED,
            [],
            f"insert at position {position} missing price or size",
        )
    if position > len(levels):
        return (
            DepthTranslationOutcome.DEGRADED,
            [],
            f"insert position {position} beyond rank frontier {len(levels)} "
            f"on {_side_label(side)}",
        )
    if size <= 0:
        # A zero-size insert is not a level; treat as a no-op (some feeds
        # pre-announce removals this way). Do not fabricate a level.
        return DepthTranslationOutcome.IGNORED, [], "zero-size insert ignored"
    dec_price = _exact(price)
    if dec_price is None or dec_price < 0:
        return DepthTranslationOutcome.REJECTED, [], f"invalid insert price: {price!r}"
    dec_size = _exact_size(size)
    if dec_size is None or dec_size <= 0:
        return DepthTranslationOutcome.REJECTED, [], f"invalid insert size: {size!r}"
    levels.insert(position, RankLevel(price=price, size=size, market_maker=market_maker))
    return (
        DepthTranslationOutcome.APPLIED,
        [event(DepthOperation.INSERT, dec_price, dec_size, position)],
        None,
    )


def _translate_update(
    levels: list[RankLevel],
    *,
    side: DepthSide,
    position: int,
    price: float | None,
    size: float | None,
    event: Callable[..., DepthUpdate],
) -> tuple[DepthTranslationOutcome, list[DepthUpdate], str | None]:
    if position >= len(levels):
        return (
            DepthTranslationOutcome.DEGRADED,
            [],
            f"update at position {position} has no provider rank level "
            f"({len(levels)} levels on {_side_label(side)})",
        )
    existing = levels[position]
    if price is None:
        return DepthTranslationOutcome.REJECTED, [], "update missing price"
    dec_price = _exact(price)
    if dec_price is None or dec_price < 0:
        return DepthTranslationOutcome.REJECTED, [], f"invalid update price: {price!r}"

    if price == existing.price:
        # Size-only update at the same price.
        if size is None:
            return DepthTranslationOutcome.REJECTED, [], "update missing size"
        if size <= 0:
            # Zero-size update implies removal (14b rule).
            levels.pop(position)
            return (
                DepthTranslationOutcome.APPLIED,
                [event(DepthOperation.DELETE, dec_price, None, position)],
                None,
            )
        dec_size = _exact_size(size)
        if dec_size is None or dec_size <= 0:
            return DepthTranslationOutcome.REJECTED, [], f"invalid update size: {size!r}"
        levels[position] = RankLevel(
            price=price,
            size=size,
            market_maker=existing.market_maker,
        )
        return (
            DepthTranslationOutcome.APPLIED,
            [event(DepthOperation.UPDATE, dec_price, dec_size, position)],
            None,
        )

    # Price changed at this rank: the level moved. Never emit a canonical
    # UPDATE that would leave stale old-price state.
    old = levels[position]
    if size is None or size <= 0:
        levels.pop(position)
        return (
            DepthTranslationOutcome.APPLIED,
            [event(DepthOperation.DELETE, _exact(old.price), None, position)],
            None,
        )
    dec_new = _exact_size(size)
    if dec_new is None or dec_new <= 0:
        return DepthTranslationOutcome.REJECTED, [], f"invalid update size: {size!r}"
    levels[position] = RankLevel(price=price, size=size, market_maker=existing.market_maker)
    return (
        DepthTranslationOutcome.APPLIED,
        [
            event(DepthOperation.DELETE, _exact(old.price), None, position),
            event(DepthOperation.INSERT, dec_price, dec_new, position),
        ],
        None,
    )


def _translate_delete(
    levels: list[RankLevel],
    *,
    side: DepthSide,
    position: int,
    price: float | None,
    event: Callable[..., DepthUpdate],
    instrument_id: str,
    resolve_snapshot_price: SnapshotPriceResolver | None,
) -> tuple[DepthTranslationOutcome, list[DepthUpdate], str | None]:
    if position >= len(levels):
        # The adapter rank state has no level at this position. Try the
        # canonical snapshot (a valid book may exist even when the local
        # rank state was cleared); otherwise fail closed.
        resolved = _resolve_external(side, position, price, resolve_snapshot_price)
        if resolved is None:
            return (
                DepthTranslationOutcome.DEGRADED,
                [],
                f"delete at position {position} has no provider rank level "
                f"({len(levels)} levels on {_side_label(side)}) and no snapshot price",
            )
        return (
            DepthTranslationOutcome.APPLIED,
            [event(DepthOperation.DELETE, resolved, None, position)],
            None,
        )
    existing = levels[position]
    levels.pop(position)
    return (
        DepthTranslationOutcome.APPLIED,
        [event(DepthOperation.DELETE, _exact(existing.price), None, position)],
        None,
    )


def _resolve_external(
    side: DepthSide,
    position: int,
    provider_price: float | None,
    resolve_snapshot_price: SnapshotPriceResolver | None,
) -> Decimal | None:
    """Resolve a delete price from the canonical snapshot or the provider.

    The provider delete price is used only as a last resort AND only when the
    callback-side snapshot resolver confirms it; otherwise we fail closed.
    """
    if resolve_snapshot_price is not None:
        resolved = resolve_snapshot_price(side, position)
        if resolved is not None:
            return resolved
    if provider_price is not None and provider_price > 0:
        # No snapshot authority to contradict it; keep it as a last resort
        # only when it is a positive price. (Snapshot resolver absence is an
        # adapter configuration choice; the canonical book will still
        # cross-check rank agreement on its own apply.)
        dec = _exact(provider_price)
        if dec is not None and dec > 0:
            return dec
    return None


def _exact(value: object) -> Decimal | None:
    from .mapping import exact_price

    try:
        return exact_price(value)
    except ValueError:
        return None


def _exact_size(value: object) -> Decimal | None:
    from .mapping import exact_size

    try:
        return exact_size(value)
    except ValueError:
        return None


def rank_side_from_ib_side(side_value: int) -> DepthSide:
    """Return the canonical side for a verified IB side integer."""
    from .mapping import decode_depth_side

    return decode_depth_side(side_value)


__all__ = [
    "RankDisagreement",
    "SnapshotPriceResolver",
    "SubscriptionRankState",
    "rank_side_from_ib_side",
    "translate_depth_callback",
]