"""Canonical multi-asset portfolio state model (G2 / BL-0105).

One authoritative, account-scoped, mode-scoped, instrument-keyed portfolio
truth model on top of the XA-01 identity kernel. Equity behavior from the
legacy fill-driven ledger is preserved (``portfolio.ledger`` remains the
parity baseline); this module is the single canonical portfolio owner that
later trading/risk work consumes.

Safety invariants:

- Portfolio state is always scoped by ``PortfolioKey`` (operational account +
  mode). There is no user-global singleton portfolio state.
- Positions are keyed by canonical XA-01 ``instrument_id`` — never by ticker,
  provider symbol, or display symbol alone.
- Position admission fails closed on reference-only identities (continuous
  futures series, family/root, economic commodities, spot references, indexes,
  currencies, FX pairs, and reference-only bonds) via ``portfolio.admission``.
- Cash is held per currency; currencies are never summed without an explicit
  FX conversion through ``portfolio.fx``.
- All financial arithmetic uses ``Decimal``. Float values are only accepted at
  legacy serialization boundaries and converted exactly.
- A valuation never fabricates a price: missing/stale/wrong-currency marks
  produce an explicit valuation status, never a zero fallback.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from threading import RLock
from typing import Any, Mapping

from ..canonical import canonical_bytes, sha256_bytes
from ..operational_identity import OPERATIONAL_MODES

PORTFOLIO_SCHEMA_VERSION = 1


class PortfolioErrorCode(StrEnum):
    INVALID_PORTFOLIO_KEY = "INVALID_PORTFOLIO_KEY"
    INVALID_MODE = "INVALID_MODE"
    INVALID_INSTRUMENT = "INVALID_INSTRUMENT"
    NON_EXECUTABLE_INSTRUMENT = "NON_EXECUTABLE_INSTRUMENT"
    UNKNOWN_INSTRUMENT = "UNKNOWN_INSTRUMENT"
    INVALID_QUANTITY = "INVALID_QUANTITY"
    INVALID_POSITION_ECONOMICS = "INVALID_POSITION_ECONOMICS"
    INVALID_CURRENCY = "INVALID_CURRENCY"
    INVALID_DECIMAL = "INVALID_DECIMAL"
    INVALID_MARK = "INVALID_MARK"
    WRONG_CURRENCY_MARK = "WRONG_CURRENCY_MARK"
    WRONG_INSTRUMENT_MARK = "WRONG_INSTRUMENT_MARK"
    MISSING_FX = "MISSING_FX"
    UNSUPPORTED_VALUATION = "UNSUPPORTED_VALUATION"
    DUPLICATE_INSTRUMENT = "DUPLICATE_INSTRUMENT"


@dataclass(frozen=True, slots=True)
class PortfolioError(Exception):
    code: PortfolioErrorCode
    message: str
    details: Mapping[str, Any]

    def __str__(self) -> str:
        return f"{self.code.value}: {self.message}"


def _as_decimal(value: Any, *, field_name: str = "value") -> Decimal:
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, int) and not isinstance(value, bool):
        result = Decimal(value)
    elif isinstance(value, str):
        try:
            result = Decimal(value)
        except InvalidOperation:
            raise PortfolioError(
                PortfolioErrorCode.INVALID_DECIMAL,
                f"{field_name} is not a valid decimal",
                {field_name: value},
            ) from None
    else:
        raise PortfolioError(
            PortfolioErrorCode.INVALID_DECIMAL,
            f"{field_name} must be a Decimal, int, or decimal string",
            {"field_name": field_name, "value_type": type(value).__name__},
        )
    if not result.is_finite():
        raise PortfolioError(
            PortfolioErrorCode.INVALID_DECIMAL,
            f"{field_name} must be finite",
            {field_name: str(value)},
        )
    return result


@dataclass(frozen=True, slots=True)
class PortfolioKey:
    """Operational scope for portfolio truth: account + mode (+ optional identity).

    The canonical owner of portfolio state is never a user-global singleton.
    ``account_id`` and ``mode`` are the mandatory dimensions; ``broker``,
    ``environment`` and ``portfolio_id`` participate only when the surrounding
    operational identity already requires them.
    """

    account_id: str
    mode: str
    broker: str = "internal.simulation"
    portfolio_id: str | None = None
    environment: str = "local"

    def __post_init__(self) -> None:
        if not self.account_id or not str(self.account_id).strip():
            raise PortfolioError(
                PortfolioErrorCode.INVALID_PORTFOLIO_KEY,
                "account_id is required",
                {},
            )
        mode = str(self.mode).upper()
        if mode not in OPERATIONAL_MODES:
            raise PortfolioError(
                PortfolioErrorCode.INVALID_MODE,
                f"mode must be one of {sorted(OPERATIONAL_MODES)}",
                {"mode": self.mode},
            )
        object.__setattr__(self, "mode", mode)

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "account_id": self.account_id,
            "mode": self.mode,
            "broker": self.broker,
            "environment": self.environment,
        }
        if self.portfolio_id is not None:
            body["portfolio_id"] = self.portfolio_id
        return body

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "PortfolioKey":
        return cls(
            account_id=str(payload["account_id"]),
            mode=str(payload["mode"]),
            broker=str(payload.get("broker", "internal.simulation")),
            portfolio_id=payload.get("portfolio_id"),
            environment=str(payload.get("environment", "local")),
        )


class QuantityUnit(StrEnum):
    """Explicit, non-interchangeable position quantity units."""

    SHARES = "SHARES"          # Equity / ETF
    CONTRACTS = "CONTRACTS"    # Options / Futures (multiplier applied separately)
    BASE_UNITS = "BASE_UNITS"  # Crypto spot: units of the base asset
    FACE_VALUE = "FACE_VALUE"  # Bonds: par / face units


class MarkType(StrEnum):
    LAST = "LAST"
    MIDPOINT = "MIDPOINT"
    CLOSE = "CLOSE"
    SETTLEMENT = "SETTLEMENT"
    PROVIDER_MARK = "PROVIDER_MARK"
    CLEAN_PRICE = "CLEAN_PRICE"
    DIRTY_PRICE = "DIRTY_PRICE"


class MarkDataStatus(StrEnum):
    FRESH = "FRESH"
    STALE = "STALE"
    MISSING = "MISSING"


class ValuationStatus(StrEnum):
    """Explicit portfolio/position valuation completeness."""

    COMPLETE = "COMPLETE"            # Native values present and current
    PARTIAL = "PARTIAL"              # Some native values present; aggregation incomplete
    UNVALUED = "UNVALUED"            # No usable mark/FX; nothing valued
    STALE = "STALE"                  # Valued with stale marks/FX
    MISSING_MARK = "MISSING_MARK"    # Mark absent; no value fabricated
    MISSING_FX = "MISSING_FX"        # Native value present; base-currency conversion unavailable
    UNSUPPORTED = "UNSUPPORTED"      # Valuation not supported for this identity/state


class BondPriceBasis(StrEnum):
    """Explicit bond price interpretation."""

    PAR_PERCENT = "PAR_PERCENT"                 # e.g. 98.50 means 98.50 % of par
    CURRENCY_PER_FACE_UNIT = "CURRENCY_PER_FACE_UNIT"


@dataclass(frozen=True, slots=True)
class CashBalance:
    """One currency's cash state. ``settled`` is the minimum required truth."""

    currency: str
    settled: Decimal
    unsettled: Decimal | None = None
    reserved: Decimal | None = None
    available: Decimal | None = None

    def __post_init__(self) -> None:
        if not self.currency or not str(self.currency).strip():
            raise PortfolioError(PortfolioErrorCode.INVALID_CURRENCY, "currency required", {})
        object.__setattr__(self, "currency", str(self.currency).upper())
        object.__setattr__(self, "settled", _as_decimal(self.settled, field_name="settled"))

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {"currency": self.currency, "settled": format(self.settled, "f")}
        if self.unsettled is not None:
            body["unsettled"] = format(self.unsettled, "f")
        if self.reserved is not None:
            body["reserved"] = format(self.reserved, "f")
        if self.available is not None:
            body["available"] = format(self.available, "f")
        return body

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "CashBalance":
        return cls(
            currency=str(payload["currency"]),
            settled=_as_decimal(payload["settled"], field_name="settled"),
            unsettled=_as_decimal(payload["unsettled"], field_name="unsettled") if payload.get("unsettled") is not None else None,
            reserved=_as_decimal(payload["reserved"], field_name="reserved") if payload.get("reserved") is not None else None,
            available=_as_decimal(payload["available"], field_name="available") if payload.get("available") is not None else None,
        )


