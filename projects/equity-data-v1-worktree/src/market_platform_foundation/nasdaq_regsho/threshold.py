"""Parse Nasdaq Reg SHO threshold files. Status, not short interest, not FTD quantity."""

from __future__ import annotations

from dataclasses import dataclass

from ..canonical import sha256_bytes
from ..short_intelligence.clocks import clocks_threshold, nasdaq_file_timestamp_to_utc
from ..short_intelligence.contracts import ObservationFamily, ThresholdStatusObservation
from ..short_intelligence.identity import SymbolMap

PARSER_VERSION = "nasdaq_regsho.threshold/1.0.0"
LISTING_COVERAGE = "NASDAQ"
SOURCE_SRO = "NASDAQ"


@dataclass(frozen=True, slots=True)
class NasdaqThresholdFile:
    trade_date: str
    file_creation_time: str
    content_hash: str
    raw_text: str
    rows: tuple[dict[str, str], ...]


def parse_threshold_file(raw: bytes | str, *, trade_date: str) -> NasdaqThresholdFile:
    text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        raise ValueError("NASDAQ_THRESHOLD_EMPTY")
    stamp = ""
    data_lines: list[str] = []
    header_seen = False
    for line in lines:
        compact = line.replace("|", "").strip()
        if len(compact) == 14 and compact.isdigit():
            stamp = compact
            continue
        if line.lower().startswith("symbol|"):
            header_seen = True
            continue
        data_lines.append(line)
    if not stamp:
        raise ValueError("NASDAQ_THRESHOLD_TIMESTAMP_MISSING")
    rows: list[dict[str, str]] = []
    for line in data_lines:
        parts = [part.strip() for part in line.split("|")]
        while len(parts) < 5:
            parts.append("")
        rows.append(
            {
                "symbol": parts[0].upper(),
                "security_name": parts[1],
                "market_category": parts[2],
                "reg_sho_threshold_flag": parts[3].upper(),
                "rule_3210_flag": parts[4].upper() if parts[4] else "",
            }
        )
    if not header_seen:
        raise ValueError("NASDAQ_THRESHOLD_HEADER_MISSING")
    return NasdaqThresholdFile(
        trade_date=trade_date[:10],
        file_creation_time=nasdaq_file_timestamp_to_utc(stamp),
        content_hash=sha256_bytes(raw if isinstance(raw, bytes) else text.encode("utf-8")),
        raw_text=text,
        rows=tuple(rows),
    )


def normalize_threshold_file(
    parsed: NasdaqThresholdFile,
    *,
    symbol_map: SymbolMap,
    observed_time: str,
    retrieved_time: str,
    requested_symbols: tuple[str, ...] | None = None,
) -> tuple[ThresholdStatusObservation, ...]:
    wanted = {item.upper() for item in requested_symbols} if requested_symbols else None
    listed = {row["symbol"] for row in parsed.rows}
    symbols = wanted if wanted is not None else listed
    observations: list[ThresholdStatusObservation] = []
    clocks = clocks_threshold(
        trade_date=parsed.trade_date,
        file_creation_time=parsed.file_creation_time,
        observed_time=observed_time,
        retrieved_time=retrieved_time,
    )
    by_symbol = {row["symbol"]: row for row in parsed.rows}
    for symbol in sorted(symbols):
        row = by_symbol.get(symbol)
        currently = bool(row and row.get("reg_sho_threshold_flag") == "Y")
        resolved = symbol_map.resolve(symbol, as_of=parsed.trade_date)
        quality: list[str] = []
        if "IDENTITY_UNRESOLVED" in resolved.quality_flags:
            quality.append("IDENTITY_UNRESOLVED")
        quality.append("NASDAQ_COVERAGE_ONLY")
        quality.append("FTD_QUANTITY_UNKNOWN")
        observations.append(
            ThresholdStatusObservation(
                observation_family=ObservationFamily.THRESHOLD_STATUS,
                instrument_id=resolved.instrument_id,
                provider_symbol=symbol,
                trade_date=parsed.trade_date,
                currently_threshold=currently,
                source_sro=SOURCE_SRO,
                listing_coverage=LISTING_COVERAGE,
                market_category=str((row or {}).get("market_category") or ""),
                security_name=str((row or {}).get("security_name") or ""),
                rule_3210_flag=(row or {}).get("rule_3210_flag") or None,
                reg_sho_threshold_flag=(row or {}).get("reg_sho_threshold_flag") or ("Y" if currently else "N"),
                file_creation_time=parsed.file_creation_time,
                content_hash=parsed.content_hash,
                parser_version=PARSER_VERSION,
                clocks=clocks,
                quality_flags=tuple(dict.fromkeys(quality)),
                source_market="NASDAQ",
                source_file_or_request_id=f"nasdaq:{parsed.trade_date}",
            )
        )
    return tuple(observations)
