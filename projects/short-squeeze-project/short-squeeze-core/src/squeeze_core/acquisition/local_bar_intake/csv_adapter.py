"""Deterministic delimited-text (CSV) parsing driven by an explicit profile.

The adapter assumes no single provider's column names: every column is resolved
through the mapping profile. One physical line is one bar record (embedded
newlines inside quoted fields are not supported), so ``source_row_number`` is
always the true 1-based physical line in the raw artifact and provenance survives
any later sorting.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass

from .models import ColumnMappingProfile
from .semantics import SUPPORTED_ENCODINGS, IntakeReasonCode


@dataclass(frozen=True, slots=True)
class ParsedRow:
    source_row_number: int
    cells: dict[str, str]


@dataclass(frozen=True, slots=True)
class ParseOutcome:
    rows: tuple[ParsedRow, ...]
    reason: IntakeReasonCode | None = None


def _decode(raw_bytes: bytes, encoding: str) -> str | None:
    if encoding.lower() not in SUPPORTED_ENCODINGS:
        return None
    try:
        return raw_bytes.decode(encoding)
    except (UnicodeDecodeError, LookupError):
        return None


def _split_line(line: str, delimiter: str) -> list[str]:
    return next(csv.reader([line], delimiter=delimiter))


def parse_delimited_rows(raw_bytes: bytes, profile: ColumnMappingProfile) -> ParseOutcome:
    text = _decode(raw_bytes, profile.encoding)
    if text is None:
        return ParseOutcome(rows=(), reason=IntakeReasonCode.UNSUPPORTED_ENCODING)

    header: list[str] | None = None
    rows: list[ParsedRow] = []
    for physical_index, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        fields = _split_line(line, profile.delimiter)
        if profile.has_header and header is None:
            header = [name.strip() for name in fields]
            continue
        if header is not None:
            cells = {
                header[index]: fields[index]
                for index in range(min(len(header), len(fields)))
            }
        else:
            # Headerless: expose positional keys "col0", "col1", ... so the profile
            # can map by position.
            cells = {f"col{index}": value for index, value in enumerate(fields)}
        rows.append(ParsedRow(source_row_number=physical_index, cells=cells))

    return ParseOutcome(rows=tuple(rows))


__all__ = ["ParsedRow", "ParseOutcome", "parse_delimited_rows"]
