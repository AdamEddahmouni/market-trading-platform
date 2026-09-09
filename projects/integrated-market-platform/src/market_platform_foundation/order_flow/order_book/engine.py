"""Canonical provider-neutral incremental L2 order-book engine (G5 / ARCH-003).

``IncrementalOrderBook`` is the *single authoritative* book-state engine for
incremental market-by-price (MBP) feeds. Providers (IBKR ``reqMktDepth``,
Moomoo MBP, replay, fixtures) are adapted into :class:`DepthUpdate` events at
the boundary; provider names never enter this state machine.

Explicit mutation semantics (price-keyed; position is advisory rank metadata):

- INSERT at price ``P``: add level ``P`` on the side. Duplicate price with an
  identical size is a benign no-op; a conflicting duplicate is structurally
  corrupt (invalidate, never silently overwrite).
- UPDATE at price ``P``: replace the size of the existing level ``P``. An
  update referencing a missing level is a divergence signal → fail closed
  (invalidate). UPDATE is never a blind whole-book snapshot replacement.
- DELETE of price ``P`` (or of rank ``N`` when no price is carried): remove
  that level and close the rank gap deterministically. Deleting a price whose
  canonical rank disagrees with the carried position is rejected (never delete
  an unrelated rank). Deleting an absent price is a benign no-op.
- RESET: clear all levels, advance the subscription generation, clear sequence
  continuity, and mark the book INVALID (RESET_PENDING) until fresh state is
  applied. RESET is not a delete.

Position semantics: a level's canonical rank is its index in the price-sorted
side (bids descending, asks ascending, 0 = best). When an event carries both a
price and a position they must agree; disagreement is rejected as structurally
corrupt input rather than silently re-ranked.

Validity is *derived truth*, never hard-coded optimism:

- UNAVAILABLE — no event applied yet.
- VALID — at least one level present and no invalidation reason.
- INVALID — reset pending, sequence gap/regression, update-of-missing-level,
  or structurally corrupt input.

Recovery model: invalidation reasons that mean "the engine is out of sync with
the feed" (SEQUENCE_GAP, SEQUENCE_REGRESSION, LEVEL_NOT_FOUND,
STRUCTURALLY_CORRUPT) are *recovery-required*: further non-RESET events are
rejected and cannot silently restore trust. RESET_PENDING / UNINITIALIZED
allow fresh events to re-establish a valid book.

Determinism: the engine never reads a wall clock. Times come only from events.
``state_hash()`` is deterministic for identical event logs.

Zero-size rules: INSERT/UPDATE require ``size > 0``; ``size == 0`` is accepted
only on DELETE. No negative price or size is ever applied.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal
from typing import Any, Iterable, Sequence

from .contracts import (
    ApplyOutcome,
    ApplyResult,
    BOOK_MODEL_VERSION,
    BookLevel,
    BookStatusReason,
    BookValidity,
    DepthOperation,
    DepthSide,
    DepthUpdate,
    SequenceState,
    build_depth_update,
    price_key,
    size_value,
)

#: Invalidation reasons that require explicit recovery (RESET / snapshot).
RECOVERY_REQUIRED_REASONS = frozenset(
    {
        BookStatusReason.SEQUENCE_GAP,
        BookStatusReason.SEQUENCE_REGRESSION,
        BookStatusReason.LEVEL_NOT_FOUND,
        BookStatusReason.STRUCTURALLY_CORRUPT,
    }
)


def _side_label(side: DepthSide) -> str:
    return "bid" if side is DepthSide.BID else "ask"


class IncrementalOrderBook:
    """Canonical incremental L2 book engine for one instrument."""

    def __init__(self, instrument_id: str) -> None:
        if not isinstance(instrument_id, str) or not instrument_id.strip():
            raise ValueError("instrument_id must be a non-empty string")
        self.instrument_id = instrument_id
        self._bids: list[BookLevel] = []  # descending price
        self._asks: list[BookLevel] = []  # ascending price
        self._bid_by_price: dict[Decimal, BookLevel] = {}
        self._ask_by_price: dict[Decimal, BookLevel] = {}
        self.generation: int = 0
        self.subscription_id: str | None = None
        self.update_count: int = 0
        self.reset_count: int = 0
        self.validity: BookValidity = BookValidity.UNAVAILABLE
        self.invalidation_reason: BookStatusReason = BookStatusReason.UNINITIALIZED
        self.last_source_time_ns: int | None = None
        self.last_received_time_ns: int | None = None
        self.last_sequence: int | None = None
        self.sequence_state: SequenceState = SequenceState.NO_SEQUENCE
        self.model_version: str = BOOK_MODEL_VERSION

    # ------------------------------------------------------------------ state

    @property
    def bids(self) -> tuple[BookLevel, ...]:
        return tuple(self._bids)

    @property
    def asks(self) -> tuple[BookLevel, ...]:
        return tuple(self._asks)

    @property
    def is_empty(self) -> bool:
        return not self._bids and not self._asks

    @property
    def is_one_sided(self) -> bool:
        return bool(self._bids) != bool(self._asks)

    @property
    def is_crossed(self) -> bool:
        """True when best bid >= best ask (explicit crossed representation)."""
        best_bid = self.best_bid_price
        best_ask = self.best_ask_price
        return best_bid is not None and best_ask is not None and best_bid >= best_ask

    @property
    def best_bid_price(self) -> Decimal | None:
        return None if not self._bids else self._bids[0].price

    @property
    def best_ask_price(self) -> Decimal | None:
        return None if not self._asks else self._asks[0].price

    @property
    def best_bid_size(self) -> Decimal | None:
        return None if not self._bids else self._bids[0].size

    @property
    def best_ask_size(self) -> Decimal | None:
        return None if not self._asks else self._asks[0].size

    @property
    def spread(self) -> Decimal | None:
        """Uncrossed spread; crossed state never yields a normal spread."""
        if self.is_crossed:
            return None
        if self.best_ask_price is None or self.best_bid_price is None:
            return None
        return self.best_ask_price - self.best_bid_price

    @property
    def book_state_valid(self) -> bool:
        """Derived truth — never hard-coded optimism."""
        return self.validity is BookValidity.VALID

    @property
    def level_counts(self) -> tuple[int, int]:
        return len(self._bids), len(self._asks)

    # ------------------------------------------------------------ generation

    def _ensure_initial_subscription(self, subscription_id: str | None) -> None:
        if subscription_id is None or self.subscription_id is not None:
            return
        self.subscription_id = subscription_id

    # --------------------------------------------------------------- apply

    def apply(self, event: DepthUpdate) -> ApplyResult:
        """Apply one canonical depth event and return an explicit result."""
        if not isinstance(event, DepthUpdate):
            raise TypeError(f"expected DepthUpdate, got {type(event).__name__}")

        # Generation/session gate. RESET is the legal way to change session.
        if (
            event.operation is not DepthOperation.RESET
            and event.subscription_id is not None
            and self.subscription_id is not None
            and event.subscription_id != self.subscription_id
        ):
            return self._result(
                ApplyOutcome.REJECTED,
                BookStatusReason.GENERATION_MISMATCH,
                SequenceState.NO_SEQUENCE,
                state_changed=False,
                message=(
                    f"event subscription {event.subscription_id} != current "
                    f"{self.subscription_id} (generation {self.generation})"
                ),
            )

        # Recovery gate runs BEFORE sequence re-evaluation: once a recovery-
        # required invalidation has occurred (gap/regression/update-of-missing/
        # structural corruption), further events are rejected outright — they
        # can neither silently restore trust nor re-enter the sequence machine.
        # Only an explicit RESET (or full snapshot) is the recovery path.
        if (
            event.operation is not DepthOperation.RESET
            and self.validity is BookValidity.INVALID
            and self.invalidation_reason in RECOVERY_REQUIRED_REASONS
        ):
            return self._result(
                ApplyOutcome.REJECTED,
                self.invalidation_reason,
                self.sequence_state,
                state_changed=False,
                message=(
                    f"recovery required ({self.invalidation_reason.value}); "
                    "RESET or full snapshot before further events"
                ),
            )

        # Sequence gate (pure evaluation; state committed only on acceptance).
        # RESET bypasses sequence evaluation entirely: it is the explicit
        # recovery path and clears sequence continuity itself.
        if event.operation is DepthOperation.RESET:
            allowed, seq_state, invalidating = True, SequenceState.NO_SEQUENCE, None
        else:
            allowed, seq_state, invalidating = self._evaluate_sequence(event.sequence)
        if invalidating is not None:
            reason = (
                BookStatusReason.SEQUENCE_GAP
                if invalidating is SequenceState.GAP
                else BookStatusReason.SEQUENCE_REGRESSION
            )
            self._invalidate(reason)
            return self._result(
                ApplyOutcome.INVALIDATED,
                reason,
                invalidating,
                message=f"sequence state: {invalidating.value} (event {event.sequence})",
            )
        if not allowed:
            return self._result(
                ApplyOutcome.DUPLICATE,
                BookStatusReason.NONE,
                seq_state,
                state_changed=False,
                message=f"duplicate sequence {event.sequence}",
            )

        self._touch_times(event)

        if event.operation is DepthOperation.RESET:
            result = self._apply_reset(event)
        elif event.operation is DepthOperation.INSERT:
            result = self._apply_insert(event)
        elif event.operation is DepthOperation.UPDATE:
            result = self._apply_update(event)
        elif event.operation is DepthOperation.DELETE:
            result = self._apply_delete(event)
        else:
            return self._result(
                ApplyOutcome.REJECTED,
                BookStatusReason.INVALID_OPERATION,
                seq_state,
                state_changed=False,
            )

        # Commit sequence state only for accepted mutations (incl. benign
        # no-ops). RESET clears sequence continuity and is not itself a base
        # event: the next sequenced event re-anchors as BASE.
        if result.outcome in {ApplyOutcome.APPLIED, ApplyOutcome.NOOP}:
            self._commit_sequence(event.sequence)
        return result

    def _touch_times(self, event: DepthUpdate) -> None:
        if event.source_time_ns is not None:
            self.last_source_time_ns = (
                max(self.last_source_time_ns, event.source_time_ns)
                if self.last_source_time_ns is not None
                else event.source_time_ns
            )
        if event.received_time_ns is not None:
            self.last_received_time_ns = (
                max(self.last_received_time_ns, event.received_time_ns)
                if self.last_received_time_ns is not None
                else event.received_time_ns
            )

    def _evaluate_sequence(
        self, sequence: int | None
    ) -> tuple[bool, SequenceState, SequenceState | None]:
        """Pure sequence evaluation. ``invalidating`` non-None ⇒ fail closed."""
        if sequence is None:
            return True, SequenceState.NO_SEQUENCE, None
        if self.last_sequence is None:
            return True, SequenceState.BASE, None
        if sequence == self.last_sequence:
            return False, SequenceState.DUPLICATE, None
        if sequence == self.last_sequence + 1:
            return True, SequenceState.CONTIGUOUS, None
        if sequence > self.last_sequence + 1:
            return False, SequenceState.GAP, SequenceState.GAP
        return False, SequenceState.REGRESSION, SequenceState.REGRESSION

    def _commit_sequence(self, sequence: int | None) -> None:
        if sequence is None:
            return
        if self.last_sequence is None:
            self.last_sequence = sequence
            self.sequence_state = SequenceState.BASE
        else:
            self.last_sequence = sequence
            self.sequence_state = SequenceState.CONTIGUOUS

    def _invalidate(self, reason: BookStatusReason) -> None:
        self.validity = BookValidity.INVALID
        self.invalidation_reason = reason

    # ------------------------------------------------------------ operations

    def _apply_reset(self, event: DepthUpdate) -> ApplyResult:
        self._clear_levels()
        self.last_sequence = None
        self.sequence_state = SequenceState.NO_SEQUENCE
        self.reset_count += 1
        if event.subscription_id is not None:
            changed = event.subscription_id != self.subscription_id
            self.subscription_id = event.subscription_id
            if changed:
                self.generation += 1
        else:
            self.generation += 1
        self._invalidate(BookStatusReason.RESET_PENDING)
        self.update_count += 1
        return self._result(
            ApplyOutcome.RESET_APPLIED,
            BookStatusReason.RESET_PENDING,
            SequenceState.NO_SEQUENCE,
            message="book cleared; fresh state required before valid",
        )

    def _apply_insert(self, event: DepthUpdate) -> ApplyResult:
        side = event.side
        if side is None:
            return self._reject(BookStatusReason.INVALID_SIDE)
        price, size, bad, message = self._coerce_price_size(event, needs_size=True)
        if bad is not None:
            return self._reject(bad, message=message)
        if size <= 0:
            return self._reject(BookStatusReason.ZERO_SIZE)
        if event.position is not None and event.position < 0:
            return self._reject(BookStatusReason.INVALID_OPERATION, message="negative rank")
        levels, by_price = self._side_views(side)

        existing = by_price.get(price)
        if existing is not None:
            if existing.size == size:
                return self._noop(
                    BookStatusReason.LEVEL_ALREADY_EXISTS,
                    message=f"duplicate insert of {price} on {_side_label(side)}",
                )
            self._invalidate(BookStatusReason.STRUCTURALLY_CORRUPT)
            return self._result(
                ApplyOutcome.INVALIDATED,
                BookStatusReason.STRUCTURALLY_CORRUPT,
                SequenceState.NO_SEQUENCE,
                message=(
                    f"conflicting duplicate insert at {price} on "
                    f"{_side_label(side)} (size {existing.size} != {size})"
                ),
            )

        index = self._insert_index(side, price)
        if event.position is not None and event.position != index:
            return self._reject(
                BookStatusReason.STRUCTURALLY_CORRUPT,
                message=(
                    f"insert position {event.position} does not match price-order "
                    f"rank {index} for {price} on {_side_label(side)}"
                ),
            )
        level = BookLevel(price=price, size=size)
        levels.insert(index, level)
        by_price[price] = level
        self._ensure_initial_subscription(event.subscription_id)
        self._after_mutation()
        return self._ok()

    def _apply_update(self, event: DepthUpdate) -> ApplyResult:
        side = event.side
        if side is None:
            return self._reject(BookStatusReason.INVALID_SIDE)
        price, size, bad, message = self._coerce_price_size(event, needs_size=True)
        if bad is not None:
            return self._reject(bad, message=message)
        if size <= 0:
            return self._reject(BookStatusReason.ZERO_SIZE)
        levels, by_price = self._side_views(side)
        existing = by_price.get(price)
        if existing is None:
            if self.book_state_valid:
                self._invalidate(BookStatusReason.LEVEL_NOT_FOUND)
                return self._result(
                    ApplyOutcome.INVALIDATED,
                    BookStatusReason.LEVEL_NOT_FOUND,
                    SequenceState.NO_SEQUENCE,
                    message=f"update of missing level {price} on {_side_label(side)}",
                )
            return self._reject(
                BookStatusReason.LEVEL_NOT_FOUND,
                message=f"update of missing level {price} on {_side_label(side)}",
            )
        rank = levels.index(existing)
        if event.position is not None and event.position != rank:
            return self._reject(
                BookStatusReason.STRUCTURALLY_CORRUPT,
                message=(
                    f"update position {event.position} does not match level rank "
                    f"{rank} for {price} on {_side_label(side)}"
                ),
            )
        replacement = BookLevel(price=price, size=size)
        levels[rank] = replacement
        by_price[price] = replacement
        self._ensure_initial_subscription(event.subscription_id)
        self._after_mutation()
        return self._ok()

    def _apply_delete(self, event: DepthUpdate) -> ApplyResult:
        side = event.side
        if side is None:
            return self._reject(BookStatusReason.INVALID_SIDE)
        levels, by_price = self._side_views(side)

        if event.price is None:
            if event.position is None:
                return self._reject(
                    BookStatusReason.INVALID_OPERATION,
                    message="delete requires price or position",
                )
            if event.position < 0 or event.position >= len(levels):
                return self._reject(
                    BookStatusReason.STRUCTURALLY_CORRUPT,
                    message=f"delete rank {event.position} out of range ({len(levels)} levels)",
                )
            removed = levels.pop(event.position)
            by_price.pop(removed.price, None)
            self._ensure_initial_subscription(event.subscription_id)
            self._after_mutation()
            return self._ok()

        price, _size, bad, message = self._coerce_price_size(event, needs_size=False)
        if bad is not None:
            return self._reject(bad, message=message)
        if price is None:
            return self._reject(BookStatusReason.INVALID_OPERATION, message="delete requires price")
        existing = by_price.get(price)
        if existing is None:
            return self._noop(
                BookStatusReason.LEVEL_NOT_FOUND,
                message=f"delete of absent level {price} on {_side_label(side)}",
            )
        rank = levels.index(existing)
        if event.position is not None and event.position != rank:
            return self._reject(
                BookStatusReason.STRUCTURALLY_CORRUPT,
                message=(
                    f"delete price {price} does not match carried rank "
                    f"{event.position} (actual {rank}) on {_side_label(side)}"
                ),
            )
        levels.pop(rank)
        by_price.pop(price, None)
        self._ensure_initial_subscription(event.subscription_id)
        self._after_mutation()
        return self._ok()

    def _coerce_price_size(
        self, event: DepthUpdate, *, needs_size: bool
    ) -> tuple[Decimal | None, Decimal | None, BookStatusReason | None, str | None]:
        """Validate price/size conversions with explicit rejection results.

        Returns (price, size, rejection_reason, message). A non-None reason
        means the event is rejected without mutation — corrupt feed input
        never crashes the engine and never silently mutates state.
        """
        price: Decimal | None = None
        if event.price is not None:
            try:
                price = price_key(event.price)
            except ValueError as exc:
                return None, None, BookStatusReason.NEGATIVE_PRICE, str(exc)
        size: Decimal | None = None
        if needs_size:
            try:
                size = size_value(event.size)
            except ValueError as exc:
                return None, None, BookStatusReason.NEGATIVE_SIZE, str(exc)
        return price, size, None, None

    # ------------------------------------------------------------ snapshot API

    def replace_from_snapshot(
        self,
        *,
        bids: Sequence[Any],
        asks: Sequence[Any],
        sequence: int | None = None,
        subscription_id: str | None = None,
        source_time_ns: int | None = None,
        received_time_ns: int | None = None,
        provider: str | None = None,
    ) -> ApplyResult:
        """Explicit full-book snapshot ingestion compatibility path.

        This is a *distinct* operation from an incremental UPDATE: it clears
        prior state (RESET semantics), loads the new levels, establishes
        validity, and advances the generation when the subscription changes.
        It never silently merges with the previous book.
        """
        self._clear_levels()
        self.last_sequence = None
        self.sequence_state = SequenceState.NO_SEQUENCE
        if subscription_id is not None and subscription_id != self.subscription_id:
            self.subscription_id = subscription_id
            self.generation += 1
        elif self.subscription_id is None and subscription_id is not None:
            self.subscription_id = subscription_id
        self.reset_count += 1
        if source_time_ns is not None:
            self.last_source_time_ns = source_time_ns
        if received_time_ns is not None:
            self.last_received_time_ns = received_time_ns

        corrupt_reason: BookStatusReason | None = None
        for side, raw in ((DepthSide.BID, bids), (DepthSide.ASK, asks)):
            for row in raw:
                if not isinstance(row, dict):
                    corrupt_reason = BookStatusReason.STRUCTURALLY_CORRUPT
                    break
                try:
                    result = self._bulk_insert(
                        side=side,
                        price=price_key(row.get("price")),
                        size=size_value(row.get("size", row.get("volume", 0))),
                        source=provider,
                        source_time_ns=source_time_ns,
                        received_time_ns=received_time_ns,
                    )
                except (KeyError, TypeError, ValueError):
                    corrupt_reason = BookStatusReason.STRUCTURALLY_CORRUPT
                    break
                if result.outcome in (ApplyOutcome.INVALIDATED, ApplyOutcome.REJECTED):
                    corrupt_reason = result.reason
                    break
            if corrupt_reason is not None:
                break

        if corrupt_reason is not None:
            self._clear_levels()
            self._invalidate(corrupt_reason)
            return self._result(
                ApplyOutcome.INVALIDATED,
                corrupt_reason,
                SequenceState.NO_SEQUENCE,
                message="snapshot import failed; book cleared",
            )

        if sequence is not None:
            self.last_sequence = sequence
            self.sequence_state = SequenceState.BASE
        self.validity = BookValidity.VALID if not self.is_empty else BookValidity.INVALID
        self.invalidation_reason = (
            BookStatusReason.NONE if self.validity is BookValidity.VALID else BookStatusReason.RESET_PENDING
        )
        self.update_count += 1
        return self._result(
            ApplyOutcome.APPLIED,
            self.invalidation_reason,
            self.sequence_state,
            message="full-book snapshot applied",
        )

    def _bulk_insert(
        self,
        *,
        side: DepthSide,
        price: Decimal,
        size: Decimal,
        source: str | None = None,
        source_time_ns: int | None = None,
        received_time_ns: int | None = None,
    ) -> ApplyResult:
        levels, by_price = self._side_views(side)
        existing = by_price.get(price)
        if existing is not None:
            return self._noop(
                BookStatusReason.LEVEL_ALREADY_EXISTS,
                message=f"duplicate snapshot level {price} on {_side_label(side)}",
            )
        index = self._insert_index(side, price)
        level = BookLevel(price=price, size=size)
        levels.insert(index, level)
        by_price[price] = level
        return self._ok()

    # ------------------------------------------------------------ projections

    def to_snapshot_rows(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        return [level.to_row() for level in self._bids], [level.to_row() for level in self._asks]

    def state_dict(self) -> dict[str, Any]:
        """Deterministic canonical state view (float only at presentation)."""
        bids, asks = self.to_snapshot_rows()
        return {
            "instrument_id": self.instrument_id,
            "model_version": self.model_version,
            "generation": self.generation,
            "subscription_id": self.subscription_id,
            "validity": self.validity.value,
            "invalidation_reason": self.invalidation_reason.value,
            "book_state_valid": self.book_state_valid,
            "sequence_state": self.sequence_state.value,
            "last_sequence": self.last_sequence,
            "update_count": self.update_count,
            "reset_count": self.reset_count,
            "last_source_time_ns": self.last_source_time_ns,
            "last_received_time_ns": self.last_received_time_ns,
            "level_counts": {"bid": len(self._bids), "ask": len(self._asks)},
            "bids": bids,
            "asks": asks,
        }

    def state_hash(self) -> str:
        """Deterministic SHA-256 over the canonical state (levels + validity)."""
        parts = [
            self.instrument_id,
            self.model_version,
            str(self.generation),
            self.validity.value,
            self.invalidation_reason.value,
            str(self.last_sequence),
        ]
        for level in self._bids:
            parts.append(f"bid:{level.price}|{level.size}")
        for level in self._asks:
            parts.append(f"ask:{level.price}|{level.size}")
        canonical = "\n".join(parts)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    # --------------------------------------------------------------- helpers

    def _side_views(self, side: DepthSide) -> tuple[list[BookLevel], dict[Decimal, BookLevel]]:
        if side is DepthSide.BID:
            return self._bids, self._bid_by_price
        return self._asks, self._ask_by_price

    def _insert_index(self, side: DepthSide, price: Decimal) -> int:
        """Deterministic insertion index by price ordering (bounded depth)."""
        levels = self._bids if side is DepthSide.BID else self._asks
        if side is DepthSide.BID:
            index = 0
            while index < len(levels) and price < levels[index].price:
                index += 1
            return index
        index = 0
        while index < len(levels) and price > levels[index].price:
            index += 1
        return index

    def _after_mutation(self) -> None:
        if not _ordered_sides(self._bids, self._asks):
            self._clear_levels()
            self._invalidate(BookStatusReason.STRUCTURALLY_CORRUPT)
            return
        self.validity = BookValidity.VALID if not self.is_empty else BookValidity.INVALID
        if self.validity is BookValidity.VALID:
            self.invalidation_reason = BookStatusReason.NONE
        elif self.invalidation_reason in (BookStatusReason.NONE, BookStatusReason.UNINITIALIZED):
            # An emptied book is not corrupt — it is awaiting fresh state.
            self.invalidation_reason = BookStatusReason.RESET_PENDING
        self.update_count += 1

    def _clear_levels(self) -> None:
        self._bids.clear()
        self._asks.clear()
        self._bid_by_price.clear()
        self._ask_by_price.clear()

    def _ok(self) -> ApplyResult:
        return self._result(ApplyOutcome.APPLIED, BookStatusReason.NONE, self.sequence_state)

    def _reject(self, reason: BookStatusReason, *, message: str | None = None) -> ApplyResult:
        return self._result(
            ApplyOutcome.REJECTED, reason, self.sequence_state, state_changed=False, message=message
        )

    def _noop(self, reason: BookStatusReason, *, message: str | None = None) -> ApplyResult:
        return self._result(
            ApplyOutcome.NOOP, reason, self.sequence_state, state_changed=False, message=message
        )

    def _result(
        self,
        outcome: ApplyOutcome,
        reason: BookStatusReason,
        sequence_state: SequenceState,
        *,
        state_changed: bool = True,
        message: str | None = None,
    ) -> ApplyResult:
        return ApplyResult(
            outcome=outcome,
            reason=reason,
            sequence_state=sequence_state,
            book_valid=self.book_state_valid,
            book_validity=self.validity,
            generation=self.generation,
            update_count=self.update_count,
            state_changed=state_changed,
            best_bid=self.best_bid_price,
            best_ask=self.best_ask_price,
            sequence=self.last_sequence,
            message=message,
        )


def _ordered_sides(bids: Sequence[BookLevel], asks: Sequence[BookLevel]) -> bool:
    """Both sides are unique-price and monotonically ordered."""
    bid_prices = [level.price for level in bids]
    if len(set(bid_prices)) != len(bid_prices):
        return False
    if not all(a > b for a, b in zip(bid_prices, bid_prices[1:])):
        return False
    ask_prices = [level.price for level in asks]
    if len(set(ask_prices)) != len(ask_prices):
        return False
    if not all(a < b for a, b in zip(ask_prices, ask_prices[1:])):
        return False
    return True


__all__ = ["IncrementalOrderBook", "RECOVERY_REQUIRED_REASONS"]
