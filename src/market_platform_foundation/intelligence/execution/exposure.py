"""Portfolio exposure calculations (BUILD 22)."""

from __future__ import annotations

from .types import ExposureSnapshot, PaperPortfolioSnapshotV1, PaperPositionSnapshot


def signed_quantity(position: PaperPositionSnapshot) -> int:
    return position.quantity


def position_market_value(position: PaperPositionSnapshot) -> int:
    return abs(position.market_value_minor)


def compute_exposure(positions: tuple[PaperPositionSnapshot, ...]) -> ExposureSnapshot:
    gross = 0
    net = 0
    for position in positions:
        gross += abs(position.market_value_minor)
        if position.quantity >= 0:
            net += position.market_value_minor
        else:
            net -= position.market_value_minor
    return ExposureSnapshot(gross_exposure_minor=gross, net_exposure_minor=net)


def symbol_position_quantity(
    positions: tuple[PaperPositionSnapshot, ...],
    *,
    instrument_id: str,
) -> int:
    total = 0
    for position in positions:
        if position.instrument_id == instrument_id:
            total += position.quantity
    return total


def symbol_market_value_minor(
    positions: tuple[PaperPositionSnapshot, ...],
    *,
    instrument_id: str,
) -> int:
    total = 0
    for position in positions:
        if position.instrument_id == instrument_id:
            total += abs(position.market_value_minor)
    return total


def projected_positions_after_trade(
    positions: tuple[PaperPositionSnapshot, ...],
    *,
    instrument_id: str,
    symbol: str,
    side: str,
    quantity: int,
    reference_price_minor: int,
) -> tuple[PaperPositionSnapshot, ...]:
    signed_delta = quantity if side == "BUY" else -quantity
    current_qty = symbol_position_quantity(positions, instrument_id=instrument_id)
    projected_qty = current_qty + signed_delta
    rows: list[PaperPositionSnapshot] = []
    replaced = False
    for position in positions:
        if position.instrument_id != instrument_id:
            rows.append(position)
            continue
        replaced = True
        if projected_qty != 0:
            rows.append(
                PaperPositionSnapshot(
                    instrument_id=instrument_id,
                    symbol=symbol,
                    quantity=projected_qty,
                    market_value_minor=abs(projected_qty) * reference_price_minor,
                )
            )
    if not replaced and projected_qty != 0:
        rows.append(
            PaperPositionSnapshot(
                instrument_id=instrument_id,
                symbol=symbol,
                quantity=projected_qty,
                market_value_minor=abs(projected_qty) * reference_price_minor,
            )
        )
    return tuple(rows)


def snapshot_exposure(snapshot: PaperPortfolioSnapshotV1) -> ExposureSnapshot:
    if snapshot.exposure is not None:
        return snapshot.exposure
    return compute_exposure(snapshot.positions)


__all__ = [
    "compute_exposure",
    "position_market_value",
    "projected_positions_after_trade",
    "signed_quantity",
    "snapshot_exposure",
    "symbol_market_value_minor",
    "symbol_position_quantity",
]
