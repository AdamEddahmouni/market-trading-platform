"""Normalize SEC FTD rows into canonical observations. Balance, not flow."""

from __future__ import annotations

from ..canonical import sha256_bytes, canonical_bytes
from ..short_intelligence.clocks import clocks_ftd
from ..short_intelligence.contracts import FailsToDeliverObservation, ObservationFamily
from ..short_intelligence.identity import SymbolMap
from .parser import FtdParsedArchive, FtdRawRow
from .periods import FtdPeriod, historical_coverage_flags, settlement_in_period


def parse_sec_price(raw: str) -> float | None:
    text = (raw or "").strip()
    if not text or text == ".":
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    if value <= 0.01:
        return None
    return value


def approx_ftd_notional_sec_price(balance: int, price: float | None) -> float | None:
    if price is None:
        return None
    return float(balance) * float(price)


def normalize_ftd_row(
    row: FtdRawRow,
    *,
    period: FtdPeriod,
    symbol_map: SymbolMap,
    observed_time: str,
    retrieved_time: str,
    source_file_id: str,
    content_hash: str,
    historical_backfill: bool = False,
) -> FailsToDeliverObservation:
    symbol = row.symbol.upper()
    settlement = row.settlement_date[:10]
    resolved = symbol_map.resolve(symbol, as_of=settlement)
    quality = list(historical_coverage_flags(settlement))
    if "IDENTITY_UNRESOLVED" in resolved.quality_flags:
        quality.append("IDENTITY_UNRESOLVED")
    price = parse_sec_price(row.previous_day_price_raw)
    if price is None:
        quality.append("PRICE_UNAVAILABLE")
    if historical_backfill:
        quality.append("PUBLICATION_TIME_UNCERTAIN")
    if not settlement_in_period(settlement, period):
        quality.append("PERIOD_MISMATCH")
    clocks = clocks_ftd(
        settlement_date=settlement,
        source_period_start=period.source_period_start,
        source_period_end=period.source_period_end,
        observed_time=observed_time,
        retrieved_time=retrieved_time,
    )
    if historical_backfill:
        clocks = dict(clocks)
        clocks["official_file_publication_time"] = ""
        clocks["publication_time_uncertain"] = "true"
    notional = approx_ftd_notional_sec_price(row.ftd_balance_quantity, price)
    return FailsToDeliverObservation(
        observation_family=ObservationFamily.FAILS_TO_DELIVER,
        instrument_id=resolved.instrument_id,
        raw_symbol=symbol,
        cusip=row.cusip,
        settlement_date=settlement,
        ftd_balance_quantity=row.ftd_balance_quantity,
        previous_day_price=price,
        approx_ftd_notional_sec_price=notional,
        issuer_description=row.issuer_description,
        source="sec_ftd",
        source_file_id=source_file_id,
        source_period=period.label,
        content_hash=content_hash,
        parser_version="sec_ftd.normalize/1.0.0",
        clocks=clocks,
        quality_flags=tuple(dict.fromkeys(quality)),
        raw_payload_hash=sha256_bytes(
            canonical_bytes(
                {
                    "cusip": row.cusip,
                    "settlement_date": settlement,
                    "symbol": symbol,
                    "ftd_balance_quantity": row.ftd_balance_quantity,
                }
            )
        ),
    )


def normalize_ftd_archive(
    parsed: FtdParsedArchive,
    *,
    period: FtdPeriod,
    symbol_map: SymbolMap,
    observed_time: str,
    retrieved_time: str,
    requested_symbols: tuple[str, ...] | None = None,
    historical_backfill: bool = False,
) -> tuple[FailsToDeliverObservation, ...]:
    wanted = {item.upper() for item in requested_symbols} if requested_symbols else None
    observations: list[FailsToDeliverObservation] = []
    for row in parsed.rows:
        if wanted is not None and row.symbol.upper() not in wanted:
            continue
        observations.append(
            normalize_ftd_row(
                row,
                period=period,
                symbol_map=symbol_map,
                observed_time=observed_time,
                retrieved_time=retrieved_time,
                source_file_id=parsed.period_key,
                content_hash=parsed.content_hash,
                historical_backfill=historical_backfill,
            )
        )
    return tuple(observations)


__all__ = [
    "approx_ftd_notional_sec_price",
    "normalize_ftd_archive",
    "normalize_ftd_row",
    "parse_sec_price",
]
