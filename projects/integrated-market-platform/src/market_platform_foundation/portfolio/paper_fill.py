"""Canonical Paper fill → CanonicalPortfolio mutation (G13).

One authoritative accounting path for Paper fills across equities, options,
and futures. Uses G4 ``portfolio.accounting`` formulas (exact Decimal) and
writes into ``CanonicalPortfolio`` — never a parallel options/futures ledger.

Legacy ``portfolio.ledger.apply_fill`` remains a compatibility projection for
equity-only replay parity; derivative fills route here exclusively.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping

from .accounting import (
    exact_decimal,
    future_variation_pnl,
    option_premium,
    realized_pnl_on_close,
)
from .canonical import CanonicalPortfolio, CashBalance, PositionInput, QuantityUnit
from .instrument_economics import kind_default_quantity_unit


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


def _signed_fill_quantity(fill: Mapping[str, Any]) -> Decimal:
    qty = Decimal(int(fill["fill_quantity"]))
    direction = str(fill.get("direction", "long")).lower()
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
        applied_fill_ids.add(fill_id)

    instrument = _instrument_from_fill(fill, intent)
    kind = str(instrument.get("instrument_kind", "TRADABLE_SECURITY")).upper()
    asset_class = str(instrument.get("asset_class", "EQUITY")).upper()
    instrument_id = str(instrument.get("instrument_id") or fill.get("instrument_id", "UNKNOWN"))
    currency = str(instrument.get("currency") or policy.get("currency", "USD")).upper()
    scale = int(policy.get("price_scale", 100))
    multiplier = exact_decimal(instrument.get("contract_multiplier", "1"), field_name="contract_multiplier")
    qty_unit = kind_default_quantity_unit(kind)

    price = _minor_to_decimal(int(fill["fill_price_minor"]), scale)
    signed_qty = _signed_fill_quantity(fill)
    abs_qty = abs(signed_qty)

    commission_minor = (
        int(fill["commission_minor"])
        if "commission_minor" in fill
        else int(abs_qty) * int(policy.get("commission_minor_per_share", 0))
    )
    fees_minor = (
        int(fill["fees_minor"])
        if "fees_minor" in fill
        else int(policy.get("fee_minor_per_order", 0))
    )
    fees = _minor_to_decimal(commission_minor + fees_minor, scale)

    existing = portfolio.get_position(instrument_id)
    position_before = existing.quantity if existing is not None else Decimal("0")
    realized_before = existing.realized_pnl_native if existing is not None else Decimal("0")
    cost_basis_before = existing.cost_basis if existing is not None else Decimal("0")
    avg_cost_before = existing.average_cost if existing is not None else None

    cash_delta = Decimal("0")
    realized_delta = Decimal("0")

    if kind in {"TRADABLE_SECURITY", "ETF_FUND"}:
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
        if signed_qty > 0:
            cash_delta = -premium - fees
            realized_delta = -fees
        else:
            if position_before <= 0:
                raise ValueError("UNSUPPORTED_RISK_MODEL: naked short option fill")
            closed = min(abs_qty, position_before)
            pnl = realized_pnl_on_close(
                instrument_kind=kind,
                entry_price=avg_cost_before or price,
                exit_price=price,
                quantity=closed,
                multiplier=multiplier,
            )
            realized_delta = (pnl or Decimal("0")) - fees
            cash_delta = premium - fees
        position_after = position_before + signed_qty
        if position_after == 0:
            cost_basis_after = Decimal("0")
            avg_cost_after = None
        elif position_before == 0 or (position_before > 0 and signed_qty > 0):
            prior_cost = cost_basis_before if position_before != 0 else Decimal("0")
            cost_basis_after = prior_cost + premium if signed_qty > 0 else prior_cost
            avg_cost_after = cost_basis_after / position_after if position_after != 0 else price
        else:
            cost_basis_after = position_after * (avg_cost_before or price) if position_after != 0 else Decimal("0")
            avg_cost_after = avg_cost_before

    elif kind == "FUTURE_CONTRACT":
        margin_facts = fill.get("margin_facts") or (intent or {}).get("margin_facts")
        if signed_qty > 0 and position_before == 0:
            if margin_facts is None:
                raise ValueError("MARGIN_MISSING: futures open requires margin facts")
            from ..risk.margin_facts import MarginRequirementFacts, required_margin_minor

            facts = (
                margin_facts
                if isinstance(margin_facts, MarginRequirementFacts)
                else MarginRequirementFacts.from_dict(margin_facts)
            )
            margin_minor = required_margin_minor(facts=facts, contracts=int(abs_qty), scale=scale)
            cash_delta = -_minor_to_decimal(margin_minor, scale) - fees
            realized_delta = -fees
        elif signed_qty < 0 and position_before > 0:
            closed = min(abs_qty, position_before)
            ref = avg_cost_before or price
            pnl = future_variation_pnl(closed, multiplier, price, ref)
            realized_delta = pnl - fees
            cash_delta = pnl - fees
            if margin_facts := fill.get("margin_facts") or (intent or {}).get("margin_facts"):
                from ..risk.margin_facts import MarginRequirementFacts, required_margin_minor

                facts = (
                    margin_facts
                    if isinstance(margin_facts, MarginRequirementFacts)
                    else MarginRequirementFacts.from_dict(margin_facts)
                )
                released = required_margin_minor(facts=facts, contracts=int(closed), scale=scale)
                cash_delta += _minor_to_decimal(released, scale)
        elif signed_qty > 0 and position_before > 0:
            cash_delta = -fees
            realized_delta = -fees
        else:
            raise ValueError("UNSUPPORTED_RISK_MODEL: futures short open without margin model")
        position_after = position_before + signed_qty
        if position_after == 0:
            cost_basis_after = Decimal("0")
            avg_cost_after = None
        elif position_before == 0:
            cost_basis_after = position_after * price
            avg_cost_after = price
        elif (position_before > 0 and signed_qty > 0) or (position_before < 0 and signed_qty < 0):
            prior_notional = position_before * (avg_cost_before or price)
            cost_basis_after = prior_notional + signed_qty * price
            avg_cost_after = cost_basis_after / position_after if position_after != 0 else price
        else:
            cost_basis_after = position_after * price if position_after != 0 else Decimal("0")
            avg_cost_after = price if position_after != 0 else None

    else:
        raise ValueError(f"UNSUPPORTED_INSTRUMENT_KIND:{kind}")

    portfolio.apply_cash(currency, cash_delta, source_time_ns=int(fill.get("fill_time", 0)))
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
    )
    portfolio.upsert_position(position_input)

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
