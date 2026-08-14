import unittest

from market_platform_foundation.credential_audit import (
    audit_path_inventory,
    classify_path,
    redact_match,
    validate_public_example,
)


class CredentialAuditTests(unittest.TestCase):
    def test_private_env_is_rejected_without_opening(self):
        result = classify_path("config/.env", tracked=True)
        self.assertEqual(result["classification"], "PROHIBITED_TRACKED_MATERIAL")
        self.assertFalse(result["content_read"])

    def test_match_output_contains_no_value_or_context(self):
        finding = redact_match("TOKEN_RULE", "PATH-0001", "abc-secret-value")
        self.assertEqual(
            set(finding),
            {"opaque_path_id", "revision_id", "rule_id", "sanitized_location"},
        )
        self.assertNotIn("abc-secret-value", repr(finding))

    def test_public_examples_require_literal_placeholders(self):
        self.assertTrue(validate_public_example("EXAMPLE"))
        self.assertFalse(validate_public_example("looks-real"))

    def test_inventory_reports_only_opaque_ids(self):
        report = audit_path_inventory(["config/.env", "README.md"], tracked=True)
        self.assertEqual(report["prohibited_count"], 1)
        self.assertNotIn("config/.env", repr(report))
