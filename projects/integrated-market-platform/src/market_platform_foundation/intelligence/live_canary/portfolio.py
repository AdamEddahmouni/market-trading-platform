"""Live portfolio snapshot for safety/reconciliation only (BUILD 29)."""

from __future__ import annotations

from .identity import derive_account_fingerprint, derive_portfolio_snapshot_id
from .types import LIVE_CANARY_SCHEMA_VERSION, LivePortfolioSnapshotV1


def build_live_portfolio_snapshot(
    *,
    as_of_ns: int,
    broker: str,
    account_ref: str,
    cash_minor: int,
    positions: tuple[dict[str, object], ...] = (),
    open_orders: tuple[dict[str, object], ...] = (),
    known_fills: tuple[dict[str, object], ...] = (),
) -> LivePortfolioSnapshotV1:
    gross = 0
    net = 0
    for pos in positions:
        qty = int(pos.get("quantity", 0))
        price = int(pos.get("price_minor", 0))
        exposure = abs(qty * price)
        gross += exposure
        net += qty * price

    snapshot = LivePortfolioSnapshotV1(
        snapshot_id="",
        schema_version=LIVE_CANARY_SCHEMA_VERSION,
        as_of_ns=as_of_ns,
        broker=broker,
        account_ref=account_ref,
        account_fingerprint=derive_account_fingerprint(account_ref),
        cash_minor=cash_minor,
        positions=positions,
        open_orders=open_orders,
        known_fills=known_fills,
        gross_exposure_minor=gross,
        net_exposure_minor=net,
    )
    object.__setattr__(snapshot, "snapshot_id", derive_portfolio_snapshot_id(snapshot))
    return snapshot


def is_flat_for_scope(
    snapshot: LivePortfolioSnapshotV1,
    *,
    allowed_instruments: tuple[str, ...],
) -> bool:
    for pos in snapshot.positions:
        instrument = str(pos.get("instrument_id", ""))
        qty = int(pos.get("quantity", 0))
        if instrument in allowed_instruments and qty != 0:
            return False
    for order in snapshot.open_orders:
        instrument = str(order.get("instrument_id", ""))
        if instrument in allowed_instruments:
            return False
    return True
