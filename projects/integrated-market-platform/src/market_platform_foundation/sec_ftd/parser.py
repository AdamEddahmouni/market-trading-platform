"""Parse SEC FTD pipe-delimited archives. Balance outstanding, not daily flow."""

from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass

from ..canonical import sha256_bytes

PARSER_VERSION = "sec_ftd.parser/1.0.0"
EXPECTED_HEADER = (
    "SETTLEMENT DATE",
    "CUSIP",
    "SYMBOL",
    "QUANTITY (FAILS)",
    "DESCRIPTION",
    "PRICE",
)


@dataclass(frozen=True, slots=True)
class FtdRawRow:
    settlement_date: str
    cusip: str
    symbol: str
    ftd_balance_quantity: int
    issuer_description: str
    previous_day_price_raw: str


@dataclass(frozen=True, slots=True)
class FtdParsedArchive:
    period_key: str
    member_name: str
    content_hash: str
    record_count: int
    rows: tuple[FtdRawRow, ...]
    parser_version: str = PARSER_VERSION


def parse_archive_bytes(content: bytes, *, period_key: str) -> FtdParsedArchive:
    content_hash = sha256_bytes(content)
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        members = archive.namelist()
        if not members:
            raise ValueError("SEC_FTD_ZIP_EMPTY")
        member = members[0]
        text = archive.read(member).decode("utf-8", errors="replace")
    rows = parse_text_rows(text)
    return FtdParsedArchive(
        period_key=period_key,
        member_name=member,
        content_hash=content_hash,
        record_count=len(rows),
        rows=tuple(rows),
    )


def parse_text_rows(text: str) -> list[FtdRawRow]:
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        raise ValueError("SEC_FTD_TEXT_EMPTY")
    reader = csv.reader(lines, delimiter="|")
    header = next(reader)
    normalized_header = tuple(item.strip().upper() for item in header)
    if normalized_header != EXPECTED_HEADER:
        raise ValueError(f"SEC_FTD_HEADER_UNEXPECTED:{normalized_header}")
    rows: list[FtdRawRow] = []
    for line_no, parts in enumerate(reader, start=2):
        while len(parts) < 6:
            parts.append("")
        if not parts[0].strip() or parts[0].strip().lower().startswith("trailer"):
            continue
        settlement = _normalize_settlement(parts[0].strip())
        cusip = parts[1].strip().upper()
        symbol = parts[2].strip().upper()
        quantity = _parse_quantity(parts[3].strip(), line_no=line_no)
        description = parts[4].strip()
        price_raw = parts[5].strip()
        if not settlement or not cusip:
            raise ValueError(f"SEC_FTD_ROW_MALFORMED:{line_no}")
        rows.append(
            FtdRawRow(
                settlement_date=settlement,
                cusip=cusip,
                symbol=symbol,
                ftd_balance_quantity=quantity,
                issuer_description=description,
                previous_day_price_raw=price_raw,
            )
        )
    return rows


def _normalize_settlement(value: str) -> str:
    text = value.strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[0:4]}-{text[4:6]}-{text[6:8]}"
    if len(text) >= 10 and text[4] == "-" and text[7] == "-":
        return text[:10]
    return text


def _parse_quantity(value: str, *, line_no: int) -> int:
    if not value:
        raise ValueError(f"SEC_FTD_QUANTITY_MISSING:{line_no}")
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"SEC_FTD_QUANTITY_INVALID:{line_no}") from exc


__all__ = [
    "EXPECTED_HEADER",
    "FtdParsedArchive",
    "FtdRawRow",
    "PARSER_VERSION",
    "parse_archive_bytes",
    "parse_text_rows",
]
