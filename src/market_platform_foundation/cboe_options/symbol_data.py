"""Parse exchange-specific Cboe options symbol data CSV snapshots."""

from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass

from .contracts import (
    CboeExchangeCode,
    CoverageScope,
    OptionContractActivitySnapshot,
    PitHistoryClass,
)
from .normalize import (
    normalize_option_type,
    parse_decimal_strike,
    parse_float,
    parse_int,
    parse_iso_timestamp,
    parse_trade_date,
)
from .quality import CboeOptionsQualityFlag, default_activity_flags
from .registry import CBOE_EXCHANGE_REGISTRY


@dataclass(frozen=True, slots=True)
class SymbolDataCapture:
    exchange: CboeExchangeCode
    snapshot_time: str
    content_hash: str
    snapshots: tuple[OptionContractActivitySnapshot, ...]


def _content_hash(body: str) -> str:
    return hashlib.sha256(body.encode("utf-8")).hexdigest().upper()


def _field_lookup(row: dict[str, str], *candidates: str) -> str:
    lowered = {key.lower().replace("_", " ").strip(): value for key, value in row.items()}
    for candidate in candidates:
        key = candidate.lower().replace("_", " ").strip()
        if key in lowered:
            return str(lowered[key]).strip()
    return ""


def _contract_id(
    *,
    exchange: CboeExchangeCode,
    underlying: str,
    expiration_date: str,
    strike: str,
    option_type: str,
    source_symbol: str,
) -> str:
    if source_symbol:
        return f"{exchange.value}:{source_symbol}"
    return f"{exchange.value}:{underlying}:{expiration_date}:{strike}:{option_type}"


def parse_symbol_data_csv(
    csv_text: str,
    *,
    exchange: CboeExchangeCode,
    retrieved_time: str,
    ingested_time: str,
    snapshot_time: str = "",
    source_artifact_id: str = "",
) -> SymbolDataCapture:
    """Exchange bid/ask are venue quotes — not NBBO or consolidated OPRA."""

    content_hash = _content_hash(csv_text)
    reader = csv.DictReader(io.StringIO(csv_text))
    if reader.fieldnames is None:
        raise ValueError("CBOE_SYMBOL_DATA_SCHEMA_CHANGED")

    exchange_entry = CBOE_EXCHANGE_REGISTRY[exchange]
    artifact_id = source_artifact_id or f"cboe_symbol_data_{exchange_entry.symbol_data_mkt_param}"
    parsed_snapshot = parse_iso_timestamp(snapshot_time) or ingested_time
    snapshots: list[OptionContractActivitySnapshot] = []

    for row in reader:
        underlying = _field_lookup(row, "Underlying", "underlying", "Root")
        expiration = parse_trade_date(
            _field_lookup(row, "Expiration Date", "expiration", "Exp Date", "expiration date")
        )
        strike = parse_decimal_strike(_field_lookup(row, "Strike", "strike", "Strike Price"))
        option_type = normalize_option_type(
            _field_lookup(row, "Call/Put", "call put", "option type", "type", "cp flag")
        )
        source_symbol = _field_lookup(
            row,
            "Option Symbol",
            "option symbol",
            "OSI Symbol",
            "symbol",
            "class",
        )
        description = _field_lookup(row, "Option Contract Description", "description")
        if not underlying and description:
            match = re.match(r"^([A-Z0-9.]+)", description.upper())
            underlying = match.group(1) if match else description[:12]

        snapshots.append(
            OptionContractActivitySnapshot(
                contract_id=_contract_id(
                    exchange=exchange,
                    underlying=underlying,
                    expiration_date=expiration,
                    strike=strike,
                    option_type=option_type,
                    source_symbol=source_symbol,
                ),
                exchange=exchange,
                snapshot_time=parsed_snapshot,
                available_time=ingested_time,
                coverage_scope=CoverageScope.EXCHANGE_SPECIFIC,
                underlying=underlying,
                expiration_date=expiration,
                strike=strike,
                option_type=option_type,
                source_symbol=source_symbol or description,
                volume=parse_int(_field_lookup(row, "Volume", "volume")),
                matched=parse_int(_field_lookup(row, "Matched", "matched")),
                routed=parse_int(_field_lookup(row, "Routed", "routed")),
                exchange_bid=parse_float(_field_lookup(row, "Bid", "bid", "Bid Price")),
                exchange_ask=parse_float(_field_lookup(row, "Ask", "ask", "Ask Price")),
                exchange_bid_size=parse_int(_field_lookup(row, "Bid Size", "bid size")),
                exchange_ask_size=parse_int(_field_lookup(row, "Ask Size", "ask size")),
                last_price=parse_float(_field_lookup(row, "Last", "last", "Last Price")),
                retrieved_time=retrieved_time,
                ingested_time=ingested_time,
                content_hash=content_hash,
                history_class=PitHistoryClass.CURRENT_SNAPSHOT_ONLY,
                quality_flags=(
                    *default_activity_flags(),
                    CboeOptionsQualityFlag.CURRENT_SNAPSHOT_ONLY.value,
                ),
                provenance_ref=f"cboe_options:symbol_data:{exchange.value}",
                predictive=False,
            )
        )

    return SymbolDataCapture(
        exchange=exchange,
        snapshot_time=parsed_snapshot,
        content_hash=content_hash,
        snapshots=tuple(snapshots),
    )


__all__ = ["SymbolDataCapture", "parse_symbol_data_csv"]
