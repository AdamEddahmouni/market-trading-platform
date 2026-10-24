"""Paper portfolio snapshot construction (BUILD 22)."""

from __future__ import annotations

from typing import Any
from decimal import Decimal, ROUND_CEILING
from ...paper.contracts import quantity_number

from ..contracts.common import INTELLIGENCE_SCHEMA_VERSION
from .exposure import compute_exposure
from .identity import derive_portfolio_snapshot_id
from .types import (
    PaperOpenOrderSnapshot,
    PaperPortfolioSnapshotV1,
    PaperPositionSnapshot,
)


def build_portfolio_snapshot(
    *,
    captured_at_ns: int,
    cash_minor: int,
    equity_minor: int,
    currency: str = "USD",
    price_scale: int = 100,
    positions: tuple[PaperPositionSnapshot, ...] = (),
    open_orders: tuple[PaperOpenOrderSnapshot, ...] = (),
    reserved_cash_minor: int = 0,
    realized_pnl_minor: int = 0,
    unrealized_pnl_minor: int = 0,
    start_of_day_equity_minor: int | None = None,
    peak_equity_minor: int | None = None,
    scenario_id: str | None = None,
    mode: str = "ACTUAL_LIVE",
    metadata: dict[str, Any] | None = None,
) -> PaperPortfolioSnapshotV1:
    exposure = compute_exposure(positions)
    body = PaperPortfolioSnapshotV1(
        snapshot_id="DERIVE",
        schema_version=INTELLIGENCE_SCHEMA_VERSION,
        captured_at_ns=captured_at_ns,
        cash_minor=cash_minor,
        equity_minor=equity_minor,
        currency=currency,
        price_scale=price_scale,
        positions=positions,
        open_orders=open_orders,
        reserved_cash_minor=reserved_cash_minor,
        exposure=exposure,
        realized_pnl_minor=realized_pnl_minor,
        unrealized_pnl_minor=unrealized_pnl_minor,
        start_of_day_equity_minor=start_of_day_equity_minor,
        peak_equity_minor=peak_equity_minor,
        scenario_id=scenario_id,
        mode=mode,
        metadata=dict(metadata or {}),
    )
    snapshot_id = derive_portfolio_snapshot_id(body)
    return PaperPortfolioSnapshotV1(
        snapshot_id=snapshot_id,
        schema_version=body.schema_version,
        captured_at_ns=body.captured_at_ns,
        cash_minor=body.cash_minor,
        equity_minor=body.equity_minor,
        currency=body.currency,
        price_scale=body.price_scale,
        positions=body.positions,
        open_orders=body.open_orders,
        reserved_cash_minor=body.reserved_cash_minor,
        exposure=body.exposure,
        realized_pnl_minor=body.realized_pnl_minor,
        unrealized_pnl_minor=body.unrealized_pnl_minor,
        start_of_day_equity_minor=body.start_of_day_equity_minor,
        peak_equity_minor=body.peak_equity_minor,
        scenario_id=body.scenario_id,
        mode=body.mode,
        metadata=body.metadata,
    )


def snapshot_from_paper_ledger(
    ledger: Any,
    *,
    captured_at_ns: int,
    start_of_day_equity_minor: int | None = None,
    scenario_id: str | None = None,
) -> PaperPortfolioSnapshotV1:
    account = ledger.project_account()
    cash_minor = int(account["cash_minor"])
    realized = int(account.get("realized_pnl_minor", 0))
    positions_raw = ledger.project_positions()
    positions: list[PaperPositionSnapshot] = []
    unrealized_total = 0
    for row in positions_raw:
        qty = quantity_number(row["quantity"])
        if str(row.get("side")) == "SHORT":
            qty = -qty
        mark = int(row.get("mark_minor") or row.get("average_fill_minor") or 0)
        if row.get("market_value_minor") is not None:
            market_value = abs(int(row["market_value_minor"]))
        else:
            unit_scale = Decimal(int(row.get("price_scale") or ledger.policy.get("price_scale", 100)))
            multiplier = Decimal(str(row.get("contract_multiplier", "1")))
            market_value = int((abs(Decimal(qty)) * mark * multiplier * Decimal(ledger.policy.get("price_scale", 100)) / unit_scale).to_integral_value(rounding=ROUND_CEILING)) if mark else int(row.get("notional_minor") or 0)
        if qty < 0:
            market_value = -market_value
        unrealized_total += int(row.get("unrealized_pnl_minor") or 0)
        positions.append(
            PaperPositionSnapshot(
                instrument_id=str(row["instrument_id"]),
                symbol=str(row.get("symbol", "UNKNOWN")),
                quantity=qty,
                market_value_minor=abs(market_value),
            )
        )
    equity_minor = cash_minor + sum(pos.market_value_minor if pos.quantity > 0 else -pos.market_value_minor for pos in positions)

    open_orders: list[PaperOpenOrderSnapshot] = []
    for order in ledger.project_orders():
        state = str(order.get("state", ""))
        if state in {"FILLED", "CANCELLED", "REJECTED", "EXPIRED", "RISK_REJECTED"}:
            continue
        open_orders.append(
            PaperOpenOrderSnapshot(
                order_id=str(order["order_id"]),
                instrument_id=str(order.get("instrument_id", ledger._primary_instrument_id())),
                side=str(order.get("side", "BUY")),
                quantity=quantity_number(order.get("working_remaining") or order.get("quantity") or order.get("desired_quantity") or 0),
                opportunity_id=(order.get("metadata") or {}).get("opportunity_id"),
            )
        )

    return build_portfolio_snapshot(
        captured_at_ns=captured_at_ns,
        cash_minor=cash_minor,
        equity_minor=equity_minor,
        reserved_cash_minor=int(account.get("reserved_cash_minor", 0)),
        currency=str(account.get("currency", "USD")),
        price_scale=int(ledger.policy.get("price_scale", 100)),
        positions=tuple(positions),
        open_orders=tuple(open_orders),
        realized_pnl_minor=realized,
        unrealized_pnl_minor=unrealized_total,
        start_of_day_equity_minor=start_of_day_equity_minor,
        scenario_id=scenario_id,
        mode=str(ledger.data_mode),
        metadata={
            "paper_account_id": account.get("paper_account_id"),
            "session_id": account.get("session_id"),
        },
    )


__all__ = ["build_portfolio_snapshot", "snapshot_from_paper_ledger"]
