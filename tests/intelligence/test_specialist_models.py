"""BUILD 11 specialist runtime model tests."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.specialists import (
    MicrostructureSpecialistPolicyV1,
    SpecialistDiagnosticCode,
    SpecialistExecutionStatus,
)


class SpecialistModelTests(unittest.TestCase):
    def test_policy_identity_is_stable(self) -> None:
        first = MicrostructureSpecialistPolicyV1().identity
        second = MicrostructureSpecialistPolicyV1().identity
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("MSPOL-"))

    def test_status_values(self) -> None:
        self.assertEqual(SpecialistExecutionStatus.COMPLETED.value, "COMPLETED")
        self.assertEqual(SpecialistExecutionStatus.STALE.value, "STALE")

    def test_diagnostic_codes_include_required_taxonomy(self) -> None:
        required = {
            "UNSUPPORTED_DOMAIN",
            "UNSUPPORTED_SEMANTIC_EVENT",
            "MISSING_REQUIRED_SOURCE",
            "STALE_INFERENCE",
            "EVIDENCE_CONFLICT",
        }
        actual = {item.value for item in SpecialistDiagnosticCode}
        self.assertTrue(required.issubset(actual))


if __name__ == "__main__":
    unittest.main()
