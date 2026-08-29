"""XA-02 operations and FRED compatibility tests."""

from __future__ import annotations

import unittest

from market_platform_foundation.xa01.registry import reset_registry_for_tests as reset_xa01_registry
from market_platform_foundation.xa02.fixtures import admit_fixture
from market_platform_foundation.xa02.operations import execute
from market_platform_foundation.xa02.registry import reset_registry_for_tests


class Xa02OperationsTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_xa01_registry()
        reset_registry_for_tests()

    def test_status_and_validate(self) -> None:
        admit_fixture(fixture_name="rates_reference_vertical.json")
        status = execute("XA02.OP.STATUS")
        self.assertEqual(status.outcome_code, "OK")
        self.assertGreaterEqual(status.verification["observation_count"], 5)
        validate = execute("XA02.OP.VALIDATE")
        self.assertEqual(validate.outcome_code, "OK")

    def test_show_indicator_and_list_relationships(self) -> None:
        admit_fixture(fixture_name="rates_reference_vertical.json")
        show = execute(
            "XA02.OP.SHOW_INDICATOR",
            {"canonical_indicator_id": "US_10Y_TREASURY_YIELD"},
        )
        self.assertEqual(show.outcome_code, "OK")
        self.assertEqual(show.verification["provider_series_id"], "DGS10")
        relationships = execute("XA02.OP.LIST_RELATIONSHIPS")
        self.assertEqual(relationships.outcome_code, "OK")
        self.assertGreaterEqual(len(relationships.verification["relationships"]), 5)

    def test_fred_tests_still_importable(self) -> None:
        import tests.fred.test_fred as fred_tests

        self.assertTrue(hasattr(fred_tests, "FredRevisionTests"))