@dataclass(frozen=True, slots=True)
class ValuationMark:
    """Normalized portfolio valuation input.

    The portfolio never fetches its own data; it consumes normalized marks
    from existing market-data/provider boundaries. ``price`` is in
    ``currency``; ``source`` / ``source_time_ns`` / ``observed_at_ns`` /
    ``data_status`` preserve provenance so values are never temporally opaque.
    """

    instrument_id: str
    price: Decimal
    currency: str
    mark_type: MarkType = MarkType.LAST
    source: str = "UNKNOWN"
    source_time_ns: int = 0
    observed_at_ns: int = 0
    data_status: MarkDataStatus = MarkDataStatus.FRESH

    def __post_init__(self) -> None:
        if not self.instrument_id or not str(self.instrument_id).strip():
            raise PortfolioError(PortfolioErrorCode.INVALID_MARK, "instrument_id required", {})
        if not self.currency or not str(self.currency).strip():
            raise PortfolioError(PortfolioErrorCode.INVALID_MARK, "currency required", {})
        object.__setattr__(self, "currency", str(self.currency).upper())
        object.__setattr__(self, "price", _as_decimal(self.price, field_name="price"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "instrument_id": self.instrument_id,
            "price": format(self.price, "f"),
            "currency": self.currency,
            "mark_type": self.mark_type.value,
            "source": self.source,
            "source_time_ns": self.source_time_ns,
            "observed_at_ns": self.observed_at_ns,
            "data_status": self.data_status.value,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ValuationMark":
        return cls(
            instrument_id=str(payload["instrument_id"]),
            price=_as_decimal(payload["price"], field_name="price"),
            currency=str(payload["currency"]),
            mark_type=MarkType(str(payload.get("mark_type", MarkType.LAST.value))),
            source=str(payload.get("source", "UNKNOWN")),
            source_time_ns=int(payload.get("source_time_ns", 0)),
            observed_at_ns=int(payload.get("observed_at_ns", 0)),
            data_status=MarkDataStatus(str(payload.get("data_status", MarkDataStatus.FRESH.value))),
        )


@dataclass(frozen=True, slots=True)
class PositionValuation:
    """Asset-aware valuation result attached to a canonical position."""

    market_value_native: Decimal | None
    unrealized_pnl_native: Decimal | None
    notional_native: Decimal | None
    reference_price: Decimal | None
    valuation_status: ValuationStatus
    mark: ValuationMark | None = None

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "valuation_status": self.valuation_status.value,
        }
        for key, value in (
            ("market_value_native", self.market_value_native),
            ("unrealized_pnl_native", self.unrealized_pnl_native),
            ("notional_native", self.notional_native),
            ("reference_price", self.reference_price),
        ):
            if value is not None:
                body[key] = format(value, "f")
        if self.mark is not None:
            body["mark"] = self.mark.to_dict()
        return body

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "PositionValuation":
        mark_payload = payload.get("mark")
        return cls(
            market_value_native=_as_decimal(payload["market_value_native"], field_name="market_value_native")
            if payload.get("market_value_native") is not None else None,
            unrealized_pnl_native=_as_decimal(payload["unrealized_pnl_native"], field_name="unrealized_pnl_native")
            if payload.get("unrealized_pnl_native") is not None else None,
            notional_native=_as_decimal(payload["notional_native"], field_name="notional_native")
            if payload.get("notional_native") is not None else None,
            reference_price=_as_decimal(payload["reference_price"], field_name="reference_price")
            if payload.get("reference_price") is not None else None,
            valuation_status=ValuationStatus(str(payload["valuation_status"])),
            mark=ValuationMark.from_dict(mark_payload) if isinstance(mark_payload, Mapping) else None,
        )


@dataclass(frozen=True, slots=True)
class PortfolioPosition:
    """Canonical position: instrument-keyed with explicit units and currency.

    ``quantity`` uses ``quantity_unit`` (SHARES / CONTRACTS / BASE_UNITS /
    FACE_VALUE). ``multiplier`` is separate from quantity so options and
    futures never fall back to equity-style arithmetic. ``realized_pnl_native``
    is always present (zero when unknown-but-tracked); the remaining valuation
    fields are populated by the valuation engine and can legitimately be None
    with an explicit ``valuation_status``.
    """

    instrument_id: str
    asset_class: str
    instrument_kind: str
    quantity: Decimal
    quantity_unit: QuantityUnit
    native_currency: str
    multiplier: Decimal = Decimal("1")
    average_cost: Decimal | None = None
    cost_basis: Decimal | None = None
    realized_pnl_native: Decimal = Decimal("0")
    price_basis: BondPriceBasis | None = None
    source_time_ns: int = 0
    observed_at_ns: int = 0
    data_status: str = "FRESH"
    valuation: PositionValuation | None = None

    def __post_init__(self) -> None:
        if not self.instrument_id or not str(self.instrument_id).strip():
            raise PortfolioError(PortfolioErrorCode.INVALID_INSTRUMENT, "instrument_id required", {})
        if not self.native_currency or not str(self.native_currency).strip():
            raise PortfolioError(PortfolioErrorCode.INVALID_CURRENCY, "native_currency required", {})
        object.__setattr__(self, "native_currency", str(self.native_currency).upper())
        object.__setattr__(self, "quantity", _as_decimal(self.quantity, field_name="quantity"))
        object.__setattr__(self, "multiplier", _as_decimal(self.multiplier, field_name="multiplier"))
        if self.average_cost is not None:
            object.__setattr__(self, "average_cost", _as_decimal(self.average_cost, field_name="average_cost"))
        if self.cost_basis is not None:
            object.__setattr__(self, "cost_basis", _as_decimal(self.cost_basis, field_name="cost_basis"))
        object.__setattr__(
            self,
            "realized_pnl_native",
            _as_decimal(self.realized_pnl_native, field_name="realized_pnl_native"),
        )

    @property
    def signed_quantity(self) -> Decimal:
        return self.quantity

    def with_valuation(self, valuation: PositionValuation) -> "PortfolioPosition":
        return replace(self, valuation=valuation)

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "instrument_id": self.instrument_id,
            "asset_class": self.asset_class,
            "instrument_kind": self.instrument_kind,
            "quantity": format(self.quantity, "f"),
            "quantity_unit": self.quantity_unit.value,
            "native_currency": self.native_currency,
            "multiplier": format(self.multiplier, "f"),
            "realized_pnl_native": format(self.realized_pnl_native, "f"),
            "source_time_ns": self.source_time_ns,
            "observed_at_ns": self.observed_at_ns,
            "data_status": self.data_status,
        }
        for key, value in (
            ("average_cost", self.average_cost),
            ("cost_basis", self.cost_basis),
        ):
            if value is not None:
                body[key] = format(value, "f")
        if self.price_basis is not None:
            body["price_basis"] = self.price_basis.value
        if self.valuation is not None:
            body["valuation"] = self.valuation.to_dict()
        return body

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "PortfolioPosition":
        valuation_payload = payload.get("valuation")
        price_basis_raw = payload.get("price_basis")
        return cls(
            instrument_id=str(payload["instrument_id"]),
            asset_class=str(payload["asset_class"]),
            instrument_kind=str(payload["instrument_kind"]),
            quantity=_as_decimal(payload["quantity"], field_name="quantity"),
            quantity_unit=QuantityUnit(str(payload["quantity_unit"])),
            native_currency=str(payload["native_currency"]),
            multiplier=_as_decimal(payload.get("multiplier", "1"), field_name="multiplier"),
            average_cost=_as_decimal(payload["average_cost"], field_name="average_cost")
            if payload.get("average_cost") is not None else None,
            cost_basis=_as_decimal(payload["cost_basis"], field_name="cost_basis")
            if payload.get("cost_basis") is not None else None,
            realized_pnl_native=_as_decimal(payload.get("realized_pnl_native", "0"), field_name="realized_pnl_native"),
            price_basis=BondPriceBasis(str(price_basis_raw)) if price_basis_raw is not None else None,
            source_time_ns=int(payload.get("source_time_ns", 0)),
            observed_at_ns=int(payload.get("observed_at_ns", 0)),
            data_status=str(payload.get("data_status", "FRESH")),
            valuation=PositionValuation.from_dict(valuation_payload) if isinstance(valuation_payload, Mapping) else None,
        )


