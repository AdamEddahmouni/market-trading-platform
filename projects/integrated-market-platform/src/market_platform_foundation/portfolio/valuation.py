"""Asset-aware portfolio valuation engine (G2).

One controlled valuation owner with asset-aware strategies, never an
``if asset_class == ...`` ladder spread across APIs/UI files:

- Equity / ETF:  market_value = quantity x mark (shares).
- Option:        market_value = contracts x premium x multiplier.
- Future:        notional and mark-to-market P&L are kept separate from
                 cash-equity market value; a future position is never valued
                 as ``contracts x full contract notional`` of owned cash.
- Crypto spot:   base-unit quantity x pair price (quote currency).
- Bond:          face/par-aware quantity with an explicit price basis
                 (PAR_PERCENT or CURRENCY_PER_FACE_UNIT); no yield invented.

Missing, stale, wrong-currency, and wrong-instrument marks produce explicit
status — never a fabricated zero value.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Iterable, Mapping

from .canonical import (
    BondPriceBasis,
    MarkDataStatus,
    MarkType,
    PortfolioError,
    PortfolioErrorCode,
    PortfolioPosition,
    PositionValuation,
    ValuationMark,
    ValuationStatus,
    _as_decimal,
)


@dataclass(frozen=True, slots=True)
class ValuationContext:
    """PIT-scoped valuation inputs: marks by instrument, optional reference prices.

    ``as_of_ns`` is the valuation cutoff: a mark whose ``source_time_ns`` is
    after the cutoff is not eligible, preserving point-in-time correctness.
    """

    marks: Mapping[str, ValuationMark] | None = None
    reference_prices: Mapping[str, Decimal] | None = None
    as_of_ns: int | None = None

    def mark_for(self, instrument_id: str) -> ValuationMark | None:
        if self.marks is None:
            return None
        mark = self.marks.get(instrument_id)
        if mark is None:
            return None
        if self.as_of_ns is not None and mark.source_time_ns > self.as_of_ns:
            return None
        return mark

    def reference_for(self, instrument_id: str) -> Decimal | None:
        if self.reference_prices is None:
            return None
        value = self.reference_prices.get(instrument_id)
        if value is None:
            return None
        if self.as_of_ns is not None:
            return value
        return value


def _position_mark(position: PortfolioPosition, mark: ValuationMark | None) -> ValuationMark | None:
    if mark is None:
        return None
    if mark.instrument_id != position.instrument_id:
        raise PortfolioError(
            PortfolioErrorCode.WRONG_INSTRUMENT_MARK,
            "mark instrument does not match position instrument",
            {"mark_instrument_id": mark.instrument_id, "position_instrument_id": position.instrument_id},
        )
    return mark


def _mark_status(mark: ValuationMark | None) -> ValuationStatus:
    if mark is None:
        return ValuationStatus.MISSING_MARK
    if mark.data_status == MarkDataStatus.MISSING:
        return ValuationStatus.MISSING_MARK
    if mark.data_status == MarkDataStatus.STALE:
        return ValuationStatus.STALE
    return ValuationStatus.COMPLETE


def value_position(
    position: PortfolioPosition,
    *,
    mark: ValuationMark | None = None,
    context: ValuationContext | None = None,
) -> PositionValuation:
    """Value one canonical position with its asset-aware rule.

    ``mark`` (preferred) or ``context.marks`` supplies the normalized mark.
    Raises ``PortfolioError(WRONG_CURRENCY_MARK)`` when the mark currency does
    not match the position's native currency, and
    ``PortfolioError(UNSUPPORTED_VALUATION)`` when the identity/kind cannot be
    valued (including reference-only identities that reached the engine
    directly).
    """
    from .admission import admission_result

    resolved = mark if mark is not None else (context.mark_for(position.instrument_id) if context else None)
    resolved = _position_mark(position, resolved)

    admission = admission_result(
        instrument_kind=position.instrument_kind,
        asset_class=position.asset_class,
    )
    if not admission.admitted:
        return PositionValuation(
            market_value_native=None,
            unrealized_pnl_native=None,
            notional_native=None,
            reference_price=None,
            valuation_status=ValuationStatus.UNSUPPORTED,
            mark=resolved,
        )

    if resolved is not None and resolved.currency != position.native_currency:
        raise PortfolioError(
            PortfolioErrorCode.WRONG_CURRENCY_MARK,
            "mark currency does not match position native currency",
            {
                "mark_currency": resolved.currency,
                "native_currency": position.native_currency,
                "instrument_id": position.instrument_id,
            },
        )

    kind = position.instrument_kind
    if kind in {"TRADABLE_SECURITY"}:
        return _value_security(position, resolved)
    if kind == "OPTION_CONTRACT":
        return _value_option(position, resolved)
    if kind == "FUTURE_CONTRACT":
        return _value_future(position, resolved, context)
    if kind == "CRYPTO_PAIR":
        return _value_crypto(position, resolved)
    return PositionValuation(
        market_value_native=None,
        unrealized_pnl_native=None,
        notional_native=None,
        reference_price=None,
        valuation_status=ValuationStatus.UNSUPPORTED,
        mark=resolved,
    )


def _value_security(position: PortfolioPosition, mark: ValuationMark | None) -> PositionValuation:
    status = _mark_status(mark)
    if mark is None:
        return PositionValuation(
            market_value_native=None,
            unrealized_pnl_native=None,
            notional_native=None,
            reference_price=None,
            valuation_status=status,
        )
    market_value = position.quantity * mark.price
    unrealized = _security_unrealized(position, market_value)
    return PositionValuation(
        market_value_native=market_value,
        unrealized_pnl_native=unrealized,
        notional_native=None,
        reference_price=None,
        valuation_status=status,
        mark=mark,
    )


def _security_unrealized(position: PortfolioPosition, market_value: Decimal) -> Decimal | None:
    """unrealized = current market value - remaining cost basis (signed)."""
    if position.cost_basis is None:
        return None
    return market_value - position.cost_basis


def _value_option(position: PortfolioPosition, mark: ValuationMark | None) -> PositionValuation:
    status = _mark_status(mark)
    if mark is None:
        return PositionValuation(
            market_value_native=None,
            unrealized_pnl_native=None,
            notional_native=None,
            reference_price=None,
            valuation_status=status,
        )
    # contracts x premium x multiplier; the multiplier comes from contract
    # identity metadata (never hard-coded to 100).
    market_value = position.quantity * mark.price * position.multiplier
    unrealized = None
    if position.cost_basis is not None:
        unrealized = market_value - position.cost_basis
    return PositionValuation(
        market_value_native=market_value,
        unrealized_pnl_native=unrealized,
        notional_native=None,
        reference_price=None,
        valuation_status=status,
        mark=mark,
    )


def _value_future(
    position: PortfolioPosition,
    mark: ValuationMark | None,
    context: ValuationContext | None,
) -> PositionValuation:
    """Futures are never valued like equities.

    - ``notional_native``: informational contract notional (contracts x
      multiplier x mark) — exposure, not owned cash-equity.
    - mark-to-market P&L uses ``(mark - reference) x multiplier x contracts``
      with the contract's own multiplier and price units.
    - A missing reference price yields UNVALUED/MISSING_MARK rather than a
      false equity-style market value.
    """
    status = _mark_status(mark)
    if mark is None:
        return PositionValuation(
            market_value_native=None,
            unrealized_pnl_native=None,
            notional_native=None,
            reference_price=None,
            valuation_status=status,
        )
    notional = position.quantity * position.multiplier * mark.price
    reference = context.reference_for(position.instrument_id) if context is not None else None
    if reference is None:
        return PositionValuation(
            market_value_native=None,
            unrealized_pnl_native=None,
            notional_native=notional,
            reference_price=None,
            valuation_status=ValuationStatus.MISSING_MARK,
            mark=mark,
        )
    variation_pnl = position.quantity * position.multiplier * (mark.price - reference)
    # market_value_native is intentionally None for futures: the cash-equity
    # concept does not exist. P&L and notional are the futures-native values.
    return PositionValuation(
        market_value_native=None,
        unrealized_pnl_native=variation_pnl,
        notional_native=notional,
        reference_price=reference,
        valuation_status=status,
        mark=mark,
    )


def _value_crypto(position: PortfolioPosition, mark: ValuationMark | None) -> PositionValuation:
    status = _mark_status(mark)
    if mark is None:
        return PositionValuation(
            market_value_native=None,
            unrealized_pnl_native=None,
            notional_native=None,
            reference_price=None,
            valuation_status=status,
        )
    # base-unit quantity x pair price; native currency is the pair quote.
    market_value = position.quantity * mark.price
    unrealized = None
    if position.cost_basis is not None:
        unrealized = market_value - position.cost_basis
    return PositionValuation(
        market_value_native=market_value,
        unrealized_pnl_native=unrealized,
        notional_native=None,
        reference_price=None,
        valuation_status=status,
        mark=mark,
    )


def value_bond_position(
    *,
    face_amount: Decimal,
    price: Decimal,
    price_basis: BondPriceBasis,
    currency: str,
    mark_type: str = "CLEAN_PRICE",
    source: str = "UNKNOWN",
    source_time_ns: int = 0,
    observed_at_ns: int = 0,
    data_status: MarkDataStatus = MarkDataStatus.FRESH,
    accrued_interest: Decimal | None = None,
) -> PositionValuation:
    """Bond valuation with an explicit price basis (G2 §28–29).

    - PAR_PERCENT: ``face x price/100`` is the clean value; accrued interest
      (when supplied) produces the dirty value.
    - CURRENCY_PER_FACE_UNIT: ``face x price`` directly.
    No yield, discounting, or fixed-income pricing engine is built here.
    """
    face = _as_decimal(face_amount, field_name="face_amount")
    price_dec = _as_decimal(price, field_name="price")
    try:
        basis = BondPriceBasis(str(price_basis))
    except ValueError:
        raise PortfolioError(
            PortfolioErrorCode.UNSUPPORTED_VALUATION,
            "bond price basis is required and must be PAR_PERCENT or CURRENCY_PER_FACE_UNIT",
            {"price_basis": str(price_basis)},
        ) from None
    if basis == BondPriceBasis.PAR_PERCENT:
        clean_value = face * price_dec / Decimal("100")
    else:
        clean_value = face * price_dec
    mark = ValuationMark(
        instrument_id="BOND_VALUATION",
        price=price_dec,
        currency=currency,
        mark_type=MarkType(str(mark_type)),
        source=source,
        source_time_ns=source_time_ns,
        observed_at_ns=observed_at_ns,
        data_status=data_status,
    )
    accrued = _as_decimal(accrued_interest, field_name="accrued_interest") if accrued_interest is not None else None
    # Dirty value is reported when accrued interest is explicitly supplied;
    # otherwise it stays unavailable instead of being invented.
    if accrued is not None:
        valuation = PositionValuation(
            market_value_native=clean_value + accrued,
            unrealized_pnl_native=None,
            notional_native=None,
            reference_price=None,
            valuation_status=ValuationStatus.COMPLETE,
            mark=mark,
        )
        return valuation
    return PositionValuation(
        market_value_native=clean_value,
        unrealized_pnl_native=None,
        notional_native=None,
        reference_price=None,
        valuation_status=ValuationStatus.COMPLETE,
        mark=mark,
    )


def value_positions(
    positions: Iterable[PortfolioPosition],
    *,
    marks: Mapping[str, ValuationMark],
    context: ValuationContext | None = None,
) -> tuple[PortfolioPosition, ...]:
    """Value every position and return positions with ``valuation`` attached."""
    resolved_context = context if context is not None else ValuationContext(marks=marks)
    valued: list[PortfolioPosition] = []
    for position in positions:
        valuation = value_position(position, context=resolved_context)
        valued.append(position.with_valuation(valuation))
    return tuple(valued)


__all__ = [
    "ValuationContext",
    "value_bond_position",
    "value_position",
    "value_positions",
]