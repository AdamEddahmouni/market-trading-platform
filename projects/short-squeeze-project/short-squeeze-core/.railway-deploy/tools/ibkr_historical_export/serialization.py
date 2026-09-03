"""Deterministic JSONL / CSV serialization and hashing for captured bars.

The raw JSONL and CSV are two byte-deterministic representations of the same provider
response. Re-running serialization over the same bars yields identical bytes and hashes.
Provider numeric values are echoed verbatim (as captured); nothing is rounded.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
from collections.abc import Sequence

from .models import BarRecord

# Fixed CSV column order. The Batch 04 ColumnMappingProfile maps by header name, so this
# order affects only byte-determinism, not parsing.
CSV_COLUMNS: tuple[str, ...] = (
    "timestamp_utc", "open", "high", "low", "close", "volume", "wap",
    "bar_count", "timestamp_epoch", "requested_symbol", "request_name",
    "resolved_con_id",
)


def serialize_bars_jsonl(bars: Sequence[BarRecord]) -> bytes:
    """One compact JSON object per line, fixed key order, trailing newline per line."""
    lines: list[str] = []
    for bar in bars:
        lines.append(json.dumps(bar.as_dict(), ensure_ascii=True, separators=(",", ":")))
    text = "".join(line + "\n" for line in lines)
    return text.encode("utf-8")


def _csv_cell(value) -> str:
    return "" if value is None else str(value)


def serialize_bars_csv(bars: Sequence[BarRecord]) -> bytes:
    """CSV with a header row and one row per bar. ``\\n`` line terminator, UTF-8."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for bar in bars:
        record = bar.as_dict()
        writer.writerow([_csv_cell(record[column]) for column in CSV_COLUMNS])
    return buffer.getvalue().encode("utf-8")


def sha256_and_length(data: bytes) -> tuple[str, int]:
    """Return (hex SHA-256, byte length) for the exact bytes."""
    return hashlib.sha256(data).hexdigest(), len(data)


def canonical_json(payload) -> bytes:
    """Deterministic pretty JSON for private manifests (sorted keys)."""
    return (json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n").encode("utf-8")


__all__ = [
    "CSV_COLUMNS",
    "serialize_bars_jsonl",
    "serialize_bars_csv",
    "sha256_and_length",
    "canonical_json",
]
