from __future__ import annotations

import unittest

from tools.postroot.contract_core import (
    ContractError,
    canonical_bytes,
    hash_without_fields,
    sha256_bytes,
    strict_loads,
    validate_contract,
)


def contract_for(field_rules: dict[str, object]) -> dict[str, object]:
    return {
        "additional_properties": "REJECT",
        "contract_id": "synthetic.example.contract",
        "field_rules": field_rules,
        "required_fields": sorted(field_rules),
        "schema_version": "1.0.0",
        "validation_rules": [],
    }


class ContractCoreTests(unittest.TestCase):
    def test_canonical_bytes_have_sorted_keys_and_no_trailing_newline(self):
        self.assertEqual(canonical_bytes({"z": 1, "a": 2}), b'{"a":2,"z":1}')

    def test_canonical_bytes_preserve_utf8(self):
        self.assertEqual(canonical_bytes({"value": "caf\N{LATIN SMALL LETTER E WITH ACUTE}"}), b'{"value":"caf\xc3\xa9"}')

    def test_sha256_bytes_is_uppercase(self):
        self.assertEqual(
            sha256_bytes(b"synthetic"),
            "B3CC0475BB78A5026098858E9889ACF666D31062D513D303314ECA31D36E72F2",
        )

    def test_duplicate_key_is_rejected(self):
        with self.assertRaisesRegex(ContractError, "JSON-DUPLICATE-KEY"):
            strict_loads(b'{"a":1,"a":2}')

    def test_bom_is_rejected(self):
        with self.assertRaisesRegex(ContractError, "BYTE-UTF8-BOM"):
            strict_loads(b"\xef\xbb\xbf{}")

    def test_invalid_utf8_is_rejected(self):
        with self.assertRaisesRegex(ContractError, "BYTE-UTF8-INVALID"):
            strict_loads(b'{"value":"\xff"}')

    def test_invalid_json_is_rejected(self):
        with self.assertRaisesRegex(ContractError, "JSON-PARSE-INVALID"):
            strict_loads(b'{"value":}')

    def test_hash_omits_only_named_fields(self):
        left = hash_without_fields({"id": "ignored", "value": 1}, {"id"})
        right = hash_without_fields({"id": "different", "value": 1}, {"id"})
        self.assertEqual(left, right)

    def test_closed_object_rejects_extra_field(self):
        result = validate_contract(
            {"name": "ok", "extra": True},
            contract_for({"name": {"type": "string", "format": "NONEMPTY"}}),
        )
        self.assertEqual(result.status, "FAIL")
        self.assertEqual(result.reason_codes, ("SCHEMA-UNDECLARED-FIELD",))

    def test_missing_required_field_is_rejected(self):
        result = validate_contract(
            {}, contract_for({"name": {"type": "string", "format": "NONEMPTY"}})
        )
        self.assertEqual(result.reason_codes, ("SCHEMA-MISSING-REQUIRED-FIELD",))

    def test_recursive_types_and_formats_accept_valid_value(self):
        value = {
            "active": True,
            "count": 2,
            "identity": "phase0.synthetic_record",
            "members": ["a", "b"],
            "nested": {"digest": "A" * 64},
            "recorded_at": "2026-08-14T20:15:16.123456789Z",
            "status": "PASS",
        }
        field_rules = {
            "active": {"type": "boolean"},
            "count": {"type": "integer"},
            "identity": {"type": "string", "format": "LOGICAL_ID"},
            "members": {
                "type": "array",
                "item_rule": {"type": "string", "format": "NONEMPTY"},
                "ordering": "LEXICOGRAPHIC_UNIQUE",
            },
            "nested": {
                "type": "object",
                "additional_properties": "REJECT",
                "field_rules": {"digest": {"type": "string", "format": "SHA256"}},
                "required_fields": ["digest"],
            },
            "recorded_at": {"type": "string", "format": "TIMESTAMP"},
            "status": {"type": "string", "enum": ["BLOCKED", "FAIL", "PASS"]},
        }
        self.assertEqual(validate_contract(value, contract_for(field_rules)).status, "PASS")

    def test_boolean_is_not_an_integer(self):
        result = validate_contract({"count": True}, contract_for({"count": {"type": "integer"}}))
        self.assertEqual(result.reason_codes, ("SCHEMA-TYPE-INVALID",))

    def test_invalid_values_report_sorted_unique_independent_codes(self):
        value = {
            "identity": "not a logical id",
            "members": ["b", "a", "a"],
            "status": "UNKNOWN",
        }
        field_rules = {
            "identity": {"type": "string", "format": "LOGICAL_ID"},
            "members": {
                "type": "array",
                "item_rule": {"type": "string"},
                "ordering": "LEXICOGRAPHIC_UNIQUE",
            },
            "status": {"type": "string", "enum": ["PASS"]},
        }
        result = validate_contract(value, contract_for(field_rules))
        self.assertEqual(
            result.reason_codes,
            (
                "SCHEMA-ARRAY-DUPLICATE",
                "SCHEMA-ARRAY-ORDER",
                "SCHEMA-ENUM-INVALID",
                "SCHEMA-FORMAT-INVALID",
            ),
        )

    def test_sequence_allows_duplicates_and_preserves_order(self):
        rule = {
            "values": {
                "type": "array",
                "item_rule": {"type": "integer"},
                "ordering": "SEQUENCE",
            }
        }
        self.assertEqual(
            validate_contract({"values": [2, 1, 1]}, contract_for(rule)).status,
            "PASS",
        )

    def test_invalid_contract_policy_is_reported(self):
        malformed = contract_for({"name": {"type": "string"}})
        malformed["additional_properties"] = "ALLOW"
        result = validate_contract({"name": "ok"}, malformed)
        self.assertEqual(
            result.reason_codes,
            ("SCHEMA-ADDITIONAL-PROPERTY-POLICY",),
        )


if __name__ == "__main__":
    unittest.main()
