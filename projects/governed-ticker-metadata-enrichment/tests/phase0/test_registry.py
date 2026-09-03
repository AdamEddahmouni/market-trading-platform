import os
import unittest

from market_platform_foundation.registry import resolve_registry, registry_snapshot


class RegistryTests(unittest.TestCase):
    def test_only_six_literal_entries_exist(self):
        self.assertEqual(
            [row["registry_id"] for row in registry_snapshot()],
            [
                "offline.equity_intraday_jsonl",
                "offline.fixture_manifest",
                "simulation.bar_conservative",
                "simulation.book_aware_l2_v1",
                "simulation.noop",
                "simulation.options_conservative",
            ],
        )

    def test_unknown_identifier_fails_closed(self):
        with self.assertRaises(KeyError):
            resolve_registry("broker.live")

    def test_environment_cannot_supply_module(self):
        os.environ["ADAPTER_MODULE"] = "prototype.provider"
        try:
            with self.assertRaises(KeyError):
                resolve_registry(os.environ["ADAPTER_MODULE"])
        finally:
            del os.environ["ADAPTER_MODULE"]
