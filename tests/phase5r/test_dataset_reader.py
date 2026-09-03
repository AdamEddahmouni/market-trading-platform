"""Tests for bounded dataset projection reader (GridIQ PORT_ADAPT)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.canonical import sha256_bytes
from market_platform_foundation.research.dataset_reader import (
    DatasetProjectionSpec,
    DatasetReadError,
    projection_identity,
    read_json_array_projection,
    read_jsonl_projection,
)


class DatasetReaderTests(unittest.TestCase):
    def test_jsonl_projection_with_optional_columns(self) -> None:
        rows = [
            {"instrument_id": "BIYA", "value": "100"},
            {"instrument_id": "BIYA", "value": "101"},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rows.jsonl"
            path.write_text(
                "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
                encoding="utf-8",
            )
            spec = DatasetProjectionSpec(
                columns=("instrument_id", "value", "note"),
                schema_version="1.0.0",
                optional_columns=frozenset({"note"}),
            )
            result = read_jsonl_projection(path, spec)
            self.assertEqual(result.row_count, 2)
            self.assertEqual(result.rows[0]["note"], None)
            self.assertEqual(result.projected_columns, ("instrument_id", "value", "note"))

    def test_hash_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rows.jsonl"
            path.write_text('{"instrument_id":"BIYA","value":"1"}\n', encoding="utf-8")
            spec = DatasetProjectionSpec(columns=("instrument_id", "value"), schema_version="1.0.0")
            with self.assertRaises(DatasetReadError) as ctx:
                read_jsonl_projection(path, spec, expected_content_hash="000000")
            self.assertEqual(ctx.exception.reason_code, "DATASET_HASH_MISMATCH")

    def test_unknown_column_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rows.jsonl"
            path.write_text('{"instrument_id":"BIYA","value":"1","drift":"x"}\n', encoding="utf-8")
            spec = DatasetProjectionSpec(columns=("instrument_id", "value"), schema_version="1.0.0")
            with self.assertRaises(DatasetReadError) as ctx:
                read_jsonl_projection(path, spec)
            self.assertEqual(ctx.exception.reason_code, "SCHEMA_DRIFT_UNKNOWN_COLUMN")

    def test_byte_limit_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rows.jsonl"
            path.write_text('{"instrument_id":"BIYA","value":"1"}\n', encoding="utf-8")
            spec = DatasetProjectionSpec(
                columns=("instrument_id", "value"),
                schema_version="1.0.0",
                max_bytes=10,
            )
            with self.assertRaises(DatasetReadError) as ctx:
                read_jsonl_projection(path, spec)
            self.assertEqual(ctx.exception.reason_code, "DATASET_BYTE_LIMIT_EXCEEDED")

    def test_json_array_projection_identity_stable(self) -> None:
        payload = [{"instrument_id": "BIYA", "value": "42"}]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rows.json"
            path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
            spec = DatasetProjectionSpec(columns=("instrument_id", "value"), schema_version="1.0.0")
            content_hash = sha256_bytes(path.read_bytes())
            result = read_json_array_projection(path, spec, expected_content_hash=content_hash)
            identity_a = projection_identity(spec, result.content_hash)
            identity_b = projection_identity(spec, result.content_hash)
            self.assertEqual(identity_a, identity_b)
            self.assertEqual(result.rows[0]["value"], "42")


if __name__ == "__main__":
    unittest.main()
