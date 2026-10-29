"""Paper-only equity/ETF short-sale admission (rebuild step 6, owner decision 2).

Runs only on a portfolio-scoped internal-simulation account whose frozen policy allows shorts. Every other
account keeps the existing rule: a sell may only reduce that instrument's own long position.

A sell that only reduces a long is not a short and passes through unchanged. A sell that would turn a long
into a short in one order is refused (reversal), as it is everywhere else. A short open must pass, in order:
the instrument scope, a known price at or above the policy minimum, the short-sale restriction (fails closed
when the day change is unknown), and the initial margin against current buying power.

Borrow is never checked against a real locate: the account records ``SIMULATED_EASY_TO_BORROW``.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_CEILING
from typing import Any, Mapping

from .contracts import exact_quantity

SHORTABLE_KINDS = frozenset({"TRADABLE_SECURITY", "ETF_FUND"})
SHORT_SALE_FACTS_SCHEMA = "paper-short-sale-facts/1.0.0"


def build_short_sale_facts(*, day_change_bps: int | None, source: str, as_of_ns: int | None) -> dict[str, Any]:
    """The server-derived facts a short open is judged on; recorded on the intent."""
    return {
        "as_of_ns": int(as_of_ns) if as_of_ns is not None else None,
        "day_change_bps": int(day_change_bps) if day_change_bps is not None else None,
        "schema_version": SHORT_SALE_FACTS_SCHEMA,
        "source": str(source),
    }


def short_sale_facts_from_change_pct(change_pct: Any, *, source: str, as_of_ns: int | None) -> dict[str, Any]:
    try:
        value = Decimal(str(change_pct))
    except Exception:  # noqa: BLE001 - an unparseable change is an unknown change
        value = None
    if value is None or not value.is_finite():
        return build_short_sale_facts(day_change_bps=None, source=source, as_of_ns=as_of_ns)
    bps = int((value * 100).to_integral_value(rounding=ROUND_CEILING))
    return build_short_sale_facts(day_change_bps=bps, source=source, as_of_ns=as_of_ns)


def enforce_equity_sell(
    *,
    ledger: Any,
    intent: Mapping[str, Any],
    kind: str,
    position_qty: int | Decimal,
    reserved_sell: int | Decimal,
    price_minor: int | Decimal | None,
    costs_minor: int,
    buying_power_minor: int,
) -> None:
    """Admit an equity/ETF sell or an explicitly opted-in crypto sell; prices are account-scale."""
    quantity = exact_quantity(intent.get("desired_quantity", 0))
    owned = max(0, position_qty)
    available_to_sell = max(Decimal(0), Decimal(owned) - Decimal(reserved_sell))
    if owned > 0:
        if quantity <= available_to_sell:
            return  # an ordinary reduction or close of a long
        raise ValueError(
            "POSITION_REVERSAL_NOT_ALLOWED: "
            f"{{'owned_quantity': {owned}, 'available_to_sell': {available_to_sell}}}"
        )
    crypto = kind == "CRYPTO_PAIR" and ledger.allows_crypto_short()
    if crypto:
        if price_minor is None or price_minor <= 0:
            raise ValueError("REQUIRED_PRICE_MISSING: crypto short requires an account-scale price")
        required = int((quantity * Decimal(price_minor) * int(ledger.policy["crypto_short_initial_margin_bps"]) / 10_000
                        + costs_minor).to_integral_value(rounding=ROUND_CEILING))
        if required > buying_power_minor:
            raise ValueError("INSUFFICIENT_SHORT_MARGIN")
        return  # USD spot simulation: no equity minimum-price or SSR rule.
    if kind not in SHORTABLE_KINDS:
        raise ValueError(f"SHORT_INSTRUMENT_UNSUPPORTED: {kind}")
    if quantity != quantity.to_integral_value():
        raise ValueError("SHORT_QUANTITY_FRACTIONAL")
    if price_minor is None:
        raise ValueError("REQUIRED_PRICE_MISSING: no price reference for short sale")
    minimum = int(ledger.policy.get("short_min_price_minor", 0))
    if int(price_minor) < minimum:
        raise ValueError(f"SHORT_PRICE_BELOW_MINIMUM: {{'price_minor': {int(price_minor)}, 'minimum_minor': {minimum}}}")
    facts = intent.get("short_sale_facts") or {}
    change = facts.get("day_change_bps")
    if type(change) is not int:
        raise ValueError("SHORT_SALE_RESTRICTION_UNKNOWN: the day change is required to admit a short sale")
    limit = int(ledger.policy.get("short_ssr_drop_bps", 0))
    if change <= -limit:
        raise ValueError(f"SHORT_SALE_RESTRICTION: {{'day_change_bps': {change}, 'restriction_bps': {-limit}}}")
    # The proceeds are credited to cash and held back again, so the net draw on buying power is the margin.
    notional = quantity * Decimal(int(price_minor))
    margin = notional * int(ledger.policy.get("short_initial_margin_bps", 0)) / 10_000
    required = int((margin + costs_minor).to_integral_value(rounding=ROUND_CEILING))
    if required > int(buying_power_minor):
        raise ValueError(
            "INSUFFICIENT_SHORT_MARGIN: "
            f"{{'required_margin_minor': {required}, 'buying_power_minor': {int(buying_power_minor)}}}"
        )


def enforce_equity_buy(*, intent: Mapping[str, Any], position_qty: int, required_minor: int,
                       buying_power_minor: int) -> None:
    """A BUY on a short-enabled account: a cover is never refused for cash; a long open uses buying power."""
    quantity = exact_quantity(intent.get("desired_quantity", 0))
    if position_qty < 0:
        if quantity > -position_qty:
            raise ValueError(
                "POSITION_REVERSAL_NOT_ALLOWED: "
                f"{{'short_quantity': {-position_qty}, 'buy_quantity': {quantity}}}"
            )
        return
    if required_minor > buying_power_minor:
        raise ValueError("INSUFFICIENT_CASH")
