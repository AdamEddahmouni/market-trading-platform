import json
import tempfile
import unittest
from pathlib import Path

from market_platform_foundation.canonical import (
    canonical_bytes,
    load_json_strict,
    sha256_bytes,
    write_canonical_json,
)


class CanonicalTests(unittest.TestCase):
    def test_recursive_key_order_and_utf8_lf(self):
        self.assertEqual(
            canonical_bytes({"z": {"b": 1, "a": 2}, "a": "é"}),
            b'{"a":"\xc3\xa9","z":{"a":2,"b":1}}\n',
        )

    def test_duplicate_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "duplicate.json"
            path.write_text('{"a":1,"a":2}\n', encoding="utf-8", newline="\n")
            with self.assertRaises(ValueError):
                load_json_strict(path)

    def test_writer_returns_file_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "value.json"
            digest = write_canonical_json(path, {"b": 2, "a": 1})
            self.assertEqual(digest, sha256_bytes(path.read_bytes()))
            self.assertEqual(
                json.loads(path.read_text(encoding="utf-8")), {"a": 1, "b": 2}
            )
