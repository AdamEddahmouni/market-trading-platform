"""Paper ledger -> canonical portfolio snapshot adapter (G2 dual-run).

The legacy fill-driven equity ledger (``portfolio.ledger`` /
``paper.ledger``) remains the parity baseline and continues to own Paper
execution semantics. This adapter provides a read-side canonical projection
of the same truth so the canonical multi-asset model can consume Paper state
without changing Paper behavior (BL-0105 migration strategy: introduce
canonical model alongside, verify parity, migrate later).

Parity contract: for a pure-equity Paper ledger, the canonical snapshot's
position quantity, average cost, realized P&L, and market value must agree
exactly (after int-minor -> Decimal conversion) with the Paper projections.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from .canonical import (
    CashBalance,
    MarkDataStatus,
    MarkType,
    PortfolioKey,
    PortfolioPosition,
    PortfolioSnapshot,
    PositionInput,
    PositionValuation,
    QuantityUnit,
    ValuationMark,
    ValuationStatus,
)
from .instrument_economics import kind_default_quantity_unit


def _minor_to_decimal(value: int, scale: int) -> Decimal:
    return Decimal(value) / Decimal(scale)


def paper_snapshot_to_canonical(
    ledger: Any,
    *,
    base_currency: str | None = None,
) -> PortfolioSnapshot:
    """Build a canonical snapshot from a ``PaperExecutionLedger`` projection.

    Uses only the ledger's public projection surface (``project_account``,
    ``project_positions``, ``policy``), so the adapter stays a pure read-side
    consumer. Paper remains authoritative for its own state; the canonical
    snapshot is a derived, deterministic projection.
    """
    from ..paper.ledger import PaperExecutionLedger

    if not isinstance(ledger, PaperExecutionLedger):
        raise TypeError("expected PaperExecutionLedger")

    account = ledger.project_account()
    positions_projection = ledger.project_positions()
    scale = int(ledger.policy.get("price_scale", 100))
    currency = str(account.get("currency", "USD")).upper()
    cash_minor = int(account.get("cash_minor", 0))
    canonical_cash: tuple[CashBalance, ...] = ()
    if ledger._uses_canonical_authority():
        canonical_cash = tuple(ledger.canonical_portfolio.cash_balances)

    key = PortfolioKey(
        account_id=ledger.paper_account_id,
        mode="PAPER",
        broker="internal.simulation",
        portfolio_id=ledger.paper_account_id,
        environment="local",
    )

    cash_balances = canonical_cash or (
        CashBalance(
            currency=currency,
            settled=_minor_to_decimal(cash_minor, scale),
        ),
    )

    positions: list[PortfolioPosition] = []
    for row in positions_projection:
        instrument_id = str(row.get("instrument_id") or row.get("symbol") or "UNKNOWN")
        quantity = Decimal(int(row.get("quantity", 0)))
        instrument_kind = str(row.get("instrument_kind", "TRADABLE_SECURITY")).upper()
        asset_class = str(row.get("asset_class", "EQUITY")).upper()
        quantity_unit = kind_default_quantity_unit(instrument_kind)
        if row.get("quantity_unit"):
            try:
                quantity_unit = QuantityUnit(str(row["quantity_unit"]))
            except ValueError:
                quantity_unit = kind_default_quantity_unit(instrument_kind)
        average_cost = (
            _minor_to_decimal(int(row["average_fill_minor"]), scale)
            if row.get("average_fill_minor") is not None
            else None
        )
        cost_basis = (
            average_cost * abs(quantity) if average_cost is not None else None
        )
        mark_minor = row.get("mark_minor")
        mark: ValuationMark | None = None
        if mark_minor is not None:
            mark = ValuationMark(
                instrument_id=instrument_id,
                price=_minor_to_decimal(int(mark_minor), scale),
                currency=currency,
                mark_type=MarkType.LAST,
                source=str(row.get("mark_source") or row.get("mark_provider") or "INTERNAL"),
                source_time_ns=int(row.get("mark_as_of_ns") or 0),
                observed_at_ns=int(row.get("mark_as_of_ns") or 0),
                data_status=MarkDataStatus.FRESH
                if str(row.get("mark_quality", "PASS")) != "STALE"
                else MarkDataStatus.STALE,
            )
        unrealized = (
            _minor_to_decimal(int(row["unrealized_pnl_minor"]), scale)
            if row.get("unrealized_pnl_minor") is not None
            else None
        )
        market_value = (
            quantity * mark.price if mark is not None else None
        )
        valuation = PositionValuation(
            market_value_native=market_value,
            unrealized_pnl_native=unrealized,
            notional_native=None,
            reference_price=None,
            valuation_status=(
                ValuationStatus.COMPLETE
                if mark is not None
                else ValuationStatus.MISSING_MARK
            ),
            mark=mark,
        )
        positions.append(
            PortfolioPosition(
                instrument_id=instrument_id,
                asset_class=asset_class,
                instrument_kind=instrument_kind,
                quantity=quantity,
                quantity_unit=quantity_unit,
                native_currency=str(row.get("currency") or currency).upper(),
                average_cost=average_cost,
                cost_basis=cost_basis,
                realized_pnl_native=_minor_to_decimal(
                    int(account.get("realized_pnl_minor", 0)), scale
                ),
                source_time_ns=int(row.get("mark_as_of_ns") or 0),
                observed_at_ns=int(row.get("mark_as_of_ns") or 0),
                data_status=str(row.get("mark_quality", "PASS")),
                valuation=valuation,
            )
        )

    native_totals: dict[str, Decimal] = {}
    if cash_balances:
        native_totals[currency] = cash_balances[0].settled
    for position in positions:
        valuation = position.valuation
        if valuation is not None and valuation.market_value_native is not None:
            native_totals[currency] = (
                native_totals.get(currency, Decimal("0"))
                + valuation.market_value_native
            )

    return PortfolioSnapshot(
        key=key,
        base_currency=base_currency,
        cash_balances=tuple(cash_balances),
        positions=tuple(positions),
        native_totals=native_totals,
        base_currency_totals={},
        valuation_status=(
            ValuationStatus.COMPLETE
            if all(
                position.valuation is not None
                and position.valuation.mark is not None
                for position in positions
            )
            else (
                ValuationStatus.MISSING_MARK
                if positions
                else ValuationStatus.COMPLETE
            )
        ),
        source_time_ns=0,
        observed_at_ns=0,
        provider="PAPER_LEDGER",
    )


def paper_position_input(ledger: Any) -> PositionInput | None:
    """Canonical ``PositionInput`` for a Paper ledger's single primary position.

    Used by tests to drive ``CanonicalPortfolio.upsert_position`` from Paper
    state (dual-run path). Returns None when Paper holds no position.
    """
    positions_projection = ledger.project_positions()
    if not positions_projection:
        return None
    row = positions_projection[0]
    scale = int(ledger.policy.get("price_scale", 100))
    instrument_id = str(row.get("instrument_id") or row.get("symbol") or "UNKNOWN")
    quantity = Decimal(int(row.get("quantity", 0)))
    average_cost = (
        _minor_to_decimal(int(row["average_fill_minor"]), scale)
        if row.get("average_fill_minor") is not None
        else None
    )
    return PositionInput(
        instrument_id=instrument_id,
        asset_class="EQUITY",
        instrument_kind="TRADABLE_SECURITY",
        quantity=quantity,
        quantity_unit=QuantityUnit.SHARES,
        native_currency=str(ledger.policy.get("currency", "USD")).upper(),
        average_cost=average_cost,
        cost_basis=average_cost * abs(quantity) if average_cost is not None else None,
        realized_pnl_native=_minor_to_decimal(
            int(ledger.project_account().get("realized_pnl_minor", 0)), scale
        ),
    )


__all__ = [
    "paper_position_input",
    "paper_snapshot_to_canonical",
]