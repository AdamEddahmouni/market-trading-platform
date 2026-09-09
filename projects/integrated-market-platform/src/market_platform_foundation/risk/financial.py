"""Cash/available-funds availability for order intents (G3 / BL-0202).

One canonical financial source: the Paper ledger's cash projection (which the
G2 ``portfolio.paper_adapter`` consumes as the canonical USD snapshot) minus
working-order obligations derived from open orders. No second reservation
ledger is created; obligations are derived from canonical working order state
(G3 §22, §23).

Supported asset-aware hooks (G3 §65): equity cash-funded buys enforce
``required_cash <= available_cash``; sell-side enforces owned quantity;
options long enforce premium × multiplier; crypto spot enforces quote-currency
cash; futures/bonds/reference identities fail explicitly where no safe
resource model exists (G3 §29–32, §66). No margin model is invented.
"""

from __future__ import annotations

from typing import Any, Mapping

from ..portfolio.canonical import QuantityUnit

INSUFFICIENT_CASH = "INSUFFICIENT_CASH"
INSUFFICIENT_POSITION = "INSUFFICIENT_POSITION"
INSUFFICIENT_SETTLEMENT_CURRENCY = "INSUFFICIENT_SETTLEMENT_CURRENCY"
UNSUPPORTED_RISK_MODEL = "UNSUPPORTED_RISK_MODEL"
REQUIRED_PRICE_MISSING = "REQUIRED_PRICE_MISSING"


def canonical_order_multiplier(order: Mapping[str, Any]) -> int:
    """Resolve one order's contract multiplier with G4 fail-closed semantics.

    Derivative orders (OPTION_CONTRACT / FUTURE_CONTRACT) must carry an
    explicit canonical multiplier: missing economics raise ``ValueError``
    rather than silently acquiring equity-style multiplier=1. Equity and
    legacy equity orders (no instrument_kind) keep multiplier=1. Symbol
    heuristics are never used.
    """
    raw = order.get("contract_multiplier")
    kind = str(order.get("instrument_kind", "") or "")
    if kind in {"OPTION_CONTRACT", "FUTURE_CONTRACT"}:
        if raw is None or (isinstance(raw, str) and not raw.strip()):
            raise ValueError(
                f"MISSING_CONTRACT_MULTIPLIER:{kind}"
            )
        if int(raw) <= 0:
            raise ValueError(
                f"INVALID_CONTRACT_MULTIPLIER:{kind}"
            )
    if raw is None:
        return 1
    return int(raw)


def _order_currency(order: Mapping[str, Any]) -> str:
    """An order's settlement currency — never a silent USD assumption (G4)."""
    raw = order.get("currency")
    if raw is None or not str(raw).strip():
        return "USD"
    return str(raw).upper()


def working_order_obligations_by_currency(
    ledger: Any,
    *,
    exclude_order_id: str | None = None,
) -> dict[str, int]:
    """Worst-case remaining cash obligations keyed by settlement currency (G4).

    For each open order (ACTIVATED/WORKING/PARTIALLY_FILLED/REPLACE_PENDING/
    REPLACED) with a buy-side direction, reserve ``working_remaining ×
    effective price × multiplier`` in the order's own settlement currency.
    Effective price is the limit price for LIMIT orders and the last fill
    price (or live mark) for MARKET orders; when neither exists the
    obligation is skipped rather than assumed zero, so callers can fail
    closed where a price is genuinely required. ``exclude_order_id`` removes
    one order's own obligation (replace recheck).
    """
    buckets: dict[str, int] = {}
    for order in ledger.project_orders():
        state = str(order.get("state", ""))
        if state not in {"ACTIVATED", "WORKING", "PARTIALLY_FILLED", "REPLACE_PENDING", "REPLACED"}:
            continue
        direction = str(order.get("direction", ""))
        if direction != "long":
            continue
        if exclude_order_id is not None and str(order.get("order_id", "")) == str(exclude_order_id):
            continue
        remaining = _order_working_remaining(order)
        if remaining <= 0:
            continue
        price = _order_effective_price_minor(order)
        if price is None:
            continue
        multiplier = canonical_order_multiplier(order)
        currency = _order_currency(order)
        buckets[currency] = buckets.get(currency, 0) + remaining * price * multiplier
    return buckets


