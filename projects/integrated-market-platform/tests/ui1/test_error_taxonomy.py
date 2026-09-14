"""Canonical error taxonomy mapping and UI API error envelope (BL-0702)."""

from __future__ import annotations

import importlib.util
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ERRORS_MODULE_PATH = ROOT / "src/market_platform_foundation/ui_api/errors.py"

_spec = importlib.util.spec_from_file_location("imp_ui_api_errors", ERRORS_MODULE_PATH)
assert _spec and _spec.loader
_errors = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_errors)

CANONICAL_ERROR_CATEGORY_VALUES = _errors.CANONICAL_ERROR_CATEGORY_VALUES
CanonicalErrorCategory = _errors.CanonicalErrorCategory
build_error_response_payload = _errors.build_error_response_payload
canonical_error_category = _errors.canonical_error_category

SERVER_PATH = ROOT / "src/market_platform_foundation/ui_api/server.py"
_SEND_ERROR_LITERAL = re.compile(r'_send_error_json\(\s*"([A-Z][A-Z0-9_]*)"')


class ErrorTaxonomyTests(unittest.TestCase):
    def test_twelve_canonical_categories(self) -> None:
        expected = {
            "VALIDATION_ERROR",
            "PROVIDER_UNAVAILABLE",
            "PROVIDER_REJECTED",
            "STALE_DATA",
            "UNSUPPORTED_CAPABILITY",
            "ACCOUNT_UNAVAILABLE",
            "RISK_BLOCKED",
            "MODE_BLOCKED",
            "AUTH_ERROR",
            "RATE_LIMITED",
            "TIMEOUT",
            "INTERNAL_ERROR",
        }
        self.assertEqual(set(CanonicalErrorCategory), {CanonicalErrorCategory(v) for v in expected})
        self.assertEqual(CANONICAL_ERROR_CATEGORY_VALUES, expected)

    def test_identity_for_canonical_reason_codes(self) -> None:
        for value in CANONICAL_ERROR_CATEGORY_VALUES:
            self.assertEqual(canonical_error_category(value), CanonicalErrorCategory(value))

    def test_documented_api_examples(self) -> None:
        samples = {
            "UI_REQUEST_INVALID": CanonicalErrorCategory.VALIDATION_ERROR,
            "PAPER_EXECUTION_NOT_AUTHORIZED": CanonicalErrorCategory.MODE_BLOCKED,
            "OPERATIONAL_ACCOUNT_UNKNOWN": CanonicalErrorCategory.ACCOUNT_UNAVAILABLE,
            "OPEND_UNAVAILABLE": CanonicalErrorCategory.PROVIDER_UNAVAILABLE,
            "AUTH_REQUIRED": CanonicalErrorCategory.AUTH_ERROR,
            "RISK_MAX_ORDER_EXCEEDED": CanonicalErrorCategory.RISK_BLOCKED,
            "UI_INTERNAL_ERROR": CanonicalErrorCategory.INTERNAL_ERROR,
        }
        for code, category in samples.items():
            with self.subTest(reason_code=code):
                self.assertEqual(canonical_error_category(code), category)

    def test_error_response_payload_shape(self) -> None:
        payload = build_error_response_payload("UI_REQUEST_INVALID", "bad field")
        self.assertEqual(
            payload,
            {
                "error": "bad field",
                "reason_code": "UI_REQUEST_INVALID",
                "error_category": "VALIDATION_ERROR",
            },
        )

    def test_server_literal_reason_codes_map_to_canonical(self) -> None:
        source = SERVER_PATH.read_text(encoding="utf-8")
        codes = sorted(set(_SEND_ERROR_LITERAL.findall(source)))
        self.assertTrue(codes, "expected _send_error_json string literals in server.py")
        for code in codes:
            with self.subTest(reason_code=code):
                category = canonical_error_category(code)
                self.assertIn(category.value, CANONICAL_ERROR_CATEGORY_VALUES)

    def test_frontend_errors_ts_matches_canonical_categories(self) -> None:
        source = (ROOT / "ui/src/api/errors.ts").read_text(encoding="utf-8")
        match = re.search(r"export const CANONICAL_ERROR_CATEGORIES = \[([^\]]+)\] as const", source)
        self.assertIsNotNone(match, "expected CANONICAL_ERROR_CATEGORIES in ui/src/api/errors.ts")
        values = set(re.findall(r'"([A-Z_]+)"', match.group(1)))
        self.assertEqual(values, CANONICAL_ERROR_CATEGORY_VALUES)
        self.assertNotIn("_REASON_CODE_TO_CATEGORY", source)
        self.assertNotIn("canonical_error_category", source)


if __name__ == "__main__":
    unittest.main()
