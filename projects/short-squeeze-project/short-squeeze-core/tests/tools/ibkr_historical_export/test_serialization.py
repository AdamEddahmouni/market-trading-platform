"""Deterministic JSONL/CSV serialization and hashing."""

from __future__ import annotations

import json

from tools.ibkr_historical_export.serialization import (
    CSV_COLUMNS,
    canonical_json,
    serialize_bars_csv,
    serialize_bars_jsonl,
    sha256_and_length,
)

from ._fakes import make_bar

BARS = [
    make_bar("XNCR", "DETECTION_CONTEXT_PRECEDING_24H", 111, 1_784_000_000,
             timestamp_utc="2026-07-17T13:38:00Z"),
    make_bar("XNCR", "DETECTION_CONTEXT_PRECEDING_24H", 111, 1_784_000_060,
             timestamp_utc="2026-07-17T13:39:00Z", volume=None, wap=None),
]


def test_jsonl_is_deterministic():
    assert serialize_bars_jsonl(BARS) == serialize_bars_jsonl(BARS)


def test_csv_is_deterministic():
    assert serialize_bars_csv(BARS) == serialize_bars_csv(BARS)


def test_csv_header_and_newlines():
    text = serialize_bars_csv(BARS).decode("utf-8")
    lines = text.split("\n")
    assert lines[0] == ",".join(CSV_COLUMNS)
    assert "\r" not in text  # LF only
    assert len(lines) == 4  # header + 2 rows + trailing empty


def test_none_volume_wap_render_empty():
    text = serialize_bars_csv(BARS).decode("utf-8")
    second_row = text.split("\n")[2].split(",")
    # volume + wap columns are empty for the second bar
    header = CSV_COLUMNS
    assert second_row[header.index("volume")] == ""
    assert second_row[header.index("wap")] == ""


def test_jsonl_values_preserved_verbatim():
    line = serialize_bars_jsonl(BARS[:1]).decode("utf-8").strip()
    payload = json.loads(line)
    assert payload["open"] == "10.0"
    assert payload["volume"] == "1000"
    assert payload["bar_count"] == 42


def test_empty_bar_sets_serialize():
    assert serialize_bars_jsonl([]) == b""
    csv_bytes = serialize_bars_csv([])
    assert csv_bytes.decode("utf-8") == ",".join(CSV_COLUMNS) + "\n"


def test_hash_matches_written_bytes():
    data = serialize_bars_csv(BARS)
    sha, length = sha256_and_length(data)
    assert length == len(data)
    assert sha == sha256_and_length(data)[0]


def test_no_account_identifier_fields_in_output():
    text = (serialize_bars_jsonl(BARS) + serialize_bars_csv(BARS)).decode("utf-8").lower()
    for token in ("account", "acct", "portfolio", "balance", "position"):
        assert token not in text


def test_canonical_json_sorted_and_trailing_newline():
    out = canonical_json({"b": 1, "a": 2})
    text = out.decode("utf-8")
    assert text.endswith("\n")
    assert text.index('"a"') < text.index('"b"')