@dataclass(frozen=True, slots=True)
class PortfolioSnapshot:
    """Deterministic, serializable point-in-time portfolio truth.

    ``valuation_status`` is COMPLETE only when every native value is present
    and, where a base currency is declared, every required conversion exists.
    A snapshot may legitimately contain correct positions and native values
    with a PARTIAL base-currency aggregation; that is never labeled COMPLETE.
    """

    key: PortfolioKey
    base_currency: str | None
    cash_balances: tuple[CashBalance, ...]
    positions: tuple[PortfolioPosition, ...]
    native_totals: dict[str, Decimal]
    base_currency_totals: dict[str, Decimal]
    valuation_status: ValuationStatus
    source_time_ns: int = 0
    observed_at_ns: int = 0
    provider: str = "INTERNAL"
    schema_version: int = PORTFOLIO_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "key": self.key.to_dict(),
            "base_currency": self.base_currency,
            "cash_balances": [balance.to_dict() for balance in self.cash_balances],
            "positions": [position.to_dict() for position in self.positions],
            "native_totals": {currency: format(value, "f") for currency, value in sorted(self.native_totals.items())},
            "base_currency_totals": {
                currency: format(value, "f") for currency, value in sorted(self.base_currency_totals.items())
            },
            "valuation_status": self.valuation_status.value,
            "source_time_ns": self.source_time_ns,
            "observed_at_ns": self.observed_at_ns,
            "provider": self.provider,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "PortfolioSnapshot":
        return cls(
            key=PortfolioKey.from_dict(payload["key"]),
            base_currency=payload.get("base_currency"),
            cash_balances=tuple(
                CashBalance.from_dict(row) for row in payload.get("cash_balances", [])
            ),
            positions=tuple(PortfolioPosition.from_dict(row) for row in payload.get("positions", [])),
            native_totals={
                str(currency): _as_decimal(value, field_name="native_totals")
                for currency, value in payload.get("native_totals", {}).items()
            },
            base_currency_totals={
                str(currency): _as_decimal(value, field_name="base_currency_totals")
                for currency, value in payload.get("base_currency_totals", {}).items()
            },
            valuation_status=ValuationStatus(str(payload.get("valuation_status", ValuationStatus.UNVALUED.value))),
            source_time_ns=int(payload.get("source_time_ns", 0)),
            observed_at_ns=int(payload.get("observed_at_ns", 0)),
            provider=str(payload.get("provider", "INTERNAL")),
            schema_version=int(payload.get("schema_version", PORTFOLIO_SCHEMA_VERSION)),
        )