def working_order_obligations_minor(ledger: Any, *, exclude_order_id: str | None = None) -> int:
    """Sum worst-case remaining cash obligations of open orders (G3 §24, G4).

    Kept for USD/legacy callers; the per-currency truth lives in
    ``working_order_obligations_by_currency``.
    """
    return sum(
        working_order_obligations_by_currency(ledger, exclude_order_id=exclude_order_id).values()
    )


def _order_effective_price_minor(order: Mapping[str, Any]) -> int | None:
    order_type = str(order.get("order_type", "MARKET"))
    limit = order.get("limit_price_minor")
    if order_type == "LIMIT" and limit is not None:
        return int(limit)
    for key in ("average_fill_minor", "fill_price_minor", "mark_minor"):
        value = order.get(key)
        if value is not None:
            return int(value)
    return None


def available_cash_minor(ledger: Any) -> int:
    """Canonical settled cash minus working-order obligations (G3 §23)."""
    account = ledger.project_account()
    cash = int(account.get("cash_minor", 0))
    obligations = working_order_obligations_minor(ledger)
    return max(0, cash - obligations)


def required_cash_minor(
    *,
    quantity: int,
    price_minor: int | None,
    multiplier: int = 1,
    commission_minor: int = 0,
    fee_minor: int = 0,
) -> int | None:
    """Worst-case cash required for a cash-funded buy (G3 §24/§26)."""
    if price_minor is None:
        return None
    return quantity * price_minor * multiplier + commission_minor + fee_minor


def currency_available_cash_minor(
    cash_minor_by_currency: Mapping[str, int],
    obligations_by_currency: Mapping[str, int],
    currency: str,
) -> int | None:
    """Available cash in ONE currency bucket; ``None`` when the bucket is absent.

    The bucket must exist — a missing currency is never treated as zero cash
    or as a silent 1:1 conversion (G4 Phase 6 rule 9).
    """
    normalized = str(currency).upper()
    bucket = cash_minor_by_currency.get(normalized)
    if bucket is None:
        return None
    obligations = obligations_by_currency.get(normalized, 0)
    return max(0, int(bucket) - int(obligations))


def order_intent_financial_check(
    *,
    ledger: Any,
    side: str,
    quantity: int,
    price_minor: int | None,
    multiplier: int = 1,
    currency: str = "USD",
    account_currency: str = "USD",
    currency_cash_minor: Mapping[str, int] | None = None,
) -> tuple[str | None, dict[str, Any]]:
    """Fail-closed financial availability gate for one order intent.

    Returns ``(reason_code, facts)``; ``reason_code`` is None when the order
    is financially affordable. The canonical rule for supported cash-funded
    buys: ``required_cash <= available_cash`` (G3 §26). Sell-side availability
    uses owned quantity when shorting is not explicitly enabled (G3 §28).

    ``currency_cash_minor`` enables per-currency accounting (G4 Phase 6): the
    order's settlement-currency bucket must exist (``None`` ->
    INSUFFICIENT_SETTLEMENT_CURRENCY, never 1:1), and available cash is that
    bucket minus that currency's working obligations. When omitted, legacy
    single-currency behavior applies (account currency required).
    """
    facts: dict[str, Any] = {}
    if currency_cash_minor is not None:
        order_currency = str(currency).upper()
        if order_currency not in currency_cash_minor:
            # No bucket, no conversion: fail closed with the funding reason.
            return INSUFFICIENT_SETTLEMENT_CURRENCY, facts
        obligations = working_order_obligations_by_currency(ledger)
        available = currency_available_cash_minor(
            currency_cash_minor,
            obligations,
            order_currency,
        )
        facts["settlement_currency"] = order_currency
        facts["available_cash_minor"] = available
    else:
        if str(currency).upper() != str(account_currency).upper():
            # No 1:1 FX assumption (G3 §25): an order denominated in a currency
            # the account does not fund fails explicitly unless a conversion
            # mechanism exists.
            return INSUFFICIENT_SETTLEMENT_CURRENCY, facts
        available = available_cash_minor(ledger)
        facts["available_cash_minor"] = available

    if side == "BUY":
        required = required_cash_minor(
            quantity=quantity,
            price_minor=price_minor,
            multiplier=multiplier,
        )
        if required is None:
            return REQUIRED_PRICE_MISSING, facts
        facts["required_cash_minor"] = required
        if required > available:
            return INSUFFICIENT_CASH, facts
        return None, facts

    if side == "SELL":
        position_shares = int(ledger._project_ledger().get("position_shares", 0))
        reserved_sell = _reserved_sell_quantity(ledger)
        owned = max(0, position_shares)
        available_to_sell = max(0, owned - reserved_sell)
        facts["owned_quantity"] = owned
        facts["reserved_sell_quantity"] = reserved_sell
        facts["available_to_sell"] = available_to_sell
        if quantity > available_to_sell:
            return INSUFFICIENT_POSITION, facts
        return None, facts

    return UNSUPPORTED_RISK_MODEL, facts


