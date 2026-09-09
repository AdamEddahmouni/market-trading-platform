"""Canonical incremental L2 order-book event contracts (G5 / ARCH-003).

This module defines the *provider-neutral* canonical vocabulary for an
incremental market-by-price (MBP) order book. Provider-specific depth feeds
(IBKR ``reqMktDepth``, Moomoo MBP, captured replay, fixtures, ...) are adapted
to this vocabulary at the boundary; provider fields never leak past the
adapter except as explicit provenance metadata.

Key principle: the engine is price-keyed and side-ordered. ``position`` is
advisory feed rank metadata used for cross-checks and G6 adapter mapping, not
the level identity. Levels are uniquely identified by (side, exact price).

Exact numerics: price/size are ``Decimal`` inside the canonical domain,
constructed from the decimal text form of the adapter value (``Decimal(str(v))``)
so that binary-float provider values are normalized deliberately at the
boundary. Float appears only in legacy snapshot projection, mirroring how the
portfolio kernel keeps Decimal internally and floats only at JSON boundaries.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any, Mapping

#: Canonical book model version. Bump only on a *semantic* contract change.
BOOK_MODEL_VERSION = "order_book/v1"
#: Canonical depth-event schema version carried on every event.
DEPTH_EVENT_SCHEMA_VERSION = "depth_event/v1"


class DepthOperation(StrEnum):
    """Canonical incremental depth operations (MBP level semantics)."""

    INSERT = "INSERT"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    RESET = "RESET"


class DepthSide(StrEnum):
    """Canonical book side."""

    BID = "BID"
    ASK = "ASK"


class ApplyOutcome(StrEnum):
    """Explicit per-operation result outcome.

    Callers must never infer success: every apply returns one of these.
    """

    APPLIED = "APPLIED"
    NOOP = "NOOP"  # state did not change (e.g. benign resend / delete of missing level)
    DUPLICATE = "DUPLICATE"  # already-applied sequence / identical re-insert
    REJECTED = "REJECTED"  # rejected event, no mutation
    INVALIDATED = "INVALIDATED"  # book invalidated (gap/regression/corruption)
    RESET_APPLIED = "RESET_APPLIED"


class SequenceState(StrEnum):
    """Truthful per-event sequence evaluation.

    ``NO_SEQUENCE`` means the provider does not supply a usable sequence; the
    book may still operate under ordered delivery but protection is absent and
    the state is exposed truthfully. ``BASE`` is the first observed sequence
    (accepted as an anchor).
    """

    NO_SEQUENCE = "NO_SEQUENCE"
    BASE = "BASE"
    CONTIGUOUS = "CONTIGUOUS"
    DUPLICATE = "DUPLICATE"
    GAP = "GAP"
    REGRESSION = "REGRESSION"


class BookValidity(StrEnum):
    """Canonical validity of the book state itself (trust, not freshness).

    - ``UNAVAILABLE``: no authoritative data has been applied yet.
    - ``VALID``: state is internally consistent and trusted.
    - ``INVALID``: state is not trustworthy (reset pending, gap, regression,
      structurally corrupt input); recovery (RESET + fresh snapshot/state)
      is required before downstream safety logic may consume it.
    """

    UNAVAILABLE = "UNAVAILABLE"
    VALID = "VALID"
    INVALID = "INVALID"


APPLY_OUTCOMES = frozenset(item.value for item in ApplyOutcome)


class FreshnessStatus(StrEnum):
    """Freshness evaluation result — never collapsed into validity.

    A stale-but-valid book must not present ``book_state_valid=true`` without
    an explicit staleness qualifier downstream safety logic can consume.
    """

    FRESH = "FRESH"
    STALE = "STALE"
    INVALID = "INVALID"
    UNAVAILABLE = "UNAVAILABLE"


class BookStatusReason(StrEnum):
    """Explicit invalidation reason (validity + sequence + reset)."""

    NONE = "NONE"
    UNINITIALIZED = "UNINITIALIZED"
    RESET_PENDING = "RESET_PENDING"
    SEQUENCE_GAP = "SEQUENCE_GAP"
    SEQUENCE_REGRESSION = "SEQUENCE_REGRESSION"
    LEVEL_NOT_FOUND = "LEVEL_NOT_FOUND"
    LEVEL_ALREADY_EXISTS = "LEVEL_ALREADY_EXISTS"
    NEGATIVE_PRICE = "NEGATIVE_PRICE"
    NEGATIVE_SIZE = "NEGATIVE_SIZE"
    ZERO_SIZE = "ZERO_SIZE"
    INVALID_SIDE = "INVALID_SIDE"
    INVALID_OPERATION = "INVALID_OPERATION"
    GENERATION_MISMATCH = "GENERATION_MISMATCH"
    STRUCTURALLY_CORRUPT = "STRUCTURALLY_CORRUPT"
    UNKNOWN = "UNKNOWN"


def exact_decimal(value: object, *, field_name: str = "value") -> Decimal:
    """Normalize a provider value into exact Decimal via its decimal text form.

    ``Decimal(str(value))`` keeps the decimal text the adapter presented and is
    deterministic for replay. ``float('nan')`` / ``inf`` are rejected.
    """
    if isinstance(value, Decimal):
        dec = value
    else:
        text = str(value)
        try:
            dec = Decimal(text)
        except (InvalidOperation, ValueError) as exc:
            raise ValueError(f"invalid decimal {field_name}: {value!r}") from exc
    if not dec.is_finite():
        raise ValueError(f"non-finite {field_name}: {value!r}")
    return dec


def price_key(value: object) -> Decimal:
    """Validate + normalize a price (must be finite, non-negative)."""
    dec = exact_decimal(value, field_name="price")
    if dec < 0:
        raise ValueError(f"negative price: {dec}")
    return dec


def size_value(value: object) -> Decimal:
    """Validate + normalize a size (finite, >= 0). Zero is legal for deletes."""
    dec = exact_decimal(value, field_name="size")
    if dec < 0:
        raise ValueError(f"negative size: {dec}")
    return dec


@dataclass(frozen=True, slots=True)
class BookLevel:
    """One canonical price level on one side (aggregated MBP level)."""

    price: Decimal
    size: Decimal
    order_count: int | None = None

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "BookLevel":
        return cls(
            price=price_key(row["price"]),
            size=size_value(row.get("size", row.get("volume", 0))),
            order_count=_optional_int(row.get("order_count")),
        )

    def to_row(self) -> dict[str, Any]:
        return {
            "price": float(self.price),
            "size": float(self.size),
            "order_count": self.order_count,
        }

    def canonical(self) -> tuple[str, str]:
        return str(self.price), str(self.size)


def _optional_int(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


@dataclass(frozen=True, slots=True)
class DepthUpdate:
    """One canonical incremental depth event.

    ``operation``/``side``/``price``/``size`` are the authoritative facts.
    ``position`` is advisory provider rank metadata (cross-checked, not the
    identity). ``source``/``source_time_ns``/``received_time_ns`` use the
    existing canonical time/source vocabulary (ns since epoch), never wall
    clock at replay time. ``sequence`` is optional: a provider without a
    usable sequence is supported but the sequence state is reported as
    ``NO_SEQUENCE`` truthfully.
    """

    instrument_id: str
    operation: DepthOperation
    side: DepthSide
    price: Decimal | None = None
    size: Decimal | None = None
    position: int | None = None
    source: str | None = None
    source_time_ns: int | None = None
    received_time_ns: int | None = None
    sequence: int | None = None
    subscription_id: str | None = None
    provider_event_id: str | None = None
    schema_version: str = DEPTH_EVENT_SCHEMA_VERSION
    provenance: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.instrument_id, str) or not self.instrument_id.strip():
            raise ValueError("instrument_id must be a non-empty string")
        if self.operation is DepthOperation.RESET:
            return
        if self.side is None:
            raise ValueError(f"side required for {self.operation}")
        if self.operation in (DepthOperation.INSERT, DepthOperation.UPDATE):
            if self.price is None:
                raise ValueError(f"price required for {self.operation}")
        if self.operation is DepthOperation.DELETE:
            if self.price is None and self.position is None:
                raise ValueError("delete requires price or position")
        if self.operation in (DepthOperation.INSERT, DepthOperation.UPDATE):
            if self.size is None:
                raise ValueError(f"size required for {self.operation}")
        if self.position is not None and (
            isinstance(self.position, bool) or not isinstance(self.position, int) or self.position < 0
        ):
            raise ValueError(f"invalid position: {self.position!r}")

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "instrument_id": self.instrument_id,
            "operation": self.operation.value,
            "schema_version": self.schema_version,
            "side": None if self.side is None else self.side.value,
        }
        if self.price is not None:
            payload["price"] = str(self.price)
        if self.size is not None:
            payload["size"] = str(self.size)
        if self.position is not None:
            payload["position"] = self.position
        if self.source is not None:
            payload["source"] = self.source
        if self.source_time_ns is not None:
            payload["source_time_ns"] = self.source_time_ns
        if self.received_time_ns is not None:
            payload["received_time_ns"] = self.received_time_ns
        if self.sequence is not None:
            payload["sequence"] = self.sequence
        if self.subscription_id is not None:
            payload["subscription_id"] = self.subscription_id
        if self.provider_event_id is not None:
            payload["provider_event_id"] = self.provider_event_id
        if self.provenance:
            payload["provenance"] = dict(self.provenance)
        return payload


def build_depth_update(
    *,
    instrument_id: str,
    operation: str | DepthOperation,
    side: str | DepthSide | None = None,
    price: object | None = None,
    size: object | None = None,
    position: int | None = None,
    source: str | None = None,
    source_time_ns: int | None = None,
    received_time_ns: int | None = None,
    sequence: int | None = None,
    subscription_id: str | None = None,
    provider_event_id: str | None = None,
    provenance: Mapping[str, Any] | None = None,
) -> DepthUpdate:
    """Ergonomic validated constructor (provider-adapter boundary)."""
    op = DepthOperation(operation) if isinstance(operation, str) else operation
    parsed_side = None if side is None else (DepthSide(side) if isinstance(side, str) else side)
    price_dec = None if price is None else price_key(price)
    size_dec = None if size is None else size_value(size)
    if sequence is not None and (isinstance(sequence, bool) or not isinstance(sequence, int)):
        raise ValueError(f"invalid sequence: {sequence!r}")
    if source_time_ns is not None and (isinstance(source_time_ns, bool) or not isinstance(source_time_ns, int)):
        raise ValueError(f"invalid source_time_ns: {source_time_ns!r}")
    if received_time_ns is not None and (
        isinstance(received_time_ns, bool) or not isinstance(received_time_ns, int)
    ):
        raise ValueError(f"invalid received_time_ns: {received_time_ns!r}")
    return DepthUpdate(
        instrument_id=instrument_id,
        operation=op,
        side=parsed_side,
        price=price_dec,
        size=size_dec,
        position=position,
        source=source,
        source_time_ns=source_time_ns,
        received_time_ns=received_time_ns,
        sequence=sequence,
        subscription_id=subscription_id,
        provider_event_id=provider_event_id,
        provenance=provenance or {},
    )


@dataclass(frozen=True, slots=True)
class ApplyResult:
    """Explicit result for one applied operation."""

    outcome: ApplyOutcome
    reason: BookStatusReason
    sequence_state: SequenceState
    book_valid: bool
    book_validity: BookValidity
    generation: int
    update_count: int
    state_changed: bool
    best_bid: Decimal | None = None
    best_ask: Decimal | None = None
    sequence: int | None = None
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "best_ask": None if self.best_ask is None else str(self.best_ask),
            "best_bid": None if self.best_bid is None else str(self.best_bid),
            "book_valid": self.book_valid,
            "book_validity": self.book_validity.value,
            "generation": self.generation,
            "message": self.message,
            "outcome": self.outcome.value,
            "reason": self.reason.value,
            "sequence": self.sequence,
            "sequence_state": self.sequence_state.value,
            "state_changed": self.state_changed,
            "update_count": self.update_count,
        }


def ensure_finite_float(value: float) -> float:
    if not math.isfinite(value):
        raise ValueError(f"non-finite numeric: {value!r}")
    return value


__all__ = [
    "APPLY_OUTCOMES",
    "ApplyOutcome",
    "ApplyResult",
    "BOOK_MODEL_VERSION",
    "BookLevel",
    "BookStatusReason",
    "BookValidity",
    "DEPTH_EVENT_SCHEMA_VERSION",
    "DepthOperation",
    "DepthSide",
    "DepthUpdate",
    "FreshnessStatus",
    "SequenceState",
    "build_depth_update",
    "exact_decimal",
    "price_key",
    "size_value",
]
