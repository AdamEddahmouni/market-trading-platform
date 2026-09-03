import unittest

from tools.postroot.contract_core import (
    ContractError,
    canonical_bytes,
    hash_without_fields,
    strict_loads,
    validate_contract,
)


class ContractCoreTests(unittest.TestCase):
    def test_canonical_bytes_have_no_trailing_newline(self):
        self.assertEqual(canonical_bytes({"z": 1, "a": 2}), b'{"a":2,"z":1}')

    def test_duplicate_key_is_rejected(self):
        with self.assertRaisesRegex(ContractError, "JSON-DUPLICATE-KEY"):
            strict_loads(b'{"a":1,"a":2}')

    def test_bom_is_rejected(self):
        with self.assertRaisesRegex(ContractError, "BYTE-UTF8-BOM"):
            strict_loads(b"\xef\xbb\xbf{}")

    def test_hash_omits_only_named_fields(self):
        left = hash_without_fields({"id": "ignored", "value": 1}, {"id"})
        right = hash_without_fields({"id": "different", "value": 1}, {"id"})
        self.assertEqual(left, right)

    def test_closed_object_rejects_extra_field(self):
        contract = {
            "additional_properties": "REJECT",
            "contract_id": "example",
            "field_rules": {
                "name": {"type": "string", "format": "NONEMPTY"},
            },
            "required_fields": ["name"],
            "schema_version": "1.0.0",
            "validation_rules": [],
        }
        result = validate_contract({"name": "ok", "extra": True}, contract)
        self.assertEqual(result.status, "FAIL")
        self.assertEqual(result.reason_codes, ("SCHEMA-UNDECLARED-FIELD",))


if __name__ == "__main__":
    unittest.main()