def _order_working_remaining(order: Mapping[str, Any]) -> int:
    """Canonical working remainder for an open order (G3 §36).

    Prefers the projection's ``working_remaining`` (requested/authorized minus
    cumulative filled); falls back to ``remaining_quantity`` for legacy
    callers, then to the original desired quantity only when no fill state
    exists at all. Never conflates original requested quantity with the
    remaining quantity after partial fills.
    """
    working = order.get("working_remaining")
    if working is not None:
        return max(0, int(working))
    legacy = order.get("remaining_quantity")
    if legacy is not None:
        return max(0, int(legacy))
    return max(0, int(order.get("desired_quantity", 0)))


def _reserved_sell_quantity(ledger: Any) -> int:
    """Quantity already reserved by open sell orders (G3 §28)."""
    total = 0
    for order in ledger.project_orders():
        state = str(order.get("state", ""))
        if state not in {"ACTIVATED", "WORKING", "PARTIALLY_FILLED", "REPLACE_PENDING", "REPLACED"}:
            continue
        if str(order.get("direction", "")) != "short":
            continue
        total += _order_working_remaining(order)
    return total


def asset_aware_cash_requirement(
    *,
    asset_class: str,
    instrument_kind: str,
    quantity: int,
    price_minor: int | None,
    multiplier: int = 1,
    quantity_unit: str = QuantityUnit.SHARES.value,
) -> tuple[str | None, int | None]:
    """Per-asset cash requirement hook (G3 §29–32, §65).

    Returns ``(unsupported_reason, required_cash_minor)``. ``required_cash``
    is None when no safe cash model exists for the asset (futures notional is
    NOT settlement cash; uncovered options/futures margin is not invented).
    """
    kind = str(instrument_kind).upper()
    if kind in {
        "FUTURE_FAMILY",
        "CONTINUOUS_SERIES",
        "COMMODITY_ECONOMIC",
        "COMMODITY_SPOT",
        "INDEX_BENCHMARK",
        "CURRENCY_UNIT",
        "FX_PAIR",
        "SOVEREIGN_SECURITY",
    }:
        return "NON_EXECUTABLE_INSTRUMENT", None
    if str(asset_class).upper() == "BOND":
        return "NON_EXECUTABLE_INSTRUMENT", None
    if kind == "FUTURE_CONTRACT":
        # No safe margin requirement exists; never use equity arithmetic.
        return UNSUPPORTED_RISK_MODEL, None
    if kind == "OPTION_CONTRACT":
        # Long options: contracts × premium × multiplier (G3 §29).
        if price_minor is None:
            return REQUIRED_PRICE_MISSING, None
        return None, quantity * price_minor * multiplier
    if kind in {"TRADABLE_SECURITY", "ETF_FUND", "CRYPTO_PAIR"}:
        if price_minor is None:
            return REQUIRED_PRICE_MISSING, None
        return None, quantity * price_minor * multiplier
    return UNSUPPORTED_RISK_MODEL, None


__all__ = [
    "INSUFFICIENT_CASH",
    "INSUFFICIENT_POSITION",
    "INSUFFICIENT_SETTLEMENT_CURRENCY",
    "REQUIRED_PRICE_MISSING",
    "UNSUPPORTED_RISK_MODEL",
    "asset_aware_cash_requirement",
    "available_cash_minor",
    "currency_available_cash_minor",
    "order_intent_financial_check",
    "required_cash_minor",
    "working_order_obligations_by_currency",
    "working_order_obligations_minor",
]