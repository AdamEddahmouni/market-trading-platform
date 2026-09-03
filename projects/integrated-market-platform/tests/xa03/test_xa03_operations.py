"""XA-03 operator capability tests."""

from __future__ import annotations

import unittest

from market_platform_foundation.xa01.registry import reset_registry_for_tests as reset_xa01_registry
from market_platform_foundation.xa02.registry import reset_registry_for_tests as reset_xa02_registry
from market_platform_foundation.xa03.fixtures import admit_fixture
from market_platform_foundation.xa03.operations import execute
from market_platform_foundation.xa03.registry import reset_registry_for_tests


class Xa03OperationsTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_xa01_registry()
        reset_xa02_registry()
        reset_registry_for_tests()

    def test_status_lists_both_verticals(self) -> None:
        result = execute("XA03.OP.STATUS")
        self.assertEqual(result.outcome_code, "OK")
        verticals = result.verification["verticals"]
        self.assertIn("fred_rates", verticals)
        self.assertIn("cftc_positioning", verticals)

    def test_validate_after_bootstrap(self) -> None:
        admit_fixture(fixture_name="positioning_reference_vertical.json")
        result = execute("XA03.OP.VALIDATE")
        self.assertEqual(result.outcome_code, "OK")
        self.assertEqual(result.verification["findings"], [])

    def test_show_source(self) -> None:
        admit_fixture(fixture_name="positioning_reference_vertical.json")
        result = execute(
            "XA03.OP.SHOW_SOURCE",
            {"market_report_id": "CFTC_MARKET:13874+:TFF:FUTURES_ONLY"},
        )
        self.assertEqual(result.outcome_code, "OK")
        self.assertGreater(result.verification["observation_count"], 0)

    def test_admit_fixture_capability(self) -> None:
        result = execute(
            "XA03.OP.ADMIT_FIXTURE",
            {"fixture_name": "positioning_reference_vertical.json"},
        )
        self.assertEqual(result.outcome_code, "OK")
        self.assertGreater(result.verification["observation_count"], 0)