@dataclass(frozen=True, slots=True)
class PositionInput:
    """Canonical position input accepted at the controlled mutation boundary.

    The mutation boundary is the only way canonical portfolio state changes:
    ``apply_position_input`` (fill/adjustment derived state),
    ``apply_snapshot`` (provider/broker snapshots), and ``apply_cash``
    (cash ledger). No independent caller mutates portfolio truth directly.
    """

    instrument_id: str
    asset_class: str
    instrument_kind: str
    quantity: Decimal
    quantity_unit: QuantityUnit
    native_currency: str
    multiplier: Decimal = Decimal("1")
    average_cost: Decimal | None = None
    cost_basis: Decimal | None = None
    realized_pnl_native: Decimal = Decimal("0")
    price_basis: BondPriceBasis | None = None
    source_time_ns: int = 0
    observed_at_ns: int = 0
    data_status: str = "FRESH"

    def __post_init__(self) -> None:
        # Validate eagerly so a bad input can never reach the store.
        PortfolioPosition(
            instrument_id=self.instrument_id,
            asset_class=self.asset_class,
            instrument_kind=self.instrument_kind,
            quantity=self.quantity,
            quantity_unit=self.quantity_unit,
            native_currency=self.native_currency,
            multiplier=self.multiplier,
            average_cost=self.average_cost,
            cost_basis=self.cost_basis,
            realized_pnl_native=self.realized_pnl_native,
            price_basis=self.price_basis,
            source_time_ns=self.source_time_ns,
            observed_at_ns=self.observed_at_ns,
            data_status=self.data_status,
        )

    def to_dict(self) -> dict[str, Any]:
        return PortfolioPosition(
            instrument_id=self.instrument_id,
            asset_class=self.asset_class,
            instrument_kind=self.instrument_kind,
            quantity=self.quantity,
            quantity_unit=self.quantity_unit,
            native_currency=self.native_currency,
            multiplier=self.multiplier,
            average_cost=self.average_cost,
            cost_basis=self.cost_basis,
            realized_pnl_native=self.realized_pnl_native,
            price_basis=self.price_basis,
            source_time_ns=self.source_time_ns,
            observed_at_ns=self.observed_at_ns,
            data_status=self.data_status,
        ).to_dict()

    @classmethod
    def from_position_dict(cls, payload: Mapping[str, Any]) -> "PositionInput":
        return cls(
            instrument_id=str(payload["instrument_id"]),
            asset_class=str(payload["asset_class"]),
            instrument_kind=str(payload["instrument_kind"]),
            quantity=_as_decimal(payload["quantity"], field_name="quantity"),
            quantity_unit=QuantityUnit(str(payload["quantity_unit"])),
            native_currency=str(payload["native_currency"]),
            multiplier=_as_decimal(payload.get("multiplier", "1"), field_name="multiplier"),
            average_cost=_as_decimal(payload["average_cost"], field_name="average_cost")
            if payload.get("average_cost") is not None else None,
            cost_basis=_as_decimal(payload["cost_basis"], field_name="cost_basis")
            if payload.get("cost_basis") is not None else None,
            realized_pnl_native=_as_decimal(payload.get("realized_pnl_native", "0"), field_name="realized_pnl_native"),
            price_basis=BondPriceBasis(str(payload["price_basis"])) if payload.get("price_basis") is not None else None,
            source_time_ns=int(payload.get("source_time_ns", 0)),
            observed_at_ns=int(payload.get("observed_at_ns", 0)),
            data_status=str(payload.get("data_status", "FRESH")),
        )


