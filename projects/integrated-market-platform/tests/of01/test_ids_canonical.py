from __future__ import annotations

import unittest
from pathlib import Path

from market_platform_foundation.canonical import load_json_strict
from market_platform_foundation.of01.canonical import (
    canonical_command_bytes,
    canonical_commit_bytes,
    canonical_record_bytes,
    command_hash_from_obj,
    commit_hash_from_obj,
    record_hash_from_obj,
    sha256_upper,
)
from market_platform_foundation.of01.errors import OF01Error
from market_platform_foundation.of01.ids import validate_imported_uuid5, validate_uuid

FIXTURE = Path(__file__).parent / "fixtures" / "golden_v1.json"


class TestIds(unittest.TestCase):
    def test_uuid_requires_lowercase_canonical_v4(self) -> None:
        self.assertEqual(
            validate_uuid("11111111-1111-4111-8111-111111111111", field="run_id"),
            "11111111-1111-4111-8111-111111111111",
        )
        for bad in (
            "",
            "{11111111-1111-4111-8111-111111111111}",
            "11111111111141118111111111111111",
            "AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA",
        ):
            with self.subTest(bad=bad):
                with self.assertRaises(OF01Error):
                    validate_uuid(bad, field="run_id")

    def test_uuid5_requires_declared_import_context(self) -> None:
        with self.assertRaises(OF01Error):
            validate_uuid("6ba7b811-9dad-51d1-80b4-00c04fd430c8", field="run_id")
        with self.assertRaises(OF01Error):
            validate_imported_uuid5(
                "6ba7b811-9dad-51d1-80b4-00c04fd430c8",
                field="run_id",
                namespace_id="11111111-1111-4111-8111-111111111111",
                provenance_qualifier="NATIVE",
            )

    def test_ledger_identity_accepts_uuid5_for_import_records(self) -> None:
        from market_platform_foundation.of01.ids import validate_ledger_identity

        self.assertEqual(
            validate_ledger_identity("6ba7b811-9dad-51d1-80b4-00c04fd430c8", field="run_id"),
            "6ba7b811-9dad-51d1-80b4-00c04fd430c8",
        )


class TestGoldenVectors(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = load_json_strict(FIXTURE)
        assert isinstance(cls.fixture, dict)

    def test_command_vector_is_exact(self) -> None:
        command = self.fixture["command"]
        data = canonical_command_bytes(command)
        self.assertEqual(len(data), self.fixture["command_byte_length"])
        self.assertEqual(data[-1], 0x0A)
        self.assertEqual(sha256_upper(data), self.fixture["command_hash"])
        self.assertEqual(command_hash_from_obj(command), self.fixture["command_hash"])

    def test_run_record_vector_is_exact(self) -> None:
        record = self.fixture["run_record"]
        data = canonical_record_bytes(record)
        self.assertEqual(len(data), self.fixture["record_byte_length"])
        self.assertEqual(data[-1], 0x0A)
        self.assertEqual(sha256_upper(data), self.fixture["record_hash"])
        self.assertEqual(record_hash_from_obj(record), self.fixture["record_hash"])

    def test_transition_record_vector_is_exact(self) -> None:
        record = self.fixture["transition_record"]
        data = canonical_record_bytes(record)
        self.assertEqual(len(data), self.fixture["transition_byte_length"])
        self.assertEqual(data[-1], 0x0A)
        self.assertEqual(sha256_upper(data), self.fixture["transition_hash"])
        self.assertEqual(record_hash_from_obj(record), self.fixture["transition_hash"])

    def test_commit_vector_is_exact(self) -> None:
        commit = self.fixture["commit"]
        data = canonical_commit_bytes(commit)
        self.assertEqual(len(data), self.fixture["commit_byte_length"])
        self.assertEqual(data[-1], 0x0A)
        self.assertEqual(sha256_upper(data), self.fixture["commit_hash"])
        self.assertEqual(commit_hash_from_obj(commit), self.fixture["commit_hash"])


if __name__ == "__main__":
    unittest.main()
