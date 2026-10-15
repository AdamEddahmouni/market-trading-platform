"""Canonical Paper fill → CanonicalPortfolio mutation (G13).

One authoritative accounting path for Paper fills across equities, options,
and futures. Uses G4 ``portfolio.accounting`` formulas (exact Decimal) and
writes into ``CanonicalPortfolio`` — never a parallel options/futures ledger.

Legacy ``portfolio.ledger.apply_fill`` remains a compatibility projection for
equity-only replay parity; derivative fills route here exclusively.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_CEILING
from typing import Any, Mapping

from .accounting import (
    exact_decimal,
    future_variation_pnl,
    option_premium,
)
from .canonical import CanonicalPortfolio, CashBalance, PositionInput
from .instrument_economics import kind_default_quantity_unit
from ..paper.cost_friction import resolve_paper_cost_friction


@dataclass(frozen=True, slots=True)
class PaperFillResult:
    fill_id: str
    instrument_id: str
    cash_delta_native: Decimal
    position_quantity_after: Decimal
    realized_pnl_delta_native: Decimal


def _minor_to_decimal(price_minor: int, scale: int) -> Decimal:
    return Decimal(int(price_minor)) / Decimal(scale)


def _decimal_to_minor(amount: Decimal, scale: int) -> int:
    return int((amount * Decimal(scale)).to_integral_value())


def _instrument_from_fill(
    fill: Mapping[str, Any],
    intent: Mapping[str, Any] | None,
) -> dict[str, Any]:
    instrument = fill.get("instrument")
    if isinstance(instrument, dict) and instrument.get("instrument_kind"):
        return dict(instrument)
    if intent is not None:
        candidate = intent.get("instrument")
        if isinstance(candidate, dict) and candidate.get("instrument_kind"):
            return dict(candidate)
    return {
        "instrument_id": str(fill.get("instrument_id", "UNKNOWN")),
        "instrument_kind": "TRADABLE_SECURITY",
        "asset_class": "EQUITY",
        "currency": "USD",
        "contract_multiplier": "1",
    }


def _positive_integer(value: Any, *, field_name: str) -> int:
    result = exact_decimal(value, field_name=field_name)
    if result <= 0 or result != result.to_integral_value():
        raise ValueError(f"INVALID_{field_name.upper()}: positive integer required")
    return int(result)


def _signed_fill_quantity(fill: Mapping[str, Any], instrument: Mapping[str, Any]) -> Decimal:
    qty = exact_decimal(fill["fill_quantity"], field_name="fill_quantity")
    if qty <= 0:
        raise ValueError("INVALID_QUANTITY: positive fill quantity required")
    if str(instrument.get("instrument_kind", "TRADABLE_SECURITY")).upper() != "CRYPTO_PAIR":
        if qty != qty.to_integral_value():
            raise ValueError("INVALID_QUANTITY: whole shares/contracts required")
    else:
        step_raw = instrument.get("quantity_step")
        if step_raw is not None:
            step = exact_decimal(step_raw, field_name="quantity_step")
            if step <= 0 or qty % step != 0:
                raise ValueError("INVALID_QUANTITY: quantity_step violated")
        # Venue minimum is an order-admission rule; a legitimate partial
        # execution may be smaller while still respecting the quantity step.
    direction = str(fill.get("direction", "long")).lower()
    if direction not in {"long", "short"}:
        raise ValueError("INVALID_DIRECTION")
    return qty if direction == "long" else -qty


def apply_paper_fill_to_portfolio(
    portfolio: CanonicalPortfolio,
    *,
    fill: Mapping[str, Any],
    intent: Mapping[str, Any] | None = None,
    policy: Mapping[str, Any],
    applied_fill_ids: set[str] | None = None,
) -> PaperFillResult:
    """Apply one canonical Paper fill idempotently to ``portfolio``.

    Raises ``ValueError`` when the fill was already applied (duplicate
    ``fill_id``). Commission/fees follow the Paper policy minor-unit rules.
    """
    fill_id = str(fill["fill_id"])
    if applied_fill_ids is not None:
        if fill_id in applied_fill_ids:
            raise ValueError(f"DUPLICATE_FILL:{fill_id}")

    instrument = _instrument_from_fill(fill, intent)
    kind = str(instrument.get("instrument_kind", "TRADABLE_SECURITY")).upper()
    asset_class = str(instrument.get("asset_class", "EQUITY")).upper()
    instrument_id = str(instrument.get("instrument_id") or fill.get("instrument_id", "UNKNOWN"))
    if fill.get("instrument_id") is not None and str(fill["instrument_id"]) != instrument_id:
        raise ValueError("FILL_INSTRUMENT_MISMATCH")
    currency = str(instrument.get("currency") or policy.get("currency", "USD")).upper()
    scale = _positive_integer(policy.get("price_scale", 100), field_name="price_scale")
    price_scale = _positive_integer(instrument.get("price_scale", scale), field_name="price_scale")
    if kind in {"OPTION_CONTRACT", "FUTURE_CONTRACT"} and "contract_multiplier" not in instrument:
        raise ValueError("MISSING_CONTRACT_MULTIPLIER")
    multiplier = exact_decimal(instrument.get("contract_multiplier", "1"), field_name="contract_multiplier")
    if multiplier <= 0:
        raise ValueError("INVALID_CONTRACT_MULTIPLIER")
    qty_unit = kind_default_quantity_unit(kind)

    price = _minor_to_decimal(_positive_integer(fill["fill_price_minor"], field_name="fill_price_minor"), price_scale)
    signed_qty = _signed_fill_quantity(fill, instrument)
    abs_qty = abs(signed_qty)

    # The legacy per-share policy is safe for fractional spot only when zero;
    # otherwise the simulator must stamp exact total costs on this fill.
    if (kind == "CRYPTO_PAIR" and abs_qty != abs_qty.to_integral_value()
            and not ("commission_minor" in fill and "fees_minor" in fill)
            and policy.get("commission_minor_per_share", 0) != 0):
        raise ValueError("COST_FRICTION_UNSET: fractional fill requires explicit costs")
    for field in ("commission_minor", "fees_minor"):
        if field in fill:
            amount = exact_decimal(fill[field], field_name=field)
            if amount < 0 or amount != amount.to_integral_value():
                raise ValueError("INVALID_COST_FRICTION")
    commission_minor, fees_minor = resolve_paper_cost_friction(
        fill=fill,
        policy=policy,
        quantity=int(abs_qty),
    )
    if commission_minor < 0 or fees_minor < 0:
        raise ValueError("INVALID_COST_FRICTION")
    fees = _minor_to_decimal(commission_minor + fees_minor, scale)

    existing = portfolio.get_position(instrument_id)
    position_before = existing.quantity if existing is not None else Decimal("0")
    realized_before = existing.realized_pnl_native if existing is not None else Decimal("0")
    cost_basis_before = existing.cost_basis if existing is not None else Decimal("0")
    avg_cost_before = existing.average_cost if existing is not None else None

    if existing is not None and (
        existing.instrument_kind != kind or existing.asset_class != asset_class
        or existing.native_currency != currency or existing.multiplier != multiplier
    ):
        raise ValueError("POSITION_ECONOMICS_MISMATCH")
    if kind in {"OPTION_CONTRACT", "FUTURE_CONTRACT", "CRYPTO_PAIR"}:
        if position_before < 0 or (signed_qty < 0 and abs_qty > position_before):
            raise ValueError("UNSUPPORTED_RISK_MODEL: short/oversell fill")
    if kind == "CRYPTO_PAIR":
        if currency != str(policy.get("currency", "USD")).upper() or currency != "USD":
            raise ValueError("UNSUPPORTED_SETTLEMENT_CURRENCY: spot requires funded USD")
        if multiplier != 1:
            raise ValueError("INVALID_CONTRACT_MULTIPLIER: spot multiplier must be one")

    cash_delta = Decimal("0")
    realized_delta = Decimal("0")
    reserved_margin_after = existing.reserved_margin_native if existing is not None else None

    if kind in {"TRADABLE_SECURITY", "ETF_FUND", "CRYPTO_PAIR"}:
        cash_delta = -(signed_qty * price) - fees
        if position_before == 0:
            realized_delta = -fees
        elif position_before > 0 and signed_qty < 0:
            closed = min(abs(signed_qty), position_before)
            closed_basis = (
                (cost_basis_before * closed / position_before)
                if position_before != 0
                else Decimal("0")
            )
            realized_delta = closed * price - closed_basis - fees
        elif position_before < 0 and signed_qty > 0:
            closed = min(signed_qty, abs(position_before))
            closed_basis = (
                (abs(cost_basis_before) * closed / abs(position_before))
                if position_before != 0
                else Decimal("0")
            )
            realized_delta = closed_basis - closed * price - fees
        else:
            realized_delta = -fees
        position_after = position_before + signed_qty
        if position_after == 0:
            cost_basis_after = Decimal("0")
            avg_cost_after = None
        elif (position_before >= 0 and signed_qty > 0) or (position_before <= 0 and signed_qty < 0):
            cost_basis_after = cost_basis_before + signed_qty * price
            avg_cost_after = abs(cost_basis_after / position_after) if position_after != 0 else None
        else:
            closed = min(abs(signed_qty), abs(position_before))
            retained = abs(cost_basis_before) - (
                abs(cost_basis_before) * closed / abs(position_before) if position_before != 0 else Decimal("0")
            )
            remaining = abs(position_after)
            if remaining == 0:
                cost_basis_after = Decimal("0")
                avg_cost_after = None
            elif abs(signed_qty) <= abs(position_before):
                cost_basis_after = (Decimal("1") if position_before > 0 else Decimal("-1")) * retained
                avg_cost_after = abs(cost_basis_after / position_after) if position_after != 0 else None
            else:
                cost_basis_after = position_after * price
                avg_cost_after = price

    elif kind == "OPTION_CONTRACT":
        premium = option_premium(abs_qty, price, multiplier)
        position_after = position_before + signed_qty
        if signed_qty > 0:
            cash_delta = -premium - fees
            realized_delta = -fees
            cost_basis_after = cost_basis_before + premium
        else:
            # Cost basis is total native premium; average_cost is the quote
            # per underlying unit, so the multiplier is applied exactly once.
            closed_basis = cost_basis_before * abs_qty / position_before
            realized_delta = premium - closed_basis - fees
            cash_delta = premium - fees
            cost_basis_after = cost_basis_before - closed_basis
        avg_cost_after = (cost_basis_after / (position_after * multiplier)
                          if position_after != 0 else None)

    elif kind == "FUTURE_CONTRACT":
        position_after = position_before + signed_qty
        if position_before > 0 and reserved_margin_after is None:
            raise ValueError("MARGIN_RESERVATION_MISSING: rebuild from opening fills")
        reserved_before = reserved_margin_after or Decimal("0")
        if signed_qty > 0:
            from ..risk.margin_facts import MarginRequirementFacts, admit_margin_facts

            margin_facts = fill.get("margin_facts") or (intent or {}).get("margin_facts")
            if margin_facts is None:
                raise ValueError("MARGIN_MISSING: every futures opening fill requires margin facts")
            facts = (margin_facts if isinstance(margin_facts, MarginRequirementFacts)
                     else MarginRequirementFacts.from_dict(margin_facts))
            admission = admit_margin_facts(facts, instrument_id=instrument_id,
                                          order_currency=currency,
                                          observation_time_ns=int(fill.get("fill_time", 0)))
            if not admission.admitted:
                raise ValueError(admission.code)
            # Never under-reserve a fractional settlement unit. This exact
            # recorded amount, including rounding, is what closing releases.
            margin_minor = int((facts.initial_margin_per_contract * abs_qty * Decimal(scale))
                               .to_integral_value(rounding=ROUND_CEILING))
            reserved = _minor_to_decimal(margin_minor, scale)
            if reserved <= 0:
                raise ValueError("MARGIN_INVALID: reservation below settlement precision")
            reserved_margin_after = reserved_before + reserved
            cash_delta = -reserved - fees
            realized_delta = -fees
            cost_basis_after = cost_basis_before + signed_qty * price
            avg_cost_after = cost_basis_after / position_after
        else:
            ref = avg_cost_before
            if ref is None:
                raise ValueError("INVALID_POSITION_ECONOMICS: futures entry basis missing")
            pnl = future_variation_pnl(abs_qty, multiplier, price, ref)
            released = (reserved_before if position_after == 0 else
                        reserved_before * abs_qty / position_before)
            reserved_margin_after = reserved_before - released
            realized_delta = pnl - fees
            cash_delta = pnl + released - fees
            cost_basis_after = (Decimal("0") if position_after == 0 else
                                cost_basis_before - cost_basis_before * abs_qty / position_before)
            avg_cost_after = avg_cost_before if position_after != 0 else None

    else:
        raise ValueError(f"UNSUPPORTED_INSTRUMENT_KIND:{kind}")

    if kind == "CRYPTO_PAIR" and signed_qty > 0:
        cash = next((balance.settled for balance in portfolio.cash_balances if balance.currency == currency),
                    Decimal("0"))
        if cash + cash_delta < 0:
            raise ValueError("INSUFFICIENT_SETTLEMENT_CURRENCY: spot cannot borrow")
    realized_after = realized_before + realized_delta
    position_input = PositionInput(
        instrument_id=instrument_id,
        asset_class=asset_class,
        instrument_kind=kind,
        quantity=position_after,
        quantity_unit=qty_unit,
        native_currency=currency,
        multiplier=multiplier,
        average_cost=avg_cost_after,
        cost_basis=cost_basis_after if position_after != 0 else Decimal("0"),
        realized_pnl_native=realized_after,
        source_time_ns=int(fill.get("fill_time", 0)),
        observed_at_ns=int(fill.get("fill_time", 0)),
        reserved_margin_native=reserved_margin_after,
    )
    portfolio.apply_fill_state(position_input, cash_delta)
    if applied_fill_ids is not None:
        applied_fill_ids.add(fill_id)

    return PaperFillResult(
        fill_id=fill_id,
        instrument_id=instrument_id,
        cash_delta_native=cash_delta,
        position_quantity_after=position_after,
        realized_pnl_delta_native=realized_delta,
    )


def rebuild_portfolio_from_fills(
    portfolio: CanonicalPortfolio,
    *,
    fills: list[tuple[Mapping[str, Any], Mapping[str, Any] | None]],
    policy: Mapping[str, Any],
    initial_cash_minor: int,
) -> None:
    """Replay fills into a fresh portfolio (idempotency / recovery)."""
    scale = int(policy.get("price_scale", 100))
    currency = str(policy.get("currency", "USD")).upper()
    portfolio.set_cash(
        CashBalance(currency=currency, settled=Decimal(initial_cash_minor) / Decimal(scale))
    )
    applied: set[str] = set()
    for fill, intent in fills:
        apply_paper_fill_to_portfolio(
            portfolio,
            fill=fill,
            intent=intent,
            policy=policy,
            applied_fill_ids=applied,
        )


__all__ = [
    "PaperFillResult",
    "apply_paper_fill_to_portfolio",
    "rebuild_portfolio_from_fills",
]