class CanonicalPortfolio:
    """In-memory canonical portfolio store (one authoritative owner).

    Thread-safety mirrors the repository's account-scoped locking pattern:
    an ``RLock`` guards this store so one account's refresh cannot corrupt
    another's. A caller with multiple accounts must use one store per
    ``PortfolioKey`` (or per account) and never share a single global dict.
    """

    def __init__(self, key: PortfolioKey) -> None:
        self.key = key
        self._lock = RLock()
        self._positions: dict[str, PortfolioPosition] = {}
        self._cash: dict[str, CashBalance] = {}
        self._marks: dict[str, ValuationMark] = {}
        self._source_time_ns: int = 0
        self._observed_at_ns: int = 0
        self._provider: str = "INTERNAL"

    @property
    def positions(self) -> dict[str, PortfolioPosition]:
        with self._lock:
            return dict(self._positions)

    @property
    def cash_balances(self) -> tuple[CashBalance, ...]:
        with self._lock:
            return tuple(sorted(self._cash.values(), key=lambda row: row.currency))

    def upsert_position(self, position_input: PositionInput) -> PortfolioPosition:
        """Controlled mutation boundary: admit and store one canonical position.

        Admission is enforced by ``portfolio.admission.assert_position_admissible``
        against the supplied identity facts; a reference-only identity is
        rejected before any store mutation. Zero quantities are removed
        deterministically (see module docs for zero-position semantics).
        """
        from .admission import assert_position_admissible
        from .instrument_economics import assert_derivative_position_economics

        assert_position_admissible(
            instrument_kind=position_input.instrument_kind,
            asset_class=position_input.asset_class,
        )
        # G4 Invariant 10: derivative positions require explicit contract
        # economics (CONTRACTS quantity unit + positive multiplier) — a
        # silent multiplier=1 fallback for an option/future is never admitted.
        assert_derivative_position_economics(
            instrument_kind=position_input.instrument_kind,
            quantity_unit=position_input.quantity_unit,
            multiplier=position_input.multiplier,
        )
        position = PortfolioPosition(
            instrument_id=position_input.instrument_id,
            asset_class=position_input.asset_class,
            instrument_kind=position_input.instrument_kind,
            quantity=position_input.quantity,
            quantity_unit=position_input.quantity_unit,
            native_currency=position_input.native_currency,
            multiplier=position_input.multiplier,
            average_cost=position_input.average_cost,
            cost_basis=position_input.cost_basis,
            realized_pnl_native=position_input.realized_pnl_native,
            price_basis=position_input.price_basis,
            source_time_ns=position_input.source_time_ns,
            observed_at_ns=position_input.observed_at_ns,
            data_status=position_input.data_status,
        )
        with self._lock:
            if position.quantity == 0:
                self._positions.pop(position.instrument_id, None)
            else:
                self._positions[position.instrument_id] = position
            self._source_time_ns = max(self._source_time_ns, position.source_time_ns)
            self._observed_at_ns = max(self._observed_at_ns, position.observed_at_ns)
            return self._positions.get(position.instrument_id, position)

    def get_position(self, instrument_id: str) -> PortfolioPosition | None:
        with self._lock:
            return self._positions.get(instrument_id)

    def set_cash(self, balance: CashBalance) -> None:
        with self._lock:
            self._cash[balance.currency] = balance

    def apply_cash(self, currency: str, amount: Decimal, *, source_time_ns: int = 0) -> CashBalance:
        """Add ``amount`` to a currency's settled cash (signed delta)."""
        currency = str(currency).upper()
        amount = _as_decimal(amount, field_name="amount")
        with self._lock:
            current = self._cash.get(currency)
            settled = current.settled + amount if current is not None else amount
            balance = CashBalance(currency=currency, settled=settled)
            self._cash[currency] = balance
            self._source_time_ns = max(self._source_time_ns, source_time_ns)
            return balance

    def apply_mark(self, mark: ValuationMark) -> None:
        with self._lock:
            self._marks[mark.instrument_id] = mark
            self._source_time_ns = max(self._source_time_ns, mark.source_time_ns)
            self._observed_at_ns = max(self._observed_at_ns, mark.observed_at_ns)

    def get_mark(self, instrument_id: str) -> ValuationMark | None:
        with self._lock:
            return self._marks.get(instrument_id)

    def apply_snapshot(
        self,
        snapshot: PortfolioSnapshot,
        *,
        overwrite_missing_positions: bool = True,
    ) -> None:
        """Controlled mutation boundary: provider/broker snapshot ingestion.

        Positions are merged by canonical instrument_id. A provider snapshot
        never silently overwrites unrelated account/mode state: the snapshot's
        ``key`` must match this store's key, and only positions present in the
        snapshot are touched. Unknown rows must be classified before this call
        (see ``portfolio.provider_normalization``) — they are never guessed
        into equity.
        """
        if snapshot.key != self.key:
            raise PortfolioError(
                PortfolioErrorCode.INVALID_PORTFOLIO_KEY,
                "snapshot key does not match portfolio store key",
                {"snapshot_key": snapshot.key.to_dict(), "store_key": self.key.to_dict()},
            )
        with self._lock:
            for balance in snapshot.cash_balances:
                self._cash[balance.currency] = balance
            if overwrite_missing_positions:
                incoming_ids = {position.instrument_id for position in snapshot.positions}
                for instrument_id in list(self._positions):
                    if instrument_id not in incoming_ids:
                        self._positions.pop(instrument_id, None)
            for position in snapshot.positions:
                if position.quantity == 0:
                    self._positions.pop(position.instrument_id, None)
                else:
                    self._positions[position.instrument_id] = position
            self._source_time_ns = max(self._source_time_ns, snapshot.source_time_ns)
            self._observed_at_ns = max(self._observed_at_ns, snapshot.observed_at_ns)

    def apply_adjustment(self, position_input: PositionInput) -> PortfolioPosition:
        """Controlled mutation boundary: explicit operator/reconciliation adjustment."""
        return self.upsert_position(position_input)

    def build_snapshot(
        self,
        *,
        base_currency: str | None = None,
        source_time_ns: int | None = None,
        observed_at_ns: int | None = None,
        provider: str = "INTERNAL",
    ) -> PortfolioSnapshot:
        """Derive a deterministic snapshot with native and (optional) base totals.

        Base-currency aggregation is performed through ``portfolio.fx`` and
        requires explicit FX facts supplied via ``set_fx_facts``; without them
        the snapshot reports PARTIAL / MISSING_FX instead of inventing 1:1.
        """
        from .fx import aggregate_to_base
        from .valuation import ValuationContext, value_positions

        with self._lock:
            positions = tuple(
                self._positions[instrument_id]
                for instrument_id in sorted(self._positions)
            )
            # Always value positions (empty marks when none stored) so a
            # missing mark yields an explicit MISSING_MARK status instead of a
            # silently unvalued position.
            positions = value_positions(
                positions,
                marks=dict(self._marks),
                context=ValuationContext(marks=dict(self._marks)),
            )
            cash_balances = tuple(sorted(self._cash.values(), key=lambda row: row.currency))
            native_totals = _native_totals(positions, cash_balances)
            source = source_time_ns if source_time_ns is not None else self._source_time_ns
            observed = observed_at_ns if observed_at_ns is not None else self._observed_at_ns
            position_status = _status_without_base(positions)
            if base_currency is None:
                base_totals: dict[str, Decimal] = {}
                valuation_status = position_status
            else:
                base_totals, base_status = aggregate_to_base(
                    positions=positions,
                    cash_balances=cash_balances,
                    native_totals=native_totals,
                    base_currency=base_currency,
                    fx_facts=dict(self._fx_facts()),
                )
                valuation_status = _merge_status(position_status, base_status)
            return PortfolioSnapshot(
                key=self.key,
                base_currency=base_currency,
                cash_balances=cash_balances,
                positions=positions,
                native_totals=native_totals,
                base_currency_totals=base_totals,
                valuation_status=valuation_status,
                source_time_ns=source,
                observed_at_ns=observed,
                provider=provider,
            )

    def set_fx_facts(self, facts: "FxFactsBundle") -> None:
        from .fx import FxFactsBundle

        if not isinstance(facts, FxFactsBundle):
            raise TypeError("expected FxFactsBundle")
        self._fx_bundle = facts

    def _fx_facts(self) -> dict[str, "FxFacts"]:
        bundle = getattr(self, "_fx_bundle", None)
        if bundle is None:
            return {}
        return dict(bundle.facts)


