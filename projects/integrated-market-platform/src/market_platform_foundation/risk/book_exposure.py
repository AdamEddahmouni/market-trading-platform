"""Read-only book exposure aggregation and limit utilization.

Consumes G2 canonical position state and G4 instrument economics. This is not
a second pre-trade engine, does not mutate the book, does not submit orders,
and does not automate Live portfolios. Missing or stale marks are excluded
from totals (never zero-filled). Mixed currencies are not summed 1:1.
Futures contribute economic notional via ``future_exposure``, never
cash-equity market value.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Mapping

from ..portfolio.accounting import (
    AccountingError,
    exact_decimal,
    equity_notional,
    future_exposure,
    market_value_by_kind,
    option_premium,
)
from ..portfolio.canonical import (
    CanonicalPortfolio,
    MarkDataStatus,
    PortfolioPosition,
    ValuationMark,
)

BOOK_EXPOSURE_VERSION = "canonical-book-exposure-v1"

EQUITY_KINDS = frozenset({"TRADABLE_SECURITY", "ETF_FUND"})
OPTION_KIND = "OPTION_CONTRACT"
FUTURE_KIND = "FUTURE_CONTRACT"
CRYPTO_KIND = "CRYPTO_PAIR"


class BookExposureStatus(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    FAIL_CLOSED = "FAIL_CLOSED"


class BookExposureReason(StrEnum):
    MISSING_MARK = "MISSING_MARK"
    STALE_MARK = "STALE_MARK"
    MIXED_CURRENCY_NO_FX = "MIXED_CURRENCY_NO_FX"
    UNSUPPORTED_EXPOSURE_MODEL = "UNSUPPORTED_EXPOSURE_MODEL"
    GROSS_EXPOSURE_LIMIT = "GROSS_EXPOSURE_LIMIT"
    NET_EXPOSURE_LIMIT = "NET_EXPOSURE_LIMIT"
    INSTRUMENT_CONCENTRATION = "INSTRUMENT_CONCENTRATION"
    INCOMPLETE_EXPOSURE = "INCOMPLETE_EXPOSURE"


@dataclass(frozen=True, slots=True)
class BookLimitPolicy:
    """Explicit book-level limits. Absence of a field means that cap is not applied."""

    currency: str = "USD"
    max_gross_exposure: Decimal | None = None
    max_net_exposure: Decimal | None = None
    max_instrument_concentration_fraction: Decimal | None = None

    def __post_init__(self) -> None:
        currency = str(self.currency).strip().upper()
        if len(currency) != 3:
            raise ValueError("BOOK_LIMIT_CURRENCY_INVALID")
        object.__setattr__(self, "currency", currency)
        for name in ("max_gross_exposure", "max_net_exposure"):
            value = getattr(self, name)
            if value is None:
                continue
            amount = exact_decimal(value, field_name=name)
            if amount < 0:
                raise ValueError(f"{name.upper()}_INVALID")
            object.__setattr__(self, name, amount)
        fraction = self.max_instrument_concentration_fraction
        if fraction is not None:
            parsed = exact_decimal(fraction, field_name="max_instrument_concentration_fraction")
            if parsed <= 0 or parsed > 1:
                raise ValueError("MAX_INSTRUMENT_CONCENTRATION_FRACTION_INVALID")
            object.__setattr__(self, "max_instrument_concentration_fraction", parsed)


@dataclass(frozen=True, slots=True)
class AssetClassExposure:
    gross_exposure: Decimal
    net_exposure: Decimal


@dataclass(frozen=True, slots=True)
class PositionExposureRow:
    instrument_id: str
    asset_class: str
    instrument_kind: str
    currency: str
    signed_exposure: Decimal | None
    gross_exposure: Decimal | None
    cash_market_value: Decimal | None
    status: str
    reason_codes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class BookExposureReport:
    """Observational book exposure. Not an order, proposal, or execution grant."""

    account_id: str
    mode: str
    currency: str | None
    status: str
    gross_exposure: Decimal | None
    net_exposure: Decimal | None
    positions: tuple[PositionExposureRow, ...]
    by_asset_class: Mapping[str, AssetClassExposure] = field(default_factory=dict)
    reason_codes: tuple[str, ...] = ()
    limit_breaches: tuple[str, ...] = ()
    concentrated_instrument_ids: tuple[str, ...] = ()
    within_limits: bool = True
    schema_version: str = BOOK_EXPOSURE_VERSION

    @property
    def implementation_version(self) -> str:
        return BOOK_EXPOSURE_VERSION


def _signed_economic_exposure(
    position: PortfolioPosition, mark: ValuationMark
) -> Decimal | None:
    kind = str(position.instrument_kind).upper()
    price = mark.price
    quantity = position.quantity
    multiplier = position.multiplier
    if kind in EQUITY_KINDS or kind == CRYPTO_KIND:
        return equity_notional(quantity, price)
    if kind == OPTION_KIND:
        return option_premium(quantity, price, multiplier)
    if kind == FUTURE_KIND:
        return future_exposure(quantity, multiplier, price)
    return None


def _cash_market_value(position: PortfolioPosition, mark: ValuationMark) -> Decimal | None:
    return market_value_by_kind(
        instrument_kind=position.instrument_kind,
        quantity=position.quantity,
        price=mark.price,
        multiplier=position.multiplier,
    )


def _row_for_position(
    position: PortfolioPosition, mark: ValuationMark | None
) -> PositionExposureRow:
    if mark is None:
        return PositionExposureRow(
            instrument_id=position.instrument_id,
            asset_class=position.asset_class,
            instrument_kind=position.instrument_kind,
            currency=position.native_currency,
            signed_exposure=None,
            gross_exposure=None,
            cash_market_value=None,
            status=BookExposureStatus.PARTIAL.value,
            reason_codes=(BookExposureReason.MISSING_MARK.value,),
        )
    if mark.data_status == MarkDataStatus.MISSING:
        return PositionExposureRow(
            instrument_id=position.instrument_id,
            asset_class=position.asset_class,
            instrument_kind=position.instrument_kind,
            currency=position.native_currency,
            signed_exposure=None,
            gross_exposure=None,
            cash_market_value=None,
            status=BookExposureStatus.PARTIAL.value,
            reason_codes=(BookExposureReason.MISSING_MARK.value,),
        )
    if mark.data_status == MarkDataStatus.STALE:
        return PositionExposureRow(
            instrument_id=position.instrument_id,
            asset_class=position.asset_class,
            instrument_kind=position.instrument_kind,
            currency=position.native_currency,
            signed_exposure=None,
            gross_exposure=None,
            cash_market_value=None,
            status=BookExposureStatus.PARTIAL.value,
            reason_codes=(BookExposureReason.STALE_MARK.value,),
        )
    signed = _signed_economic_exposure(position, mark)
    if signed is None:
        return PositionExposureRow(
            instrument_id=position.instrument_id,
            asset_class=position.asset_class,
            instrument_kind=position.instrument_kind,
            currency=position.native_currency,
            signed_exposure=None,
            gross_exposure=None,
            cash_market_value=None,
            status=BookExposureStatus.FAIL_CLOSED.value,
            reason_codes=(BookExposureReason.UNSUPPORTED_EXPOSURE_MODEL.value,),
        )
    try:
        cash_value = _cash_market_value(position, mark)
    except AccountingError:
        cash_value = None
    return PositionExposureRow(
        instrument_id=position.instrument_id,
        asset_class=position.asset_class,
        instrument_kind=position.instrument_kind,
        currency=str(position.native_currency).upper(),
        signed_exposure=signed,
        gross_exposure=abs(signed),
        cash_market_value=cash_value,
        status=BookExposureStatus.COMPLETE.value,
        reason_codes=(),
    )


def _apply_limits(
    *,
    policy: BookLimitPolicy | None,
    status: str,
    gross: Decimal | None,
    net: Decimal | None,
    rows: tuple[PositionExposureRow, ...],
) -> tuple[bool, tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    breaches: list[str] = []
    extra_reasons: list[str] = []
    concentrated: list[str] = []
    if status == BookExposureStatus.FAIL_CLOSED.value:
        return False, tuple(breaches), tuple(concentrated), tuple(extra_reasons)
    if status == BookExposureStatus.PARTIAL.value:
        extra_reasons.append(BookExposureReason.INCOMPLETE_EXPOSURE.value)
        within = False
    else:
        within = True
    if policy is None or gross is None or net is None:
        return within, tuple(breaches), tuple(concentrated), tuple(extra_reasons)
    if policy.max_gross_exposure is not None and gross > policy.max_gross_exposure:
        breaches.append(BookExposureReason.GROSS_EXPOSURE_LIMIT.value)
        within = False
    if policy.max_net_exposure is not None and abs(net) > policy.max_net_exposure:
        breaches.append(BookExposureReason.NET_EXPOSURE_LIMIT.value)
        within = False
    fraction = policy.max_instrument_concentration_fraction
    if fraction is not None and gross > 0:
        for row in rows:
            if row.gross_exposure is None:
                continue
            if row.gross_exposure / gross > fraction:
                concentrated.append(row.instrument_id)
                if BookExposureReason.INSTRUMENT_CONCENTRATION.value not in breaches:
                    breaches.append(BookExposureReason.INSTRUMENT_CONCENTRATION.value)
                within = False
    return within, tuple(breaches), tuple(concentrated), tuple(extra_reasons)


def aggregate_book_exposure(
    portfolio: CanonicalPortfolio,
    *,
    policy: BookLimitPolicy | None = None,
) -> BookExposureReport:
    """Aggregate current canonical positions into gross/net exposure and limit use.

    Read-only. Live books may be observed; nothing here fetches a broker,
    submits, resizes, or rebalances.
    """
    if not isinstance(portfolio, CanonicalPortfolio):
        raise TypeError("expected CanonicalPortfolio")
    positions = tuple(
        portfolio.positions[instrument_id]
        for instrument_id in sorted(portfolio.positions)
    )
    rows = tuple(
        _row_for_position(position, portfolio.get_mark(position.instrument_id))
        for position in positions
    )
    reasons: list[str] = []
    for row in rows:
        reasons.extend(row.reason_codes)

    if any(row.status == BookExposureStatus.FAIL_CLOSED.value for row in rows):
        status = BookExposureStatus.FAIL_CLOSED.value
    elif any(row.status == BookExposureStatus.PARTIAL.value for row in rows):
        status = BookExposureStatus.PARTIAL.value
    else:
        status = BookExposureStatus.COMPLETE.value

    included = [row for row in rows if row.signed_exposure is not None]
    currencies = {row.currency for row in included}
    if len(currencies) > 1:
        status = BookExposureStatus.FAIL_CLOSED.value
        reasons.append(BookExposureReason.MIXED_CURRENCY_NO_FX.value)
        within, breaches, concentrated, extra = _apply_limits(
            policy=policy,
            status=status,
            gross=None,
            net=None,
            rows=rows,
        )
        return BookExposureReport(
            account_id=portfolio.key.account_id,
            mode=portfolio.key.mode,
            currency=policy.currency if policy is not None else None,
            status=status,
            gross_exposure=None,
            net_exposure=None,
            positions=rows,
            by_asset_class={},
            reason_codes=tuple(dict.fromkeys(reasons + list(extra))),
            limit_breaches=breaches,
            concentrated_instrument_ids=concentrated,
            within_limits=within,
        )

    currency = next(iter(currencies), policy.currency if policy is not None else None)
    if (
        policy is not None
        and currency is not None
        and included
        and currency != policy.currency
    ):
        status = BookExposureStatus.FAIL_CLOSED.value
        reasons.append(BookExposureReason.MIXED_CURRENCY_NO_FX.value)
        within, breaches, concentrated, extra = _apply_limits(
            policy=policy,
            status=status,
            gross=None,
            net=None,
            rows=rows,
        )
        return BookExposureReport(
            account_id=portfolio.key.account_id,
            mode=portfolio.key.mode,
            currency=policy.currency,
            status=status,
            gross_exposure=None,
            net_exposure=None,
            positions=rows,
            by_asset_class={},
            reason_codes=tuple(dict.fromkeys(reasons + list(extra))),
            limit_breaches=breaches,
            concentrated_instrument_ids=concentrated,
            within_limits=within,
        )

    gross = sum((row.gross_exposure or Decimal("0") for row in included), Decimal("0"))
    net = sum((row.signed_exposure or Decimal("0") for row in included), Decimal("0"))
    by_class: dict[str, AssetClassExposure] = {}
    class_gross: dict[str, Decimal] = {}
    class_net: dict[str, Decimal] = {}
    for row in included:
        asset = row.asset_class
        class_gross[asset] = class_gross.get(asset, Decimal("0")) + (row.gross_exposure or Decimal("0"))
        class_net[asset] = class_net.get(asset, Decimal("0")) + (row.signed_exposure or Decimal("0"))
    for asset in sorted(class_gross):
        by_class[asset] = AssetClassExposure(
            gross_exposure=class_gross[asset],
            net_exposure=class_net[asset],
        )

    within, breaches, concentrated, extra = _apply_limits(
        policy=policy,
        status=status,
        gross=gross,
        net=net,
        rows=rows,
    )
    reasons.extend(extra)
    reasons.extend(breaches)
    return BookExposureReport(
        account_id=portfolio.key.account_id,
        mode=portfolio.key.mode,
        currency=currency,
        status=status,
        gross_exposure=gross,
        net_exposure=net,
        positions=rows,
        by_asset_class=by_class,
        reason_codes=tuple(dict.fromkeys(reasons)),
        limit_breaches=breaches,
        concentrated_instrument_ids=concentrated,
        within_limits=within,
    )


__all__ = [
    "BOOK_EXPOSURE_VERSION",
    "AssetClassExposure",
    "BookExposureReason",
    "BookExposureReport",
    "BookExposureStatus",
    "BookLimitPolicy",
    "PositionExposureRow",
    "aggregate_book_exposure",
]
