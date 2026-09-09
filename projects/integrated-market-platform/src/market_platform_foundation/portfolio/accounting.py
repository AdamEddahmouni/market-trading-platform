"""One authoritative money / notional accounting kernel (G4 / BL-0211).

Centralizes the exact-Decimal formulas that previously lived in scattered
float or duplicated code paths. Every authoritative money/notional/P&L
calculation for Equities, Options, and Futures flows through here (or through
``portfolio.instrument_economics`` which supplies the economics this kernel
consumes).

Numeric policy (G4 Phase 2):

- authoritative money amounts, prices, quantities, multipliers, notionals,
  cost basis, realized/unrealized P&L are ``Decimal`` (exact) or integer
  minor units where the Paper path owns them;
- binary float is NEVER accepted at this boundary: ``exact_decimal`` raises
  ``AccountingError(UNSUPPORTED_BINARY_FLOAT)`` for raw float input. Boundary
  code that receives floats (provider rows / legacy fixtures) must convert
  with the *string-exact* ``Decimal(str(value))`` form first (see
  ``portfolio.options_ledger`` for the canonical example);
- the five economic quantities are NOT interchangeable: transaction cash
  requirement, gross economic exposure, mark-to-market value, P&L, and
  buying-power reservation are distinct formulas selected per instrument
  kind. ``None`` means "no safe formula exists" and the caller must fail
  closed (never apply equity arithmetic to futures).

Kind semantics:

- Equity/ETF:      notional = price x shares; multiplier is 1.
- Option:          premium/exposure = price x contracts x multiplier
                   (multiplier from canonical contract identity, never 100).
- Future:          economic exposure = contracts x multiplier x price;
                   P&L = signed quantity x multiplier x (mark - reference).
                   Full notional is exposure, NOT settled cash (margin is not
                   invented here).
- Crypto spot:     quote-currency value = base units x pair price.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any, Mapping

EQUITY_LIKE_KINDS: frozenset[str] = frozenset({"TRADABLE_SECURITY", "ETF_FUND"})
DERIVATIVE_KINDS: frozenset[str] = frozenset({"OPTION_CONTRACT", "FUTURE_CONTRACT"})


class AccountingErrorCode(StrEnum):
    UNSUPPORTED_BINARY_FLOAT = "UNSUPPORTED_BINARY_FLOAT"
    INVALID_AMOUNT = "INVALID_AMOUNT"
    UNSUPPORTED_ECONOMICS = "UNSUPPORTED_ECONOMICS"
    INVALID_PRICE = "INVALID_PRICE"
    INVALID_QUANTITY = "INVALID_QUANTITY"
    INVALID_MULTIPLIER = "INVALID_MULTIPLIER"


@dataclass(frozen=True, slots=True)
class AccountingError(Exception):
    code: AccountingErrorCode
    message: str
    details: Mapping[str, Any]

    def __str__(self) -> str:
        return f"{self.code.value}: {self.message}"


def exact_decimal(value: Any, *, field_name: str = "value", allow_float: bool = False) -> Decimal:
    """Coerce to an exact ``Decimal``; binary float is rejected by default.

    ``allow_float=True`` performs the *string-exact* conversion
    ``Decimal(str(value))`` so a legacy float like ``0.1`` becomes the
    human-intent ``Decimal('0.1')`` rather than the binary expansion. It is
    only for boundary code that cannot avoid a float at the seam; internal
    arithmetic must stay Decimal. No raw float math ever reaches a formula.
    """
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, int) and not isinstance(value, bool):
        result = Decimal(value)
    elif isinstance(value, str):
        try:
            result = Decimal(value)
        except InvalidOperation:
            raise AccountingError(
                AccountingErrorCode.INVALID_AMOUNT,
                f"{field_name} is not a valid decimal string",
                {field_name: value},
            ) from None
    elif isinstance(value, float):
        if not allow_float:
            raise AccountingError(
                AccountingErrorCode.UNSUPPORTED_BINARY_FLOAT,
                f"{field_name} must be Decimal/int/str, not binary float "
                "(convert at the boundary with Decimal(str(value)))",
                {field_name: value},
            )
        result = Decimal(str(value))
    else:
        raise AccountingError(
            AccountingErrorCode.INVALID_AMOUNT,
            f"{field_name} must be a Decimal, int, or decimal string",
            {field_name: value, "value_type": type(value).__name__},
        )
    if not result.is_finite():
        raise AccountingError(
            AccountingErrorCode.INVALID_AMOUNT,
            f"{field_name} must be finite",
            {field_name: str(value)},
        )
    return result


def notional(quantity: Any, price: Any, multiplier: Any = 1) -> Decimal:
    """Generic q x p x m. Callers select the kind-specific meaning explicitly."""
    q = exact_decimal(quantity, field_name="quantity")
    p = exact_decimal(price, field_name="price")
    m = exact_decimal(multiplier, field_name="multiplier")
    if p < 0:
        raise AccountingError(AccountingErrorCode.INVALID_PRICE, "price must be non-negative", {"price": str(p)})
    if m <= 0:
        raise AccountingError(
            AccountingErrorCode.INVALID_MULTIPLIER,
            "multiplier must be positive",
            {"multiplier": str(m)},
        )
    return q * p * m


def equity_notional(quantity: Any, price: Any) -> Decimal:
    """Equity: price x shares (multiplier is 1 by definition)."""
    return notional(quantity, price, 1)


def option_premium(quantity: Any, price: Any, multiplier: Any) -> Decimal:
    """Option premium / exposure: price x contracts x multiplier."""
    return notional(quantity, price, multiplier)


def future_exposure(quantity: Any, multiplier: Any, price: Any) -> Decimal:
    """Future gross economic exposure: contracts x multiplier x price.

    This is exposure, never a settled-cash expenditure or margin requirement.
    """
    return notional(quantity, price, multiplier)


def future_variation_pnl(
    quantity: Any,
    multiplier: Any,
    mark: Any,
    reference: Any,
) -> Decimal:
    """Future mark-to-market P&L: signed quantity x multiplier x (mark - reference)."""
    q = exact_decimal(quantity, field_name="quantity")
    m = exact_decimal(multiplier, field_name="multiplier")
    mark_d = exact_decimal(mark, field_name="mark")
    ref = exact_decimal(reference, field_name="reference")
    if m <= 0:
        raise AccountingError(
            AccountingErrorCode.INVALID_MULTIPLIER,
            "multiplier must be positive",
            {"multiplier": str(m)},
        )
    return q * m * (mark_d - ref)


def market_value_by_kind(
    *,
    instrument_kind: str,
    quantity: Any,
    price: Any,
    multiplier: Any = 1,
) -> Decimal | None:
    """Kind-aware mark-to-market value; ``None`` when no safe value exists.

    Futures never return a cash-equity-style market value (full notional is
    exposure, not owned cash): callers use ``future_exposure`` and
    ``future_variation_pnl`` for futures-native semantics.
    """
    kind = str(instrument_kind).upper()
    if kind in EQUITY_LIKE_KINDS or kind == "CRYPTO_PAIR":
        return equity_notional(quantity, price)
    if kind == "OPTION_CONTRACT":
        return option_premium(quantity, price, multiplier)
    if kind == "FUTURE_CONTRACT":
        return None
    raise AccountingError(
        AccountingErrorCode.UNSUPPORTED_ECONOMICS,
        "no market-value formula for instrument kind",
        {"instrument_kind": kind},
    )


def cash_requirement_by_kind(
    *,
    instrument_kind: str,
    side: str,
    quantity: Any,
    price: Any,
    multiplier: Any = 1,
) -> Decimal | None:
    """Transaction cash requirement; ``None`` = unsupported, caller fails closed.

    - equity/ETF/crypto BUY: price x quantity (cash-funded);
    - long option BUY:       premium x contracts x multiplier (debit);
    - option SELL:           ``None`` (uncovered short margin not invented);
    - future:                ``None`` (no safe margin model exists; never
                             treat full notional as settled cash);
    - reference/synthetic:   ``None`` (never executable).
    """
    side_upper = str(side).upper()
    kind = str(instrument_kind).upper()
    if kind in EQUITY_LIKE_KINDS or kind == "CRYPTO_PAIR":
        if side_upper != "BUY":
            return None
        return equity_notional(quantity, price)
    if kind == "OPTION_CONTRACT":
        if side_upper != "BUY":
            return None
        return option_premium(quantity, price, multiplier)
    if kind == "FUTURE_CONTRACT":
        return None
    raise AccountingError(
        AccountingErrorCode.UNSUPPORTED_ECONOMICS,
        "no cash-requirement formula for instrument kind",
        {"instrument_kind": kind},
    )


def realized_pnl_on_close(
    *,
    instrument_kind: str,
    entry_price: Any,
    exit_price: Any,
    quantity: Any,
    multiplier: Any = 1,
) -> Decimal | None:
    """Signed realized P&L from a full close of ``quantity`` units.

    Sign semantics: positive quantity (long) earns (exit - entry); negative
    quantity (short) earns (entry - exit). Returns ``None`` for kinds without
    a safe close formula (futures use variation P&L against the roll/entry
    reference instead of an exit-price sale).
    """
    kind = str(instrument_kind).upper()
    entry = exact_decimal(entry_price, field_name="entry_price")
    exit_d = exact_decimal(exit_price, field_name="exit_price")
    q = exact_decimal(quantity, field_name="quantity")
    if kind in EQUITY_LIKE_KINDS or kind == "CRYPTO_PAIR":
        return q * (exit_d - entry)
    if kind == "OPTION_CONTRACT":
        m = exact_decimal(multiplier, field_name="multiplier")
        if m <= 0:
            raise AccountingError(
                AccountingErrorCode.INVALID_MULTIPLIER,
                "multiplier must be positive",
                {"multiplier": str(m)},
            )
        return q * (exit_d - entry) * m
    if kind == "FUTURE_CONTRACT":
        return None
    raise AccountingError(
        AccountingErrorCode.UNSUPPORTED_ECONOMICS,
        "no realized-P&L formula for instrument kind",
        {"instrument_kind": kind},
    )


def working_reservation(
    working_remaining: Any,
    effective_price: Any,
    multiplier: Any = 1,
) -> Decimal:
    """Reservation for a still-working remainder: remaining x price x multiplier.

    The canonical working-obligation building block. ``working_remaining`` is
    never the original desired quantity: partial fills and replaces shrink it
    before this formula is applied (G3 §24/§36, G4 Phase 7).
    """
    remaining = exact_decimal(working_remaining, field_name="working_remaining")
    if remaining < 0:
        raise AccountingError(
            AccountingErrorCode.INVALID_QUANTITY,
            "working_remaining must be non-negative",
            {"working_remaining": str(remaining)},
        )
    return notional(remaining, effective_price, multiplier)


def exact_display(value: Any) -> str:
    """Deterministic string form for Decimal values (``format(value, 'f')``)."""
    return format(exact_decimal(value, field_name="value"), "f")


__all__ = [
    "AccountingError",
    "AccountingErrorCode",
    "DERIVATIVE_KINDS",
    "EQUITY_LIKE_KINDS",
    "cash_requirement_by_kind",
    "equity_notional",
    "exact_decimal",
    "exact_display",
    "future_exposure",
    "future_variation_pnl",
    "market_value_by_kind",
    "notional",
    "option_premium",
    "realized_pnl_on_close",
    "working_reservation",
]