def _native_totals(
    positions: tuple[PortfolioPosition, ...],
    cash_balances: tuple[CashBalance, ...],
) -> dict[str, Decimal]:
    totals: dict[str, Decimal] = {}
    for balance in cash_balances:
        totals[balance.currency] = totals.get(balance.currency, Decimal("0")) + balance.settled
    for position in positions:
        valuation = position.valuation
        if valuation is None or valuation.market_value_native is None:
            continue
        currency = position.native_currency
        totals[currency] = totals.get(currency, Decimal("0")) + valuation.market_value_native
    return {currency: totals[currency] for currency in sorted(totals)}


def _status_without_base(positions: tuple[PortfolioPosition, ...]) -> ValuationStatus:
    if not positions:
        return ValuationStatus.COMPLETE
    statuses = [position.valuation.valuation_status for position in positions if position.valuation is not None]
    if not statuses:
        return ValuationStatus.UNVALUED
    return _merge_status(*statuses)


def _merge_status(*statuses: ValuationStatus) -> ValuationStatus:
    """Merge valuation statuses worst-first (fail-safe, deterministic)."""
    if not statuses:
        return ValuationStatus.COMPLETE
    if any(status in {ValuationStatus.MISSING_MARK, ValuationStatus.MISSING_FX, ValuationStatus.UNSUPPORTED} for status in statuses):
        for status in (ValuationStatus.MISSING_MARK, ValuationStatus.MISSING_FX, ValuationStatus.UNSUPPORTED):
            if status in statuses:
                return status
    if ValuationStatus.STALE in statuses:
        return ValuationStatus.STALE
    if ValuationStatus.UNVALUED in statuses:
        return ValuationStatus.UNVALUED
    if ValuationStatus.PARTIAL in statuses:
        return ValuationStatus.PARTIAL
    return ValuationStatus.COMPLETE


def portfolio_identity_hash(snapshot: PortfolioSnapshot) -> str:
    """Deterministic identity hash for a serialized snapshot (replay/recovery)."""
    return sha256_bytes(canonical_bytes(snapshot.to_dict()))


__all__ = [
    "BondPriceBasis",
    "CanonicalPortfolio",
    "CashBalance",
    "MarkDataStatus",
    "MarkType",
    "PORTFOLIO_SCHEMA_VERSION",
    "PortfolioError",
    "PortfolioErrorCode",
    "PortfolioKey",
    "PortfolioPosition",
    "PortfolioSnapshot",
    "PositionInput",
    "PositionValuation",
    "QuantityUnit",
    "ValuationMark",
    "ValuationStatus",
    "portfolio_identity_hash",
]